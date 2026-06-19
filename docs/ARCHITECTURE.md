# ARCHITECTURE.md — the target full-platform architecture

> Where the template is going. Inherits [PRINCIPLES.md](PRINCIPLES.md); sequenced by
> [ROADMAP.md](ROADMAP.md); choices justified in [LIBRARY-DECISIONS.md](LIBRARY-DECISIONS.md).
> Today's state is [CURRENT-STATE.md](CURRENT-STATE.md). Nothing here is built yet — this is the
> map the phases execute toward.

---

## 1. Shape: one modular monolith, two planes

The platform stays a **single FastAPI modular monolith** (not microservices) — the right default
for a bootstrapped team: one deploy, one Postgres, one Redis, ports for everything that might later
move out. Logically it has two planes:

- **Control plane** — *who/what/how-much*: identity & sessions, tenancy & isolation, authorization,
  API keys, billing & entitlements, feature flags, rate limits & quotas, admin, audit. Mostly
  Postgres-resident, low-volume, strongly-consistent.
- **Data plane** — *the work*: the service's domain endpoints, object storage, search, AI/agent
  flows, background jobs & durable workflows, outbound webhooks & notifications. Higher-volume,
  latency-sensitive, best-effort at the edges.

Everything external (a vendor, a managed service, a second datastore) sits **behind a port** so the
monolith can offload it later without an app rewrite. The seams are the architecture.

```
                         ┌─────────────────────── FastAPI app (app.main) ───────────────────────┐
   request →  middleware │ request-id · tenant-context(contextvars) · authn · idempotency ·       │
   stack               → │ rate-limit/quota · OTel span · structlog                              │
                         ├──────────────────────────────────────────────────────────────────────┤
   CONTROL PLANE         │  users/authn · tenancy(+RLS) · authz · api_keys · billing+metering ·   │
   (Postgres)            │  entitlements · feature-flags · quotas · admin · audit                 │
                         ├──────────────────────────────────────────────────────────────────────┤
   DATA PLANE            │  domain routes · storage · search · agents/MCP                          │
                         │            │ enqueue() seam            │ outbox relay                   │
                         └────────────┼───────────────────────────┼──────────────────────────────┘
                                      ▼                           ▼
                              jobs (arq) / workflows(DBOS)   outbox → webhooks(SSRF-guarded)
                                      │                           │  → notifications(email/SMS/…)
                                      ▼                           ▼
                              Redis · Postgres            tenant endpoints · providers
                         ┌──────────────────────────────────────────────────────────────────────┐
   CROSS-CUTTING         │ secrets(port) · field-encryption(KMS) · observability(OTLP) ·          │
                         │ data-rights(export/erasure) · transactional outbox                     │
                         └──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Request lifecycle (target middleware order)

A mutating request traverses (each layer is a phase's deliverable; all gated):

1. **Request-id / correlation** — bind a request id into structlog contextvars + the OTel span.
2. **Tenant context** — resolve `tenant_id` (JWT/subdomain/header) into a contextvar; the session
   factory and RLS GUC read it. One source of truth for "who is this for."
3. **Authn** — `AuthnPort` validates the access token (fastapi-users JWT default; OIDC/SAML adapter
   later); refresh-rotation + Redis revocation checked here.
4. **Authorization** — `AuthorizationPort.check(subject, action, resource)` (RBAC adapter default).
5. **Idempotency** — for mutations carrying `Idempotency-Key`, replay the stored result or proceed
   once (Postgres-backed).
6. **Rate-limit / quota** — per-tenant, per-plan token bucket (Redis); quota counters tie to the
   entitlements/plan.
7. **Handler** — domain logic; DB access through the **tenant-scoped session** (RLS backstop
   enforces isolation even if a `WHERE org_id` is missed).
8. **Side-effects via outbox** — state change + event row commit in one transaction; a relay
   publishes to webhooks/notifications/metering so nothing is lost on crash (no dual-write).

---

## 3. Port–adapter catalog (the seams)

Legend: **status** = ✅ exists · ➕ build-now (this roadmap) · 🔌 seam-now/adapter-later · 🟢 fine-as-is.
"Default" is the cost-effective self-hostable choice; "Seam to" is the managed/heavier swap.

| Port (boundary) | Status | Default adapter (cost-effective / self-host) | Seam to (later) | Selected by |
|---|---|---|---|---|
| **PaymentsPort** | ✅ | Razorpay / Stripe (subscriptions) | Orb/Metronome (managed billing) | `payments_provider` |
| **MeteringPort** + **BillingPort** (usage→rating→invoice) | ➕ | **Postgres-native** metering+rating+invoice core (events/outbox/wallet) | Lago / OpenMeter (self-host) · Stripe Meters / Orb (managed) | `metering_provider` |
| **EmailPort** | ✅ | SMTP (aiosmtplib) / console | Amazon SES | `email_provider` |
| **NotificationPort** (multi-channel) | 🔌 | in-app (Postgres) + email; FCM push | SMS (MSG91) · WhatsApp (Gupshup) · Novu orchestrator (self-host, MIT) | `notification_provider` per channel |
| **StoragePort** (object storage) | ✅ | **Cloudflare R2** (zero-egress) via S3-compat | AWS S3 / MinIO / B2 | `s3_endpoint_url` |
| **AuthnPort** (identity) | 🔌 | fastapi-users JWT (+refresh rotation, Redis revocation) | OIDC/SAML → self-host **Authentik** (MIT); managed WorkOS/Scalekit | `authn_provider` |
| **AuthorizationPort** (`check`) | 🔌 | in-process RBAC (role hierarchy) | **Cerbos** embedded (Apache-2) / OpenFGA | `authz_engine` |
| **DatasourcePort** (tenant→DB) | ➕ | pooled shared-schema (+Postgres **RLS** backstop) | per-tenant silo (Supabase Mumbai / Aurora) | tenant registry |
| **TaskQueuePort** (`enqueue`) | 🟢 | arq (Redis) — already abstracted by `enqueue()` | — (infra, not a vendor) | — |
| **WorkflowPort** (durable, multi-step) | 🔌 | **DBOS Transact** (Postgres-native) | Temporal (Cloud/self-host) | `workflow_engine` |
| **Webhook delivery** (+SSRF guard) | ✅/➕ | hand-rolled HMAC via arq **+ SSRF egress guard (build-now)** | Svix | — (toggle) |
| **IdempotencyPort** | ➕ | Postgres unique-constraint store | — | toggle |
| **RateLimitPort** | 🔌 | Redis token-bucket (fastapi-limiter), per-tenant/plan | gateway (APISIX/Envoy) | toggle |
| **FeatureFlagPort** | 🔌 | **Unleash** self-host (Apache-2) / DB flags | LaunchDarkly/PostHog | `flags_provider` |
| **CachePort** | 🟢/🔌 | Redis cache-aside + dogpile lock | — | toggle |
| **SearchPort** | 🟢/🔌 | Postgres-native (`tsvector`/GIN + **pgvector**; `pg_search` BM25) | Meilisearch/Typesense/Qdrant (>50M scale) | `search_backend` |
| **SecretsPort** (config provider) | 🔌 | env/`.env` (discipline) | Infisical/Vault/cloud secret manager | `secrets_provider` |
| **KMS / field-encryption** | 🔌 | app-layer envelope encryption (local key) | cloud KMS (AWS/GCP India region) | `kms_provider` |
| **ObservabilityExport** (OTLP) | ✅ | self-host Grafana/Tempo/Loki/Prometheus | Axiom / SigNoz / Grafana Cloud | `OTEL_*` endpoint |

The catalog is the contract surface: a new phase adds *at most* a port + a default adapter + a
toggle; it never wires a vendor SDK into a handler.

---

## 4. Data architecture

- **One Postgres** is the system of record for the control plane and most of the data plane.
  Multi-tenancy is **shared-schema** with `org_id` FKs **plus a Postgres RLS backstop** (session GUC
  `app.current_tenant` set per transaction via a SQLAlchemy event hook; `FORCE ROW LEVEL SECURITY`;
  PgBouncer in **transaction** pooling mode). The **`DatasourcePort`** lets a high-value tenant move
  to a dedicated database (silo) with no query changes — pooled default, silo upgrade path.
- **Redis** is cache + rate-limit + arq queue + JWT revocation denylist. Not a system of record.
- **Object storage** (R2/S3) holds blobs, tenant-prefixed (`orgs/<id>/`).
- **Outbox table** in Postgres makes event publication transactional; a relay (arq/poller) drains it
  to webhooks, notifications, and metering. This is the backbone for reliable side-effects (P5).
- **Search** stays in Postgres (`pgvector` + full-text) until scale forces a dedicated engine behind
  `SearchPort`.

---

## 5. Reliability & security spine

- **Idempotency + outbox** make money/message paths retry- and replay-safe (P5).
- **RLS backstop + SSRF egress guard + least-privilege** are the defense-in-depth layer (P6).
- **Field-level encryption behind a KMS seam + per-subject data map** make DPDP/GDPR export &
  erasure tractable and keep a DB dump from being a breach (P7); **India-region, self-hostable
  defaults** for residency.
- **Supply chain**: uv-locked deps + Renovate, SBOM (CycloneDX), image scan (Trivy), pinned action
  SHAs — the template's own CI and the generated service's CI both harden.
- **Observability by default** (P10): every port emits spans/metrics/trace-correlated logs; `/readyz`
  aggregates the health of whatever dependencies are present; SLO/error-budget posture documented.

---

## 6. What stays a monolith vs what can move out

Nothing *needs* to be a separate service at bootstrap scale. The ports that most plausibly become
external first (and are designed for it): **WorkflowPort** (DBOS→Temporal), **AuthnPort**
(→Authentik/WorkOS for enterprise SSO), **DatasourcePort** (silo tenants), **MeteringPort**
(→managed billing), **Webhook delivery** (→Svix). Each is already a seam, so "extract a service"
is an adapter swap + deploy, never a rewrite — the whole point of the discipline.
