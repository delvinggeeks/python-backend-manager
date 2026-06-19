# CURRENT-STATE.md — what the template is today (as of v0.18.0)

> Inventory for the deep-research spec-hardening effort (Phase 0). Source of truth for
> *what exists*; gaps and target state live in [GAP-ANALYSIS.md](GAP-ANALYSIS.md),
> [ARCHITECTURE.md](ARCHITECTURE.md), and [ROADMAP.md](ROADMAP.md).

**Note on version:** the task brief said "current: v0.17.0"; `main` is actually at **v0.18.0**
(the admin / sqladmin control panel merged in PR #31, `aa96495`). This inventory reflects v0.18.0.

---

## 1. What this repo is

A **Copier template** (`_subdirectory: template`) that generates self-maintaining FastAPI
backends. Two surfaces:

- **`template/`** — the body rendered into each generated service. `*.jinja` files are
  content-rendered; everything else is copied verbatim; path/file names are *always*
  templated (a dir named `{% raw %}{% if include_x %}x{% endif %}{% endraw %}` renders only when the toggle is on).
- **Repo root** — the template's own management surface (CI/CD, `copier.yml`, Renovate, these
  docs). Not rendered into services.

Copier config: `_envops: trim_blocks: true, lstrip_blocks: true`; default Jinja delimiters;
`_answers_file: .copier-answers.yml`. Python 3.13/3.14, managed by **uv**.

---

## 2. Capability toggles & the "implies" graph

Toggles live in `copier.yml`. The computed (hidden) `sync_extras` maps toggles → the uv extras a
service installs. Key relationships (A → B = "A implies B renders"):

```
include_users ─────────────► db + users extras
include_tenancy ───────────► users (org+membership)        ┐
include_rbac ──────────────► tenancy                        │ each implies the
include_api_keys ──────────► tenancy                        │ ones to its right
include_billing ───────────► tenancy + payments extra       │ via the OR-gates
include_webhooks ──────────► tenancy + jobs(worker)         ┘
include_audit ─────────────► db   (users-INDEPENDENT — flat or org-scoped)
include_admin ─────────────► db + users + admin extra (sqladmin)   [v0.18.0]
include_jobs ──────────────► worker extra (arq)             (db/users independent)
include_observability ─────► observability extra (OTel)     (capability-independent)
include_storage ───────────► storage extra (aioboto3)       (no db)
include_email ─────────────► email extra (SMTP/SES/jinja2)  (no db)
include_cache ─────────────► redis
include_worker ────────────► arq
include_mcp ───────────────► FastMCP at /mcp
agent_framework ───────────► one of none|pydantic-ai|langgraph|openai-agents (conflicting extras)
```

A capability that "implies users/db" is OR'd into **every** gate keyed on the
`include_users`/`include_db` token (the db-present and users-present OR-sets, the path-name dir/file
gates, the singular feature gates, and `sync_extras`). This is the central gating discipline.

---

## 3. Shipped modules (capability → what exists + consequential choices)

| Capability | What ships | Consequential choices |
|---|---|---|
| **users / auth** | `fastapi-users` (UUID user, JWT **bearer** login, register/reset/verify/users routers); password hashing via fastapi-users' `PasswordHelper` (pwdlib/argon2). | Access-token-only JWT (**no refresh rotation, no revocation/denylist, no MFA, no SSO/SCIM**). Secret = `USERS_JWT_SECRET`, lifetime `USERS_JWT_LIFETIME_SECONDS` (default 3600). |
| **tenancy** | `Organization` + `Membership` (per-membership `role` string), `/orgs` router, migration `0002`. | **Shared-schema**, single shared DB, **app-level** `org_id` scoping. **No Postgres RLS backstop. No tenant→datasource routing.** GUID PK type from fastapi-users for FK compat. |
| **rbac** | Role hierarchy `owner>admin>member` via `ROLE_RANK`; `require_role()` / `require_scope()` dependency factories over `get_current_membership`; `SCOPES_BY_ROLE` map. | Data-driven, in-process, **<0.1 ms** checks. Coarse role/scope model — **no ABAC/ReBAC, no per-resource grants**. |
| **api_keys** | `ApiKey` (plaintext `prefix` for lookup + **SHA-256** `hashed_secret`), `/orgs/{id}/api-keys` CRUD, an auth dep accepting **JWT *or* API key**, identity router, migration `0003`. | Org-scoped service tokens; `scopes` is a free string. SHA-256 (not a slow KDF) for the secret hash. |
| **billing** | Hexagonal **`PaymentsPort`** with **Stripe + Razorpay** adapters (active one via `payments_provider`), hosted checkout + customer portal, signature-verified webhook with **idempotent `ProcessedEvent`** dedupe, `Subscription` model synced from normalized events, entitlements map + `require_feature()`, migration `0004`. | **Subscription-only.** **No usage metering / rating / invoicing, no hybrid base+overage, no credits/wallets, no burn-rate.** Both provider SDKs ship; one active per service. |
| **storage** | `aioboto3` S3-compatible async client, upload/download/delete/**presigned-URL**, `/storage` router; keys **tenant-prefixed** `orgs/<org_id>/` when tenancy on (pure key helpers, unit-tested). | Works with AWS S3 / MinIO / R2 / any S3-compatible endpoint. No CDN, no virus scan, no per-object encryption beyond provider SSE. |
| **email** | Hexagonal **`EmailPort`** with **SMTP (aiosmtplib) + SES (aioboto3) + console** adapters, jinja2 body templates, typed `send_template`, **suppress-when-unconfigured**; welcome/reset wired into the users flow (enqueued through arq when jobs on). | Transactional **email only** — no SMS/WhatsApp/push/in-app, no user preferences, no digest. |
| **jobs** | **arq** (Redis) worker (`just worker`), thin **`enqueue()` seam** (call sites never import arq; **best-effort** — swallows+logs on Redis outage, returns bool), example task + arq **cron**. | arq used directly (no runtime port — "infra choice, not a swappable vendor"). **No durable workflows** (retries/sagas/human-in-the-loop) for long AI flows. |
| **webhooks** | Tenant-scoped `WebhookEndpoint` (url / per-endpoint `secret` / subscribed events / active), `/orgs/{id}/webhooks` CRUD, `dispatch()` that **enqueues** one delivery per subscribed endpoint; delivery in the arq worker POSTs **HMAC-SHA256-signed** (`X-Webhook-Signature`) via httpx with retry/backoff; migration `0006`. | Hand-rolled delivery. **No SSRF egress guard** (a tenant URL can target `169.254.169.254` / private IPs). No dead-letter UI, no replay, no signature rotation. |
| **audit** | Append-only `AuditLog` (actor/action/target/JSON meta, org-scoped when tenancy), `record()` helper, read-only paginated list (admin-gated under rbac), migration `0005`. **Users-independent** (sqlalchemy `Uuid` when no tenancy, fastapi-users `GUID` when tenancy). | Append-only by construction (no update/delete). Not a general event bus / outbox. |
| **observability** | OTel **three pillars** (traces+metrics+logs over OTLP), auto-instruments FastAPI+httpx (+SQLAlchemy/redis when present), `trace_id`/`span_id` injected into structlog, Prometheus `/metrics`, `/healthz`+`/readyz` (probes db/redis), **optional Sentry** (no-op w/o DSN); self-host compose profile (Collector+Prometheus+Tempo+Loki+Grafana, `just observe`). | Export only when `OTEL_EXPORTER_OTLP_ENDPOINT` set (clean with no collector). Self-host stack by default. No SLO/error-budget config. |
| **admin** | `sqladmin` panel at `/admin`, **superuser-only** `AuthenticationBackend` (fastapi-users password check + re-validated-each-request signed session), `ModelView`s per capability with **secret columns redacted** (password/api-key hashes, webhook secret, provider customer/subscription ids), audit log read-only. | Internal CRUD panel. Server-rendered; no audit of admin actions yet. |
| **mcp** | FastMCP server mounted at `/mcp` (combined lifespan). | Optional; agent-tool exposure surface. |
| **agents** | One agent framework per service (`pydantic-ai`/`langgraph`/`openai-agents`), model tiers from settings (`model_fast`/`model_default`/`model_frontier`). | Frameworks are conflicting extras; never two. |

---

## 4. The ports-and-adapters pattern (the canonical seam)

The repo's core discipline, exemplified by `billing` and `email`:

- **`ports.py`** — a `typing.Protocol` (the hexagonal *port*) expressing the app's needs, plus
  **normalized frozen-dataclass value types** and **provider-neutral exceptions**. The app depends
  only on the port + value types — *never* a vendor SDK. (`PaymentsPort`, `EmailPort`.)
- **`adapters/`** — concrete vendor implementations behind the port (`stripe.py`, `razorpay.py`,
  `smtp.py`, `ses.py`, `console.py`).
- **`provider.py`** — a settings-driven **registry** (`_PROVIDERS: dict[str, Callable[[], Port]]`)
  with a `get_*_provider()` FastAPI dependency; selecting the active adapter touches no app code.
- **Structural contracts** — e.g. `BillingAccount` is a `runtime_checkable` Protocol so the ORM
  `Organization` satisfies it without the port importing the db layer.

**Ports vs toggles** (the two-axis model): a **port** abstracts a *runtime, vendor-swappable*
choice (Stripe↔Razorpay, SMTP↔SES) selected by a setting; a **copier toggle** is a *build-time
framework/capability* choice (db on/off, which agent framework). arq and OTLP are deliberately
*not* ports — "infra choices, not swappable vendors" (the abstraction is the protocol itself).

**Resilience conventions:** best-effort where the subsystem exists to add resilience
(`enqueue()` swallows+logs Redis outages, returns `False`); **no-op-when-unconfigured** (email
suppresses, Sentry no-ops without DSN, observability no-ops without an OTLP endpoint).
**Idempotency** is done where it matters (webhook `ProcessedEvent` (provider, event_id) dedupe) but
**not** generalized to inbound mutations.

---

## 5. Cross-cutting conventions

- **Settings** — `app.core.config.get_settings()` (pydantic-settings, `@lru_cache`); app code never
  reads `os.environ`. Per-capability settings blocks are gated.
- **Logging** — `structlog` via `app.core.logging.get_logger`; human console locally, JSON in prod
  (`LOG_JSON`); `add_trace_context` processor injects span ids when observability is on.
- **Lifespan** — `app.core.lifespan` configures logging on startup; flushes observability on
  shutdown. Pools/clients init commented as extension points.
- **Container** — multi-stage `Dockerfile` (uv, `--frozen`, bytecode-compiled), **non-root** `app`
  user, only `sync_extras` installed.
- **Secrets** — environment / `.env` only. No Vault/KMS seam, no field-level encryption.

---

## 6. CI / CD and the validation discipline

`.github/workflows/ci.yml` has three jobs (CI) + CD:

1. **`generate-and-test`** — the **framework matrix** (4 legs: `none`+db, `pydantic-ai`+db,
   `langgraph`, `openai-agents`). Renders with `copier --vcs-ref HEAD`, **render-gates** the
   generated workflow YAML (so a Renovate action bump can't go green unless it renders valid YAML),
   then `uv lock` + `uv sync` + `ruff check` + `ruff format --check` + `mypy src` + `pytest`.
2. **`generate-capability`** — the **capability matrix** (one row per module ALONE + key combos,
   e.g. `users`, `tenancy`, …, `observability`/`observability_full`, `admin`/`admin_full`). Same
   gate **plus** an alembic round-trip (`upgrade head` / `downgrade base`) guarded on
   `[ -f alembic.ini ]` (db-less legs skip it).
3. **`generate-capability-gate`** — a single **stable required check** that `needs:` the whole
   capability matrix, so adding a capability row is covered by branch protection automatically
   (no protection change). Branch protection: 5 required checks (4 framework + this gate),
   `enforce_admins=true`, `strict=true`.
4. **CD** — on push to `main` after CI, auto-tags a SemVer from the Conventional-Commit prefix
   (`feat:`/`fix:`/breaking) and cuts a GitHub Release; downstream services `copier update` to it.

**The edge validation matrix every template change must pass** (hard-won; each guards a real past
bug):
- **byte-identity** — an OFF render (capability off) is **byte-for-byte identical** to the prior
  release; gating must emit nothing when off.
- **ALONE leg** — the capability at **minimal deps** installs + passes (catches dependency leaks,
  e.g. a db-less module importing a db-only lib).
- **`--vcs-ref HEAD` from a clean committed tree** — commit before validating; a dirty worktree
  false-greens locally while CI fails; omitting `--vcs-ref` renders the latest *tag*, silently
  dropping new files.
- **tests under no infra** — pytest runs with **no live Redis/DB/collector** (sqlite tempfile,
  `REDIS_URL=redis://127.0.0.1:6399`); a running local service must not false-green a request-path
  connection CI lacks.

---

## 7. What is NOT here (forward pointer)

Missing or seam-absent today (detailed in [GAP-ANALYSIS.md](GAP-ANALYSIS.md)): refresh-token
rotation / JWT revocation / MFA / enterprise SSO+SCIM; Postgres RLS backstop + tenant→datasource
bridge; fine-grained authz (ReBAC/ABAC); **usage metering/rating/invoicing** (priority — the
founder's products are usage-priced); durable workflows for long AI flows; webhook **SSRF egress
guard** + delivery infra hardening; multi-channel notifications (SMS/WhatsApp/push/in-app);
API versioning/pagination standard; **idempotency keys** on mutations; per-tenant rate limiting &
quotas; feature flags; caching; full-text/vector search seam; secrets-manager seam; **PII
field-level encryption + India DPDP data residency**; GDPR/DPDP export + right-to-be-forgotten;
**transactional outbox**; supply-chain hardening (SBOM, image scan, action pinning); SLO posture.
