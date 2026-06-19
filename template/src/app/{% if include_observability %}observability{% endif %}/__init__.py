"""Observability: OpenTelemetry three pillars (traces, metrics, logs) + health + errors.

Public surface: ``setup_observability`` (call once from the app factory, which app.main does)
and ``shutdown_observability`` (called on lifespan shutdown to flush buffered telemetry).
Requires the `observability` extra.
"""

from __future__ import annotations

from app.observability.setup import setup_observability, shutdown_observability

__all__ = ["setup_observability", "shutdown_observability"]
