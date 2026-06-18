"""API-key routers. Requires the `db` + `users` extras.

``router`` is org-scoped (mounted under ``/orgs``) and reuses the tenancy membership
dependency, so every route is authorised by the caller's membership in ``{org_id}``:

    POST   /orgs/{org_id}/api-keys        mint a key (full secret returned ONCE)
    GET    /orgs/{org_id}/api-keys        list this org's keys (prefixes only)
    DELETE /orgs/{org_id}/api-keys/{id}   revoke a key

``identity_router`` exposes ``GET /whoami`` — a protected route that accepts EITHER a JWT
or an ``X-API-Key`` header and echoes the resolved principal.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api_keys.dependencies import Principal, get_principal
from app.api_keys.models import ApiKey
from app.api_keys.schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyRead, PrincipalRead
from app.api_keys.security import generate_key, utcnow
from app.db.session import get_session
from app.tenancy.dependencies import get_current_membership
from app.tenancy.models import Membership

router = APIRouter()
identity_router = APIRouter()


def _to_read(api_key: ApiKey) -> ApiKeyRead:
    """Project an ORM row to ``ApiKeyRead``, splitting stored scopes into a list."""
    return ApiKeyRead(
        id=api_key.id,
        organization_id=api_key.organization_id,
        created_by_user_id=api_key.created_by_user_id,
        name=api_key.name,
        prefix=api_key.prefix,
        scopes=api_key.scopes.split() if api_key.scopes else [],
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        revoked_at=api_key.revoked_at,
        created_at=api_key.created_at,
    )


@router.post(
    "/{org_id}/api-keys",
    response_model=ApiKeyCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    org_id: uuid.UUID,
    payload: ApiKeyCreate,
    membership: Membership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_session),
) -> ApiKeyCreated:
    """Mint an API key for the org. The full secret is returned ONCE, here only."""
    full_key, prefix, hashed_secret = generate_key()
    expires_at = (
        utcnow() + timedelta(days=payload.expires_in_days)
        if payload.expires_in_days is not None
        else None
    )
    api_key = ApiKey(
        organization_id=org_id,
        created_by_user_id=membership.user_id,
        name=payload.name,
        prefix=prefix,
        hashed_secret=hashed_secret,
        scopes=" ".join(payload.scopes) if payload.scopes else None,
        expires_at=expires_at,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    return ApiKeyCreated(**_to_read(api_key).model_dump(), key=full_key)


@router.get("/{org_id}/api-keys", response_model=list[ApiKeyRead])
async def list_api_keys(
    org_id: uuid.UUID,
    membership: Membership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_session),
) -> list[ApiKeyRead]:
    """List the org's API keys — prefixes only, never the secret."""
    result = await session.execute(
        select(ApiKey).where(ApiKey.organization_id == org_id).order_by(ApiKey.created_at)
    )
    return [_to_read(k) for k in result.scalars().all()]


@router.delete("/{org_id}/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    org_id: uuid.UUID,
    key_id: uuid.UUID,
    membership: Membership = Depends(get_current_membership),
    session: AsyncSession = Depends(get_session),
) -> None:
    """Revoke a key (sets ``revoked_at``); revoked keys are rejected by ``get_principal``."""
    result = await session.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.organization_id == org_id)
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
    api_key.revoked_at = utcnow()
    await session.commit()


@identity_router.get("/whoami", response_model=PrincipalRead)
async def whoami(principal: Principal = Depends(get_principal)) -> PrincipalRead:
    """Resolve the caller — works with a user JWT or an ``X-API-Key`` header."""
    return PrincipalRead(
        user_id=principal.user_id,
        organization_id=principal.organization_id,
        api_key_id=principal.api_key_id,
        scopes=principal.scopes,
        auth_method=principal.method,
    )
