"""Shared response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    environment: str
    version: str


class AgentRequest(BaseModel):
    prompt: str
    tier: str = "default"  # "fast" | "default" | "frontier"


class AgentResponse(BaseModel):
    output: str
    model: str
