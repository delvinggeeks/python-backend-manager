"""Smoke tests that pass with zero extras installed."""

from __future__ import annotations


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body


async def test_agent_requires_backend(client):
    # With no ANTHROPIC_API_KEY / no framework, the endpoint reports 503 cleanly.
    resp = await client.post("/agent", json={"prompt": "hello"})
    assert resp.status_code == 503
