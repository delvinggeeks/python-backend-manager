"""PII scrubbing in the logging pipeline — redaction is a processor, not a call-site discipline.

Scrubbing belongs in the processor chain for the same reason tenant isolation belongs in the
database: a call-site rule fails the first time someone logs an object they did not write. These
tests assert on RENDERED output, because that is what actually reaches the log sink.
"""

from __future__ import annotations

import json

import pytest
import structlog

from app.core.logging import configure_logging

# Values that must never survive to the sink, keyed by the field name that should mask them.
_SENTINELS = {
    "password": "hunter2-should-never-appear",
    "token": "tok_live_should_never_appear",
    "secret": "shh-should-never-appear",
    "authorization": "Bearer should-never-appear",
    "api_key": "sk_live_should_never_appear",
    "email": "person@should-never-appear.test",
}


@pytest.fixture(autouse=True)
def _json_logs(monkeypatch: pytest.MonkeyPatch):
    """Render JSON so assertions read the sink's bytes, not a console-formatted approximation."""
    from app.core.config import get_settings

    monkeypatch.setenv("LOG_JSON", "true")
    get_settings.cache_clear()
    configure_logging()
    yield
    get_settings.cache_clear()


def test_sentinel_values_never_reach_the_rendered_output(capsys: pytest.CaptureFixture) -> None:
    """Every sensitive value is masked at the top level of an event."""
    structlog.get_logger(__name__).info("user.updated", **_SENTINELS)
    out = capsys.readouterr().out
    leaked = [name for name, value in _SENTINELS.items() if value in out]
    assert not leaked, f"these values reached the log sink unmasked: {leaked}\n{out}"


def test_sentinel_values_are_masked_at_any_nesting_depth(capsys: pytest.CaptureFixture) -> None:
    """A nested payload is the common case — an object logged wholesale, not field by field."""
    structlog.get_logger(__name__).info(
        "webhook.received",
        payload={"user": {"profile": {"email": _SENTINELS["email"]}}, "auth": dict(_SENTINELS)},
        items=[{"token": _SENTINELS["token"]}],
    )
    out = capsys.readouterr().out
    leaked = [name for name, value in _SENTINELS.items() if value in out]
    assert not leaked, f"nested values reached the log sink unmasked: {leaked}\n{out}"


def test_non_sensitive_fields_are_untouched(capsys: pytest.CaptureFixture) -> None:
    """Scrubbing must not eat the logs: anything not on the sentinel list survives verbatim."""
    structlog.get_logger(__name__).info("order.created", order_id="ord_123", amount=4200)
    line = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert line["order_id"] == "ord_123"
    assert line["amount"] == 4200
