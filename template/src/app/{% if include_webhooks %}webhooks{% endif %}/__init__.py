"""Outbound webhooks — tenant-registered endpoints that receive signed event deliveries.

Endpoints are managed through :mod:`app.webhooks.router` (org-scoped CRUD). A domain event is
fanned out with :func:`dispatch`, which enqueues one background delivery per subscribed
endpoint; the worker task (:func:`app.jobs.tasks.deliver_webhook`) signs each POST with the
endpoint's secret. Requires the `db` + `worker` extras.
"""

from __future__ import annotations

from app.webhooks.dispatch import dispatch

__all__ = ["dispatch"]
