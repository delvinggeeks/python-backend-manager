"""Billing & entitlements (provider-agnostic). Requires the `db` + `users` + `payments` extras.

Payments go through a hexagonal port: ``app.billing.ports.PaymentsPort`` is the app's-needs
contract; ``app.billing.adapters`` holds the Stripe and Razorpay implementations; the active
one is chosen by ``settings.payments_provider`` (see ``app.billing.provider``). Each org is a
provider customer (`organizations.payments_customer_id`). This package adds org-scoped
checkout + customer-portal routers, a signature-verified, idempotent webhook that syncs a
`Subscription` row from normalized events, and an entitlements layer (`plan -> features`)
exposed as a `require_feature(...)` dependency. `app.main.create_app` mounts the org-scoped
router under `/orgs` and the webhook router under `/billing`. The heavy imports (the provider
SDKs, ORM models) live in the submodules, so importing this package is cheap and free of
import-time side effects.
"""

from __future__ import annotations
