"""Example agentic endpoint. Returns 503 if no agent backend is configured."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.agents.example_agent import AgentUnavailableError, run_agent
from app.schemas.common import AgentRequest, AgentResponse

router = APIRouter()


@router.post("", response_model=AgentResponse)
async def run(req: AgentRequest) -> AgentResponse:
    try:
        output, model = await run_agent(req.prompt, tier=req.tier)
    except AgentUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return AgentResponse(output=output, model=model)
