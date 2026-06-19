# PRINCIPLES.md — the laws every phase inherits

> Cross-cutting rules that **every** roadmap phase must obey. A phase spec doesn't restate these;
> it inherits them. If a phase appears to need an exception, that's a signal to revisit the phase,
> not the principle. Companion to [AGENTS.md](../AGENTS.md) (operating rules) and
> [ROADMAP.md](ROADMAP.md) (the ordered plan). These are *additive* to AGENTS.md, never in conflict.

---

## P1 — Two axes of variability: ports vs toggles

Every "it could be different here" decision is exactly one of:

- **Copier toggle** — a **build-time** capability/framework choice baked at generation
  (`include_db`, `agent_framework`, `include_billing`). Mutually-exclusive options are
  *conflicting extras*. A toggle changes *what code exists*.
- **Runtime port** — a **vendor-swappable** boundary selected by a *setting* at run time
  (`PaymentsPort` Stripe↔Razorpay via `payments_provider`; `EmailPort` SMTP↔SES). A port changes
  *which adapter runs*, touching no application code.

**Rule:** a *vendor/provider* you might swap for an equivalent → **port**. A *capability* you either
have or don't → **toggle**. Some things are deliberately *neither* (arq, OTLP): when the open
protocol *is* the abstraction and there's no equivalent vendor to swap, don't invent a port — that's
gold-plating (see P9). When in doubt, prefer a **port + a single default adapter** over a bare
vendor call, because a port is cheap to add now and a refactor is expensive later (the "seam-now"
discipline, P8).

**Port anatomy** (the canonical shape, mirror it):
`ports.py` = a `typing.Protocol` + normalized frozen-dataclass value types + provider-neutral
exceptions; `adapters/` = concrete vendor impls; `provider.py` = a settings-driven registry
(`dict[str, Callable[[], Port]]`) exposing a `get_*_provider()` FastAPI dependency. The app imports
the *port*, never a vendor SDK.

---

## P2 — Gated, and byte-for-byte invisible when off

All new code for a capability lives behind its `include_*` toggle. **An OFF render must be
byte-for-byte identical to the previous release.** Adding `or include_x` to an existing gate is
safe because `X or false == X`; reformatting a shared line is *not* (it changes the OFF output).
A capability that "implies" db/users is OR'd into **every** gate carrying the implied token (the
db-present and users-present OR-sets, the path-name dir/file gates, the singular feature gates, and
the computed `sync_extras`) — `grep` the token to enumerate; never eyeball it.

---

## P3 — The edge validation matrix (every template change passes all four)

A change is not done until it passes, locally and in CI, the matrix that has caught every recent
class of bug:

1. **Byte-identity OFF** — capability-off render == the prior release, byte-for-byte.
2. **ALONE leg (minimal deps)** — the capability at its *minimum* dependency set installs, lints,
   type-checks, tests, and (if db-backed) round-trips its migrations. Catches dependency leaks
   (a module importing a lib its extra doesn't pull). Validate the **MAXIMAL** combo too — some
   failures (import-sort, missing-table) only appear when all gated blocks render.
3. **Clean-tree `--vcs-ref HEAD`** — commit first; render from the committed tree. A dirty worktree
   false-greens locally; omitting `--vcs-ref` renders the latest *tag* and silently drops new files.
4. **Tests under no infra** — pytest passes with **no live Redis/DB/collector** (sqlite tempfile,
   `REDIS_URL` pointed at a dead port). A running local service must not mask a request-path
   connection CI lacks.

Each new capability adds a `generate (capability)` matrix **row** (ALONE) and, where combinations
matter, a `*_full` row — never a new required check (the gate aggregates the matrix).

---

## P4 — Resilience is best-effort; unconfigured is a no-op

- **Best-effort at the seam:** a subsystem that exists to *add* resilience must not *remove* it.
  `enqueue()` swallows+logs a Redis outage and returns `False` rather than breaking the request that
  scheduled the job. Side-channel effects (webhooks, analytics, audit fan-out) are best-effort by
  default; the request path stays up.
- **No-op when unconfigured:** a capability with no credentials degrades silently and safely — email
  suppresses, Sentry no-ops without a DSN, observability exports nothing without an OTLP endpoint. A
  freshly generated service **runs clean with zero external config**. New capabilities inherit this:
  ship a working *console/null* adapter as the default.

---

## P5 — Idempotency and exactly-once-effect

Money, messages, and external side-effects must tolerate retries and replays:

- **Inbound** mutations that create charges/records expose an idempotency key (Stripe-style
  `Idempotency-Key`); a replay returns the original result, not a duplicate effect.
- **Webhook/event ingestion** dedupes on `(source, event_id)` (the existing `ProcessedEvent`
  pattern) so redelivery is a no-op.
- **Outbound** events use the **transactional outbox** (state change + event enqueue commit in one
  DB transaction; a relay publishes) to defeat dual-write loss. Generalize the pattern the webhook
  module hints at; don't reinvent per-feature.

---

## P6 — Defense in depth, least privilege, tenant isolation as a backstop

- **App-level tenant scoping is necessary but not sufficient.** Where the data store supports it
  (Postgres RLS), add an **independent** backstop so a missing `WHERE org_id=` can't leak across
  tenants. Two independent layers, not one.
- **Least privilege everywhere:** non-root containers; per-tenant key prefixes for storage; the
  admin panel superuser-only and re-validated each request; secrets never logged or surfaced
  (the admin redaction discipline).
- **Egress is hostile:** any user-supplied URL the server fetches (webhooks, imports) passes an
  **SSRF guard** (resolve-then-pin; block private/link-local/loopback/cloud-metadata; re-validate on
  redirect).

---

## P7 — Secrets hygiene and data-protection by construction

- Secrets come from `get_settings()`, never `os.environ` in app code, never committed. A
  **`SecretsPort`** seam lets a service move from `.env` to a managed secrets store without app
  changes.
- **PII is encrypted at the field level** where it's sensitive, via envelope encryption behind a KMS
  seam, so a DB dump alone isn't a breach and **crypto-shredding** (drop the key) makes erasure
  tractable.
- **Data-subject rights (export + erasure)** are designed in via a per-tenant/per-subject data map,
  not bolted on. **India residency (DPDP Act 2023):** default to India-region infra and
  self-hostable components; never make a managed cross-border vendor the *only* path — it sits
  behind a port so an India-resident adapter can replace it.

---

## P8 — Cost-effective, self-hostable defaults; managed is a seam

For the bootstrapped-founder / India-SMB context, the **default adapter** for any port is the
**cheapest credible self-hostable / open-source** option (prefer Postgres/Redis-native to avoid new
infra), and the **managed** provider is a *later swap behind the same port*. "Seam-now,
build-later" is the standing posture: when the right answer is "not yet," add the **port + a minimal
default adapter (or a stub)** now so adopting the heavy implementation later is an adapter swap, not
a refactor. Every library/provider choice is recorded as an ADR in
[LIBRARY-DECISIONS.md](LIBRARY-DECISIONS.md) with cost at small *and* large scale, license
(flag AGPL/BSL/SSPL/source-available traps), lock-in, and the swap path.

---

## P9 — Lean where it doesn't matter, robust where it does (anti-gold-plating)

The discipline cuts **both** ways. Close real gaps **and** refuse manufactured ones. Every addition
is justified against a concrete need; "an enterprise might want it" is not a need until the seam to
provide it is cheap and the absence is a real risk. Prefer the smallest thing that is correct:
a Postgres table over a new service, a library over a sidecar, one default adapter over three. A
phase that adds a subsystem with no consumer, or a port with one conceivable adapter forever, is
gold-plating — reject it or downgrade it to a documented future seam.

---

## P10 — Observability and operability by default

Every capability is observable the moment it ships: structured logs via `structlog`
(trace-correlated when observability is on), spans/metrics through the existing OTel seam, and a
readiness contribution where it owns a dependency (`/readyz` probes what's present). New
long-running or external-call work emits a span and a best-effort metric. Health/SLO posture is a
first-class output, not an afterthought (P10 pairs with P4: degraded-but-up beats down).

---

### How a phase uses this file

A ROADMAP phase spec lists only its **deltas**: the toggle(s)/port(s) it adds, its
dependencies/implies, its definition-of-done, and its exact validation-matrix + CI-row plan. It
**inherits** P1–P10. Review (human or `build-judge`) checks the deltas *and* that the inherited laws
hold (byte-identity, ALONE leg, no-infra tests, no-op-when-unconfigured, cost-justified choice).
