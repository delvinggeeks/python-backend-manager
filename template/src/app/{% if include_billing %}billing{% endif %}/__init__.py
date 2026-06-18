"""Billing & entitlements (Stripe). Requires the `db` + `users` + `payments` extras.

Each organization is a Stripe customer (`organizations.stripe_customer_id`). This package
adds org-scoped checkout + customer-portal routers, a signature-verified, idempotent
webhook that syncs a `Subscription` row, and an entitlements layer (`plan -> features`)
exposed as a `require_feature(...)` dependency. `app.main.create_app` mounts the org-scoped
router under `/orgs` and the webhook router under `/billing`. The heavy imports (the Stripe
SDK, ORM models) live in the submodules, so importing this package is cheap and free of
import-time side effects.
"""

from __future__ import annotations
