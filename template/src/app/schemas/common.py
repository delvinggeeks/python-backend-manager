"""Shared response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health-check payload: service status, environment, and version."""

    status: str = "ok"
    environment: str
    version: str


class AgentRequest(BaseModel):
    """Request body for the example agent endpoint."""

    prompt: str
    tier: str = "default"  # "fast" | "default" | "frontier"


class AgentResponse(BaseModel):
    """Response from the example agent: the output text and the model used."""

    output: str
    model: str
