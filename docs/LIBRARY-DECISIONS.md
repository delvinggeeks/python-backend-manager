# LIBRARY-DECISIONS.md — one ADR per subsystem

> The cost-effective-library-selection record. Each ADR: the **chosen default** (cheapest credible
> self-hostable option), **alternatives** with cost + license, **why**, and the **swap path** (which
> port). Costs are 2025-2026 order-of-magnitude for the bootstrapped/India-SMB lens; sources are in
> the per-subsystem research (summarized inline). License traps (AGPL/BSL/SSPL/source-available) are
> flagged because they bind a SaaS differently than MIT/Apache-2. Inherits
> [PRINCIPLES.md#P7–P8](PRINCIPLES.md); sequenced by [ROADMAP.md](ROADMAP.md).

Format — **Default** · *Alternatives (cost / license)* · **Why** · **Swap path**.

---

## ADR-01 — Usage metering & billing  ⭐ priority
- **Default:** **Postgres-native metering→rating→invoice core** (own `UsageEvent`/`UsageOutbox`/
  `Invoice`/`CustomerWallet` tables + a small rating engine), charged through the existing
  `PaymentsPort` (Razorpay default for INR, Stripe where eligible).
- **Alternatives:** **Lago** self-host (free; **AGPLv3 + commercial dual-license** ⚠️ — see
  [DECISIONS-NEEDED](DECISIONS-NEEDED.md)); **OpenMeter** self-host (Apache-2 ✓, newer, Kong-backed);
  **Stripe Billing Meters** (~2% + fees; managed; India invite-only/entity-gated); **Orb**/**Metronome**
  (Metronome acquired by Stripe Jan-2026 — avoid for new) managed, 2-4% of billings.
- **Cost:** small ≈ ₹0 infra (rides existing Postgres); large ≈ Postgres scale only (~0.8-1.5% vs
  Stripe Meters 2%+ or Orb 2-4%). India reality: **Razorpay has no metering engine; Stripe India is
  invite-only** → metering must be done by us regardless, so own-it-first is both cheapest and the
  only universally-workable option.
- **Why:** license-clean, no new infra, India-rail-agnostic, and the rating logic is the part you'll
  customize anyway. Managed engines add 2-4% revenue share for features you don't need at bootstrap.
- **Swap path:** `MeteringPort` (`ingest_event`/`get_balance`/`query_aggregation`) + `BillingPort`
  (`rate_usage`/`create_invoice`/`grant_credits`/`get_spend_rate`) → swap to Lago/OpenMeter/Stripe-
  Meters adapters at volume.

## ADR-02 — Transactional outbox
- **Default:** **Postgres `outbox_events` table + arq relay poller** (event written in the business
  transaction; relay publishes; retry/dead-letter).
- **Alternatives:** **Debezium CDC → Kafka** (lower latency, zero-poll; heavy ops — Kafka cluster);
  LISTEN/NOTIFY (no durability on missed notify).
- **Cost:** ≈ ₹0 (existing Postgres + arq); Debezium adds a Kafka cluster (₹10k+/mo + ops).
- **Why:** fixes a real dual-write data-loss bug with zero new infra; CDC is premature below ~1M
  events/day.
- **Swap path:** the relay is internal; a CDC adapter can replace the poller later without changing
  call sites (they only INSERT to the outbox).

## ADR-03 — Idempotency keys
- **Default:** **Postgres unique-constraint store** (`(tenant, idempotency_key)` UNIQUE; cached
  response replay) via an `IdempotencyPort` + FastAPI dependency.
- **Alternatives:** Redis `SET NX` + TTL (ephemeral; weaker durability for money paths).
- **Cost:** ≈ ₹0 either way; Postgres adds durability for free.
- **Why:** money/usage paths need durable, atomic dedupe; the UNIQUE constraint *is* the lock.
- **Swap path:** `IdempotencyPort` (store/lookup) — Redis adapter possible for ultra-high-volume
  non-financial endpoints.

## ADR-04 — Webhook egress (delivery + SSRF guard)
- **Default:** **keep hand-rolled** HMAC-SHA256 delivery via arq **+ build an SSRF egress guard**
  (stdlib `ipaddress`/`socket`, resolve-then-pin, block private/link-local/loopback/`169.254.169.254`,
  re-validate on redirect).
- **Alternatives:** **Svix** (self-host is enterprise-plan-only; Cloud **$490/mo** min); Convoy
  (Elastic-License, unmaintained); Hook0 (SSPL, EU-only). All overkill at bootstrap.
- **Cost:** SSRF guard ≈ ₹0 (stdlib); Svix ≈ ₹37L/yr Cloud min.
- **Why:** the hand-rolled path is adequate; the only real gap is the SSRF hole (security, not scale).
- **Swap path:** optional `WebhookPort` marks the seam to Svix if replay-UI/analytics/rotation become
  worth $490/mo.

## ADR-05 — Auth core & session hardening
- **Default:** **keep fastapi-users** (MIT, pwdlib/argon2) + **build refresh-rotation + Redis JTI
  revocation + logout-everywhere + token-version-on-reset**.
- **Alternatives:** SuperTokens (AGPL self-host), rolling your own JWT stack (don't).
- **Cost:** ≈ ₹0 (Redis already present).
- **Why:** closes the only critical auth gap (no revocation) without changing the identity model.
- **Swap path:** `AuthnPort` (ADR-06) wraps it so an external IdP can replace it later.

## ADR-06 — Enterprise identity (SSO/SCIM/MFA)
- **Default:** **`AuthnPort` + OIDC adapter (authlib, BSD)**; self-host **Authentik** (MIT, Python,
  Redis-free since 2025.10) as the enterprise IdP seam; **TOTP via `pyotp`** (MIT) behind an MFA
  toggle; **passkeys via `py_webauthn`** (BSD) later.
- **Alternatives:** **WorkOS** ($125/connection — the "SSO tax"), **Scalekit**/**Stytch**/**Kinde**
  ($125/conn class), **Clerk** (per-MAU; US-region — DPDP friction); **Keycloak** (Apache-2, heavier
  Java ops), **Zitadel** (⚠️ **AGPLv3** since Mar-2025).
- **Cost:** self-host Authentik ≈ ₹1.4-2k/mo flat (no per-connection tax, DPDP-resident); managed SSO
  ≈ ₹18k-3L+/mo at 10-50 connections.
- **Why:** enterprise SSO is a paid upsell with no customer yet → seam, don't build. Self-host
  Authentik wins on cost + India residency; managed is a per-deal swap.
- **Swap path:** `AuthnPort` (`authenticate`/`handle_callback`/`invalidate`) selects jwt|oidc|saml.

## ADR-07 — Multi-tenancy isolation (RLS + datasource bridge)
- **Default:** **shared-schema + Postgres RLS backstop** (session GUC, `FORCE ROW LEVEL SECURITY`,
  PgBouncer transaction-mode) **+ a `DatasourcePort`** (pooled shared default).
- **Alternatives (silo path):** **Supabase** (asia-south1 Mumbai ✓, ~$25/project) for India-resident
  silos; **Neon** (branching, cheap-at-scale but **US-only → DPDP friction**); **Aurora Mumbai**
  (₹10k+/mo per silo); **Citus** (DPPL/commercial for SaaS ⚠️, sharding ops).
- **Cost:** RLS ≈ ₹0 (additive); shared pool ₹500-2k/mo small, ~₹50k/mo for 500 tenants; silos ₹10k+/mo
  each (only for high-ARR tenants).
- **Why:** RLS is cheap defense-in-depth; the bridge is the scaling/compliance escape hatch built as a
  seam, not as live silos.
- **Swap path:** `DatasourcePort.get_session_factory(tenant_id)` → pooled vs silo engine; silo adapter
  added per paying tenant.

## ADR-08 — Authorization
- **Default:** **keep the in-process role hierarchy** + a thin **`AuthorizationPort`**
  (`check(subject, action, resource)`).
- **Alternatives:** **Cerbos** (Apache-2 PDP, embedded *or* sidecar — best self-host fit), **OpenFGA**
  (Apache-2, service+Postgres), **SpiceDB** (strong-consistency, $3-8k/mo managed — overkill),
  **Oso** (proprietary cloud / alpha embedded), **Permit.io**/**Topaz**.
- **Cost:** role model ≈ ₹0; Cerbos embedded ≈ ₹0 infra; OpenFGA/SpiceDB add a service tier
  (₹1.5-8k/mo at scale).
- **Why:** the role model covers ~90% of SaaS; ReBAC is a customer-triggered need. **Cerbos embedded**
  is the build-later default (cheap, YAML/CEL policies, Apache-2).
- **Swap path:** `AuthorizationPort` adapter swap → Cerbos/OpenFGA when a customer needs ABAC/ReBAC.

## ADR-09 — Background work & durable workflows
- **Default:** **keep arq** (Redis) for simple jobs; add a **`WorkflowPort`** with **DBOS Transact**
  (MIT, **Postgres-native** durable execution) as the durable default for long multi-step AI flows.
- **Alternatives:** **Temporal** (MIT, but self-host ops ≈ $26k+/mo; Cloud from $100/mo → $2k+);
  **Hatchet** (Postgres, younger, gRPC); **Restate** (serverless-centric); **Inngest** (cloud-only);
  **Prefect**.
- **Cost:** arq + DBOS ≈ ₹0 new infra (both ride Redis/Postgres); Temporal self-host is the ops-tax
  trap.
- **Why:** DBOS gives durability/retries/sagas on the Postgres you already run; Temporal is deferred
  until tenant-isolation/throughput demand a cluster.
- **Swap path:** `WorkflowPort` (start/signal/query) → DBOS adapter now, Temporal adapter later.
  Simple `enqueue()` stays the `TaskQueuePort` (arq, no vendor to swap).

## ADR-10 — Notifications (multi-channel)
- **Default:** **`NotificationPort`** generalizing `EmailPort`; ship **in-app feed (Postgres)** +
  email; **FCM** (free) for push. Per-user preferences + quiet hours table.
- **Alternatives / India:** **SMS — MSG91** (₹0.15-0.18/SMS + **DLT registration** ₹5.9k one-time,
  mandatory); **WhatsApp — Gupshup** (₹0.5-1/conversation + platform fee; **often beats SMS on
  cost+engagement in India**); **Novu** self-host (**MIT ✓**) as the orchestrator seam; Courier/Knock
  (managed, pricier).
- **Cost:** email/in-app/push ≈ ₹0; multi-channel for 1k users ≈ ₹29k/yr, 100k users ≈ ₹3.4L/yr
  (SMS/WhatsApp dominate).
- **Why:** Indian SMBs expect WhatsApp/SMS; build the port + free channels now, seam paid channels.
- **Swap path:** `NotificationPort` per-channel adapters; Novu orchestrator adapter at >50k notifs/mo.

## ADR-11 — Rate limiting & quotas
- **Default:** **Redis token-bucket** behind a **`RateLimitPort`**, keyed `tenant:plan:endpoint`.
- **Alternatives:** SlowAPI (single-node), API gateway (APISIX/Envoy — $2-5k/mo managed + ops).
- **Cost:** ≈ ₹0 (Redis present).
- **Why:** distributed, plan-tiered, no new infra; gateways are premature.
- **Swap path:** `RateLimitPort` → gateway adapter if edge enforcement is needed later.
- **AMENDED at P8 (v0.35.0) — `fastapi-limiter` dropped; the bucket is our own Lua script.** The
  original ADR named `fastapi-limiter` as the implementation. Building it surfaced two defects that
  disqualify it under the production-scale rule (real code that scales, atomic primitives — not a
  prove-it version):
  1. it is **fixed-window**, not a token bucket, so a caller gets `2 × limit` across a window
     boundary — the classic burst that makes a "60/min" limit briefly a "120/min" limit;
  2. its counter is an **`INCR` + `EXPIRE` pair**, not atomic — interleaving can leave a key with no
     TTL (a permanently-stuck limit), and it read-modify-writes under concurrency.
  The adapter therefore evaluates a **token bucket as a single Lua script** (`EVALSHA`): one atomic
  round-trip per decision, correct across any number of app instances, timed by the **Redis server
  clock** (`TIME`) so hosts cannot disagree under clock skew, with idle buckets expiring so key
  growth stays bounded. Cost is unchanged (≈ ₹0, Redis already present) and the port is unchanged,
  so the gateway swap path still holds. The `ratelimit` extra is consequently just `redis[hiredis]`.
- **Quotas — scope split, deliberate.** This phase ships the *protection* half (per-tenant, plan-tiered
  request budgets). Durable per-org usage accounting and anything billable stays in **P7 `metering`**,
  which already owns usage events, rating and invoicing; a second Postgres counter table here would be
  a duplicate source of truth for the same numbers. Plan tiers are protection ceilings, not entitlements
  to sell against.

## ADR-12 — Feature flags
- **Default:** **`FeatureFlagPort` + a Postgres flag table** (zero new infra) as the default adapter.
- **Alternatives:** **Unleash** self-host (**Apache-2 ✓**, ~₹500-2k/mo), Flagsmith (BSD), GrowthBook
  (MIT), PostHog; **LaunchDarkly** ($500-5k/mo — 20-40× costlier).
- **Cost:** DB flags ≈ ₹0; Unleash ≈ ₹500-2k/mo self-host.
- **Why:** most teams need a handful of flags — a DB table + cache suffices; Unleash is the seam when
  you want targeting/rollout UI. OpenFeature-compatible interface keeps it portable.
- **Swap path:** `FeatureFlagPort` → Unleash adapter.

## ADR-13 — Secrets management
- **Default:** **env/`.env` via pydantic-settings** (discipline) behind a **`SecretsPort`**.
- **Alternatives:** **Infisical** (**MIT core ✓**, self-host ~₹500-1.5k/mo) as the first seam;
  **HashiCorp Vault** (⚠️ **BSL 1.1**, high ops; Enterprise ₹80L+/yr); cloud secret managers
  (AWS ~₹25-50/secret/mo, GCP) for VPC-native.
- **Cost:** env ≈ ₹0; Infisical cheap; Vault is an ops/licensing trap at bootstrap.
- **Why:** `.env` is fine early; the port lets a managed store slot in without app changes.
- **Swap path:** `SecretsPort` (`get`/`get_many`) → Infisical/cloud adapter.

## ADR-14 — PII field-level encryption + KMS
- **Default:** **`EncryptionPort` + SQLAlchemy `EncryptedType`** (`cryptography`/sqlalchemy-utils),
  **app-layer envelope encryption** with a local DEK (gated `include_pii_encryption`).
- **Alternatives:** **cloud KMS** (AWS/GCP, India region, ~$1/mo + per-request) as the envelope seam;
  pgcrypto (in-DB, key-in-DB — weaker).
- **Cost:** local-key ≈ ₹0; KMS ≈ ₹100s/mo.
- **Why:** keeps a DB dump from being a breach and enables crypto-shredding (ADR-15); local key for
  early stage, KMS seam for rotation/SDF.
- **Swap path:** `EncryptionPort`/`KMSPort` → cloud-KMS adapter (India region for DPDP).

## ADR-15 — Data-subject rights (export + erasure)
- **Default:** **export** = async arq job → JSON/CSV → signed URL (reuse storage presign);
  **erasure** = **crypto-shredding** (drop the per-subject key from ADR-14) + soft-delete + weekly
  purge job; per-subject data map; all recorded in the audit log first.
- **Alternatives:** hard-delete cascade (impossible for append-only audit / external copies).
- **Cost:** ≈ ₹0 (pattern, not a product).
- **Why:** makes GDPR/DPDP erasure tractable without mutating the append-only audit log.
- **Swap path:** depends on ADR-14 (encryption) + ADR-02 (outbox for processor-notify).

## ADR-16 — API versioning & pagination
- **Default:** **URL-path versioning (`/v1`)** + **cursor/keyset pagination** (`fastapi-pagination`,
  already available) + **RFC-8594 Sunset / RFC-9745 Deprecation** headers.
- **Alternatives:** header versioning (GitHub-style — worse CDN cacheability); offset pagination
  (O(N), breaks on inserts).
- **Cost:** ≈ ₹0 (convention + existing lib).
- **Why:** URL versioning caches cleanly (Stripe's choice at scale); cursor pagination keeps DB cost
  flat as data grows.
- **Swap path:** convention; pagination helper is a thin dependency.

## ADR-17 — Search
- **Default:** **Postgres-native** — `tsvector`/GIN (full-text) + **pgvector** (vectors), both already
  in the template — behind a thin **`SearchPort`**.
- **Alternatives:** ParadeDB `pg_search` (BM25 in Postgres; AGPL ext); **Meilisearch**/**Typesense**
  (self-host ~₹5-80/mo); **Qdrant** (>100M vectors); Algolia ($500-5k/mo — avoid).
- **Cost:** Postgres-native ≈ ₹0; external engine adds a service only past ~50M vectors.
- **Why:** pgvector beats standalone Qdrant under ~50M vectors; staying in Postgres avoids new infra.
- **Swap path:** `SearchPort` → Meilisearch/Qdrant adapter at scale.

## ADR-18 — Caching
- **Default:** **Redis cache-aside + dogpile/stampede lock** (apply as a pattern; `fastapi-cache2`
  available), HTTP ETags. **No phase until a hot path is measured.**
- **Why:** premature caching is complexity without a consumer (P9).
- **Swap path:** optional `CachePort`.

## ADR-19 — Supply-chain security
- **Default:** **CycloneDX/Syft SBOM + Trivy image scan + Cosign keyless signing (GitHub OIDC) +
  SHA-pinned actions**, in both the template CI and the generated service CI; keep uv-lock + Renovate
  (Renovate auto-merge **off for majors**).
- **Alternatives:** Grype (scan), manual SBOM.
- **Cost:** ≈ ₹0 (all OSS, within CI free tier).
- **Why:** near-free, high compliance ROI (SDF audits), and it hardens the template's own
  auto-merge-of-action-bumps story.
- **Swap path:** CI-level; no app port.

## ADR-20 — Object storage
- **Default:** **Cloudflare R2** (S3-compatible, **zero egress**) as the recommended default endpoint;
  the existing `aioboto3` client/`StoragePort` is already swappable.
- **Alternatives:** AWS S3 Mumbai ($0.09/GB egress — the killer), Backblaze B2 (+CDN), MinIO self-host.
- **Cost:** egress dominates — R2 saves ~$12.75/mo at 50GB/3× and scales linearly.
- **Why:** zero-egress is decisive for a bootstrapped SaaS; no code change, just the default endpoint
  + docs.
- **Swap path:** `s3_endpoint_url` setting (already the seam).

## ADR-21 — Observability backend
- **Default:** **keep OTLP export + self-host Grafana/Tempo/Loki/Prometheus** (compose profile) +
  optional Sentry.
- **Alternatives:** **Axiom** (free 500GB/mo — great early), **SigNoz** (self/cloud), **Grafana Cloud**,
  Better Stack; Datadog (avoid — 20-40× cost).
- **Cost:** self-host ≈ infra only; Axiom free tier ≈ ₹0 for months; managed ≈ ₹45-92/mo class.
- **Why:** OTLP keeps the backend swappable; self-host or Axiom free-tier are both cheap. Solo founders
  may prefer Axiom (no ops).
- **Swap path:** `OTEL_EXPORTER_OTLP_ENDPOINT` (already the seam).

## ADR-22 — Admin
- **Default:** **keep sqladmin** (Apache-2, superuser-only, secret-redacted).
- **Alternatives:** FastAPI-Admin, Piccolo/starlette-admin (OSS); Appsmith/ToolJet self-host (ops UI);
  Retool ($95-350/mo — post-PMF).
- **Cost:** ≈ ₹0.
- **Why:** adequate to ~PMF; internal-tools platforms are a later ops-scale decision.
- **Swap path:** none needed; add role-scoped views incrementally.

## ADR-23 — Health / SLO posture
- **Default:** **extend `/readyz`** with timeout-bounded dependency checks; an `app/core/slo.py`
  SLO/error-budget definition emitting OTel metrics; graceful-degradation on best-effort paths
  (already P4); optional `pybreaker` circuit breaker on flaky externals.
- **Cost:** ≈ ₹0.
- **Why:** turns the existing probes into an operability posture; light, no new infra.
- **Swap path:** metrics flow through the existing OTel seam.

## ADR-24 — Real-time updates
- **Default:** **`RealtimePort` + FastAPI WebSocket/SSE over a Redis pub/sub backplane** (channels
  per tenant; presence via Redis-TTL; backfill from the P5 outbox).
- **Alternatives:** **Centrifugo** (BSD, self-host ~₹800/mo) / Soketi (MIT) — the managed-ish seam;
  **Ably/Pusher** (managed, ₹7.5-50k/mo — 6-10× self-host); Postgres `LISTEN/NOTIFY` (<10k conns, no
  Redis); NATS/Kafka (premature).
- **Cost:** Redis backplane ≈ existing infra; managed balloons with connections/messages.
- **Why:** rides the Redis already in the stack; outbox supplies reliable backfill; managed is a swap
  when ops/scale demand it.
- **Swap path:** `RealtimePort` → Centrifugo/Ably adapter.

## ADR-25 — Mobile / BFF backend support
- **Default:** **BUILD-NOW backend caps** — `MobileConfigPort` (version-gate), an **APNs** adapter
  (alongside FCM, behind NotificationPort), **app-attestation verify** (Play Integrity / App Attest —
  free Google/Apple APIs), PKCE + deep links. **`SyncPort` is a SEAM** (stub now).
- **Alternatives (offline-sync seam):** **PowerSync** (OSS self-host / cloud) · **ElectricSQL**
  (Postgres-native, open-source) · Replicache/Zero · WatermelonDB-sync. Custodial mobile-auth SaaS — avoid.
- **Cost:** attestation/version-gate ≈ ₹0; sync engine adds ops/cost only if offline is needed.
- **Why:** these are cheap, high-value backend capabilities; offline-sync is a heavy, app-driven
  decision deferred behind a port.
- **Swap path:** `SyncPort` → PowerSync/ElectricSQL adapter; the app itself is out-of-scope.

## ADR-26 — AI agent system-safety
- **Default:** **defense-in-depth on the existing ports, ₹0 new infra** — `AgentPolicy`
  (least-privilege capability tokens) + MCP tool signing/scoping/arg-validation + HITL approval +
  memory admission control + per-agent spend caps + immutable audit. Input/output scanning via
  **LLM-Guard** (MIT) + **Llama/Prompt-Guard** (free) + `instructor`.
- **Alternatives:** **Cerbos** (Apache-2) for agent authz + kill-switch (seam); **Lakera Guard**
  (managed injection detection, free tier→₹2-5k/mo); **SPIFFE/SPIRE** (agent mTLS identity, self-host);
  tool **sandbox** (Modal/gVisor/E2B) only if agents run untrusted code.
- **Cost:** MVP ≈ ₹0 (OSS + Postgres/Redis tables); managed scanners/sandbox optional at scale.
- **Why:** jailbroken agents are a *live* 2025-2026 threat (OWASP Agentic Top-10, MITRE ATLAS); the
  controls are cheap now and catastrophic to retrofit after an incident. **Build before production agents.**
- **Swap path:** each control is a hook on an existing port → Cerbos/Lakera/SPIFFE/sandbox adapters later.

## ADR-27 — Crypto / blockchain payments
- **Default:** **`CryptoPaymentAdapter` behind `PaymentsPort`** — self-host **BTCPay Server**
  (non-custodial, **0% fee**, MIT) for BTC/Lightning + **Beldex (BDX)** via AEON-Pay/BTCPayServer;
  **NOWPayments** (non-custodial, ~0.5%, 350+ coins) + **stablecoins USDC/USDT on Polygon/Solana**
  (fees ~$0.0004-0.002) for the practical path; idempotent on-confirmation webhook reuses `ProcessedEvent`.
- **Alternatives:** Coinbase Commerce / BitPay (custodial, 1-2%, US-domiciled — lock-in/FEMA risk);
  CoinGate (fiat payout); OpenNode (BTC/LN).
- **Cost:** BTCPay ≈ $240/yr VPS + 0%; NOWPayments 0.5% — vs Stripe/Razorpay 2-3% (5-6× cheaper
  processing, you own hosting ops).
- **Why:** crypto is ~5-6× cheaper to process and chargeback-free; BTCPay is the license-clean,
  non-custodial, self-host default; stablecoins avoid volatility. **But India VDA/FEMA/FIU rules make
  this a deliberate compliance decision (D14) — ship off-by-default.**
- **Swap path:** `crypto_provider` setting → BTCPay / NOWPayments / Coinbase adapters; `PaymentsPort`
  unchanged.

## ADR-28 — Custom domains + automated TLS
- **Default:** **`DomainPort` + Caddy on-demand TLS / CertMagic** (self-host, MIT/Apache-2) — ACME
  cert issuance at scale with an ask-endpoint that verifies domain ownership before issuing; Host-header
  → tenant resolution feeding RLS; a `domains` table + DNS TXT/CNAME verification.
- **Alternatives:** **Approximated.app** (managed, ~$20/mo + ~$0.10/domain, self-host option, low
  lock-in — the recommended *managed* seam for bootstrap); **Cloudflare for SaaS** (first 100 free then
  $0.10/domain; Enterprise $5-15k/mo at scale + high lock-in/DDoS upside); **cert-manager** (K8s-native,
  only if already on K8s).
- **Cost:** Caddy self-host ≈ infra only (marginal ~₹0/domain) + DIY renewal-uptime ops; Approximated
  ≈ breakeven ~300 domains; Cloudflare free <100 then flat per-domain.
- **Why:** Caddy gives full control + India residency (DPDP) + no per-domain fee; Approximated removes
  ops with low lock-in; Cloudflare only when DDoS/global-edge justifies the contract. Security
  (subdomain-takeover, host-header allowlist) is part of the phase, not optional.
- **Swap path:** `domain_strategy` setting → caddy|approximated|cloudflare adapters behind `DomainPort`.

## ADR-29 — Backend SEO surface
- **Default:** ship the **backend-owned** SEO primitives — dynamic per-tenant/per-domain **sitemap.xml**
  (+ sitemap-index) + **robots.txt**, **canonical/trailing-slash** middleware, a **`RedirectPort`** 301
  manager — all in-process (no new infra); a **`SeoMetadataPort`** (JSON-LD/schema.org + OG + hreflang)
  as a seam for an SSR/SSG frontend.
- **Alternatives:** `fastapi-sitemap` or a custom async route (sitemaps); Pydantic→JSON-LD serializer
  (structured data). **Prerendering** (Rendertron / Prerender.io) is **rejected/out-of-scope** —
  dynamic rendering is deprecated (Google 2025) and frontend SSR/SSG is the correct, cheaper answer.
- **Cost:** ≈ ₹0 (in-process; rides existing cache/observability for TTFB).
- **Why:** the backend is the *source of truth* for sitemaps/canonical/structured-data; the frontend
  renders. Building prerendering into the backend would be ops-heavy gold-plating for a deprecated
  technique.
- **Swap path:** `SeoMetadataPort` for structured-data; per-domain sitemaps compose with `DomainPort`
  (ADR-28).

## ADR-30 — Tax & invoicing compliance
- **Default:** **`TaxPort` + self-calc** for India (GST 18%, SAC-998361, place-of-supply, GSTIN
  validation, sequential numbering) + a **GSTN IRP e-invoicing/IRN** adapter; compliant invoice PDF via
  **WeasyPrint**.
- **Alternatives:** **Stripe Tax** (0.5%/tx, if on Stripe), **Anrok** (SaaS-native, exposure
  monitoring), **Avalara** (enterprise) — global VAT (OSS/VIES) + US nexus.
- **Cost:** self-calc ≈ ₹0 + a GSP/CA (~₹50k-1L/yr); managed 0.5-1.5% of revenue.
- **Why:** India e-invoicing is a **legal requirement at AATO ≥₹5Cr** (30-day rule) that no global
  engine fully owns — own the India path, seam managed engines for global. (D18.)
- **Swap path:** `tax_engine` setting → self-calc / stripe-tax / anrok / avalara.

## ADR-31 — Analytics & reporting
- **Default:** `AnalyticsPort` over **Postgres-native continuous aggregates / TimescaleDB** (RLS-scoped)
  + `ReportPort` (**WeasyPrint** PDF, **Polars** Excel/CSV, streaming exports, arq-scheduled).
- **Alternatives:** **DuckDB** embedded (tenant dashboards), **ClickHouse** (>1M events/day),
  **Cube**/Metabase (semantic/embedded BI), PostHog (product analytics).
- **Cost:** Postgres-native ≈ ₹0; ClickHouse/Cube add infra/ops only past real scale.
- **Why:** stay in Postgres until event volume forces an OLAP store; reports ride existing libs + jobs.
- **Swap path:** `AnalyticsPort` → ClickHouse adapter; `ReportPort` formats.

## ADR-32 — Public API / developer platform
- **Default:** **Authlib** OAuth2.1 provider (self-host, BSD) + an **inbound-webhook receiver**
  (HMAC → outbox) + **OpenAPI Generator** SDKs in CI (Apache-2) + **Scalar** dev portal (self-host).
- **Alternatives:** Authentik (managed-ish AS, ties to D3); **Speakeasy/Stainless** SDKs ($/lang);
  **ReadMe** portal; **Svix** for webhook replay-UI; Kong/APISIX gateway at scale.
- **Cost:** all-self-host ≈ ₹0; managed seams $/mo only when SDK/docs/replay become products.
- **Why:** turns the SaaS into a platform with zero new infra; managed tooling is a later differentiator.
- **Swap path:** `oauth_provider` / `developer_portal` settings; `sdk` CI step.

## ADR-33 — i18n / l10n / multi-currency / timezones
- **Default:** `LocalizationPort` + **Babel/gettext** strings, **JSONB-per-locale** content,
  **py-moneyed + Decimal** money (never float), **zoneinfo** UTC-storage timezones; **Frankfurter/ECB**
  FX; **Weblate** self-host as the translation-mgmt seam.
- **Alternatives:** Tolgee (TMS); Crowdin/Phrase (managed); translation tables (vs JSONB) for 100+ langs.
- **Cost:** ≈ ₹0 (stdlib + OSS); Weblate self-host ~₹60-120/yr VM.
- **Why:** correct money/time/locale handling is cheap to do right and catastrophic to retrofit; RTL/
  display is the frontend's.
- **Swap path:** `LocalizationPort` → Weblate adapter; FX provider setting.

## ADR-34 — File / media processing
- **Default:** `MediaProcessingPort` — presigned upload + **magic-byte validation** + **ClamAV**
  self-host malware scan (quarantine + audit) + **pyvips** image processing; **Docling/Tesseract** OCR
  (ties to RAG).
- **Alternatives:** **imgproxy** sidecar (on-the-fly resize at scale); VirusTotal (non-PII only —
  shares files); managed Cloudflare Images / video transcoding (out-of-scope).
- **Cost:** ClamAV + pyvips ≈ infra only; managed per-op at scale.
- **Why:** malware scanning is a real upload-security gate (DPDP); pyvips is ~10× Pillow at <50MB RAM;
  all self-hostable.
- **Swap path:** scan/image/doc adapters behind the port; imgproxy/managed as seams.

## ADR-35 — Tenant lifecycle & onboarding
- **Default:** a Postgres-backed **tenant state machine** (provision → trial → suspend → offboard →
  delete) + arq-driven trial expiry + **PaymentsPort proration** + DPDP **export-then-purge** offboarding
  with **1-yr audit retention**.
- **Alternatives:** SCIM for enterprise directory-sync (seam); managed onboarding tools (overkill).
- **Cost:** ≈ ₹0 (state + middleware + jobs).
- **Why:** lifecycle + compliant offboarding is core multi-tenant plumbing; composes P16 (data-rights)
  rather than reinventing it.
- **Swap path:** lifecycle service; SCIM adapter when an enterprise needs directory sync.

## ADR-36 — Code-quality, coverage & determinism stack
- **Default:** the **Python-native quality stack** — `ruff` (+`S` security/`I` import rules, have),
  `mypy --strict` (have), `vulture` (dead code), `radon`/`xenon` (complexity), **`import-linter`**
  (architecture-boundary enforcement of ports/adapters), `interrogate` (docstrings), `coverage.py`
  patch/branch gate; **test-effectiveness**: `Hypothesis` (invariants) + `Schemathesis` (OpenAPI fuzz);
  **determinism**: `pytest-randomly` + `freezegun`/`time-machine` + reproducible builds
  (`SOURCE_DATE_EPOCH` + digest-pinned image). Full spec: [CODE-QUALITY.md](CODE-QUALITY.md).
- **Alternatives:** **SonarQube** (Community = no PR/branch analysis; Developer **$15-25k/yr**),
  **Codacy/DeepSource/Qlty** (managed aggregators), **CodeQL** (free OSS-only), **Semgrep** ($40/dev/mo
  beyond OSS), **Codecov/Coveralls** (PR coverage decoration — free tier seam); **mutmut** mutation
  testing + **atheris** fuzzing (SEAM-NOW, critical modules).
- **Cost:** native stack ≈ ₹0, self-hosted, DPDP-safe, sub-1% false-positives; SonarQube is ops + $$$.
- **Why:** the native stack covers all SonarQube-Community features and more (dead-code, architecture
  boundaries, docstrings) at zero cost; SonarQube only adds PR-decoration/taint at enterprise scale.
  `import-linter` is the standout — it makes the architecture itself a CI gate.
- **Swap path:** add SonarQube/Codecov as CI steps at ≥50 devs / regulated audit — the native gates stay.

## ADR-37 — Revenue-model & packaging engine (P39)
- **Default:** **Postgres-native pricing catalog** (products·plans·features·prices·streams as **versioned
  data**) behind a **`PricingPort` + `PackagingPort`** — deterministic `resolve(tenant, plan, usage)`,
  proration, multi-stream composition into the P7 invoice. Full spec: [MONETIZATION.md](MONETIZATION.md).
- **Alternatives:** **Stripe Billing** (pricing in Stripe; 0.5-0.8% billing fee + lock-in), **Lago**
  (self-host, MIT — full billing engine), **Metronome / Orb** (usage-billing platforms, managed, rev-share).
- **Cost:** Postgres-native ≈ ₹0 + full control + auditable history; managed engines are 0.5-2% of revenue.
- **Why:** pricing is core IP and must change **without a deploy**, be **auditable/reversible**, and compose
  several streams the app already meters (P7); the port keeps the managed swap a config change at volume.
- **Swap path:** `pricing_provider` → Stripe Billing / Lago when packaging complexity or finance-team
  tooling justifies the rev-share; the `PricingPort` contract (resolve/proration) is unchanged.

## ADR-38 — AI pricing intelligence (P40)
- **Default:** a **`rules+forecast` baseline** (deterministic — usage-percentile plan-fit + EWMA/Holt
  forecast + upsell/churn heuristics) behind a **`PricingIntelligencePort`**; recommendations are
  **human-approved** and guardrailed (floors/ceilings/fairness, ties P26). Full spec: [MONETIZATION.md](MONETIZATION.md).
- **Alternatives:** an **`llm` adapter** over the P21 gateway (token-metered, structured-output via
  `instructor`) that proposes changes with rationale + confidence; an **offline elasticity model** (notebook/
  DW seam) for price-elasticity; managed pricing-optimization SaaS (e.g. usage-analytics vendors).
- **Cost:** rules baseline ≈ ₹0; the `llm` adapter costs metered tokens (its own AI cost flows through P7).
- **Why:** ship revenue-optimization value with **zero AI cost** and **no auto-apply** (legal/fairness risk);
  the decision *model* is a port, so a trained elasticity model or an LLM agent drops in without touching
  callers; dynamic/personalized pricing stays **off** until the founder enables it (D20).
- **Swap path:** `pricing_ai_provider` `rules` → `llm` (or a future ML model) — same recommend/simulate/
  evaluate contract; degrades to `rules` when the LLM is unconfigured.
