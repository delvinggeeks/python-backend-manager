"""Usage metering, rating & prepaid billing. Requires the `db` + `users` extras.

Records ``UsageEvent``s (idempotent), aggregates them, rates a period against the org's plan's rate
card into an ``Invoice``, and charges it against a prepaid ``CustomerWallet`` — all behind
``MeteringPort`` + ``BillingPort`` (:mod:`app.metering.ports`), default adapter
:mod:`app.metering.service`. The org-scoped router is mounted under ``/orgs`` by ``app.main``. The
plan comes from the billing ``Subscription`` when the billing module is present, else the free card.
"""

from __future__ import annotations
