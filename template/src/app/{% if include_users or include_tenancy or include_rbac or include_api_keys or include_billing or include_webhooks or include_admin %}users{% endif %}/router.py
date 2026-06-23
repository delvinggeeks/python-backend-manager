"""Custom auth router: login + rotating refresh + logout (one + everywhere).

Replaces fastapi-users' built-in ``/auth/jwt`` login/logout so login returns a refresh token
alongside the access token. Mounted by ``app.main.create_app`` under ``/auth/jwt``.

  * ``POST /login``      — email+password → ``TokenPair`` (access + refresh).
  * ``POST /refresh``    — rotate a refresh token → a new pair; replay revokes its family.
  * ``POST /logout``     — denylist this access token (best-effort) + revoke its refresh family.
  * ``POST /logout-all`` — bump ``token_version`` (kills all access tokens) + revoke all families.
"""

from __future__ import annotations

import time

import jwt
from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi_users import exceptions
from fastapi_users.jwt import decode_jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.users.auth import bearer_transport, get_jwt_strategy
from app.users.denylist import deny_jti
from app.users.deps import current_active_user
from app.users.manager import UserManager, get_user_manager
from app.users.models import User
from app.users.schemas import RefreshRequest, TokenPair
from app.users.sessions import (
    RefreshError,
    issue_refresh_token,
    revoke_all_for_user,
    revoke_family_of,
    rotate_refresh_token,
)

router = APIRouter()

_BAD_CREDENTIALS = HTTPException(status.HTTP_400_BAD_REQUEST, detail="LOGIN_BAD_CREDENTIALS")
_BAD_REFRESH = HTTPException(status.HTTP_401_UNAUTHORIZED, detail="INVALID_REFRESH_TOKEN")


async def _denylist_access_token(token: str) -> None:
    """Best-effort: add this access token's jti to the denylist for its remaining lifetime."""
    strategy = get_jwt_strategy()
    try:
        data = decode_jwt(
            token, strategy.decode_key, strategy.token_audience, algorithms=[strategy.algorithm]
        )
    except jwt.PyJWTError:
        return
    jti = data.get("jti")
    exp = data.get("exp")
    if jti is None or exp is None:
        return
    ttl = int(exp) - int(time.time())
    if ttl > 0:
        await deny_jti(jti, ttl)


@router.post("/login", response_model=TokenPair)
async def login(
    credentials: OAuth2PasswordRequestForm = Depends(),
    user_manager: UserManager = Depends(get_user_manager),
    session: AsyncSession = Depends(get_session),
) -> TokenPair:
    """Authenticate by email + password and issue an access token + a rotating refresh token."""
    user = await user_manager.authenticate(credentials)
    if user is None or not user.is_active:
        raise _BAD_CREDENTIALS
    access = await get_jwt_strategy().write_token(user)
    refresh = await issue_refresh_token(session, user.id)
    await session.commit()
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    body: RefreshRequest,
    user_manager: UserManager = Depends(get_user_manager),
    session: AsyncSession = Depends(get_session),
) -> TokenPair:
    """Rotate a refresh token into a fresh pair. A replayed token revokes the family (401)."""
    try:
        user_id, new_refresh = await rotate_refresh_token(session, body.refresh_token)
    except RefreshError:
        await session.commit()  # persist any family revocation triggered by reuse detection
        raise _BAD_REFRESH from None
    try:
        user = await user_manager.get(user_id)
    except exceptions.UserNotExists:
        await session.commit()
        raise _BAD_REFRESH from None
    if not user.is_active:
        await session.commit()
        raise _BAD_REFRESH from None
    access = await get_jwt_strategy().write_token(user)
    await session.commit()
    return TokenPair(access_token=access, refresh_token=new_refresh)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest,
    _user: User = Depends(current_active_user),
    token: str | None = Depends(bearer_transport.scheme),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """End this session: denylist the access token (best-effort) + revoke its refresh family."""
    if token is not None:
        await _denylist_access_token(token)
    await revoke_family_of(session, body.refresh_token)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Log out everywhere: bump token_version (rejects every access token) + revoke all families."""
    # `user` is attached to this request's session (the dependency is cached), so an ORM bump
    # persists on commit — no atomicity concern: a concurrent bump just changes the version again.
    user.token_version += 1
    await revoke_all_for_user(session, user.id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
