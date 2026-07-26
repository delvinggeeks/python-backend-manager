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


async def test_security_headers_present(client):
    # SecurityHeadersMiddleware adds the hardening headers to every response, safe-by-default.
    resp = await client.get("/health")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert resp.headers["content-security-policy"] == "frame-ancestors 'none'"
    # HSTS is production-only (it requires HTTPS); the default test env is local, so it's absent.
    assert "strict-transport-security" not in resp.headers
