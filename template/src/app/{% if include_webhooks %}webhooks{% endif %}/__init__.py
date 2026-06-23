"""Outbound webhooks — tenant-registered endpoints that receive signed event deliveries.

Endpoints are managed through :mod:`app.webhooks.router` (org-scoped CRUD). A domain event is
recorded with :func:`dispatch`, which writes it to the transactional outbox in the caller's
transaction (so it is never lost to a queue outage); the arq relay
(:func:`app.webhooks.outbox.drain_outbox`) then fans it out, enqueuing one background delivery per
subscribed endpoint, and the worker task (:func:`app.jobs.tasks.deliver_webhook`) signs each POST
with the endpoint's secret. Requires the `db` + `worker` extras.
"""

from __future__ import annotations

from app.webhooks.dispatch import dispatch

__all__ = ["dispatch"]
