# ROADMAP.md — the ordered phase plan to a finished platform

> Each phase is **one `feat:` PR**, gate-enforced, dependency-ordered, independently shippable, and
> **inherits [PRINCIPLES.md](PRINCIPLES.md)** (esp. the P3 edge-validation matrix — *byte-identity
> OFF · ALONE minimal-deps leg · `--vcs-ref HEAD` clean tree · tests under no infra* — which is NOT
> restated per phase; assume it). Choices are justified in
> [LIBRARY-DECISIONS.md](LIBRARY-DECISIONS.md); gaps in [GAP-ANALYSIS.md](GAP-ANALYSIS.md). Standing
> module-build rules apply (branch → gate behind toggle → validate matrix+module → squash-merge with
> the exact `feat:` title → CD tags the version). Versions below are *suggested* next tags from the
> current **v0.18.0**; CD derives the real bump from the commit.

Per-phase fields: **Scope · Toggle/Port · Implies/Deps · Definition-of-done · CI rows + special
validation**. "CI rows" are additions to the `generate (capability)` matrix (the gate aggregates
them automatically — no branch-protection change).

> **Every phase also obeys the full SDLC discipline** in [SDLC.md](SDLC.md): it ships its per-phase
> artifact set (requirements + RTM rows, C4/sequence/ER-delta diagrams, STRIDE threat model, test
> pyramid + port contract tests, DevSecOps gates, IaC/deploy note, runbook, SLO) and appends to the
> [TRACEABILITY.md](TRACEABILITY.md) matrix — the Definition-of-Done blocks the squash-merge until that
> trace is complete and CI-verified. The scope lines below are the *deltas*; the discipline is inherited.

---

## Wave 0 — near-free hardening (no behavior change; fast, low-risk)

### P1 · Webhook SSRF egress guard  🔴
- **Scope:** resolve-then-pin egress guard on outbound webhook delivery; block
  private/link-local/loopback/`169.254.169.254`; re-validate on redirect; DNS-rebinding-safe.
  Retrofit of the shipped `webhooks` module.
- **Toggle/Port:** none new (part of `include_webhooks`); internal `egress_guard` helper.
- **Implies/Deps:** webhooks. None.
- **DoD:** delivery to a private/metadata IP is refused + logged; public IPs unaffected; unit tests
  cover IPv4/IPv6/redirect/rebind cases.
- **CI:** reuse `webhooks` / `audit_webhooks` rows; add a guard unit test (no network).

### P2 · Supply-chain + ingress hardening  🟠 (CI + a small middleware)
- **Scope:** (a) **supply-chain** — SBOM (CycloneDX/Syft), Trivy image scan, Cosign keyless signing
  (GitHub OIDC), SHA-pinned actions — in **both** the template's own CI and the **generated**
  service's `.github/workflows`; Renovate auto-merge off for majors. (b) **ingress hardening** — a
  security-headers middleware (HSTS, `X-Content-Type-Options`, `X-Frame-Options`/frame-ancestors CSP,
  `Referrer-Policy`) and tightened CORS defaults (the current `allow_origins=["*"]` is a dev default
  to lock down). *(Skeptic-review addition: the template had egress SSRF on the roadmap but no
  ingress header posture.)*
- **Toggle/Port:** none new (CI surface + a core middleware that's safe-by-default).
- **Implies/Deps:** none. The generated-workflow render-gate already validates the YAML.
- **DoD:** template CI emits a signed image + SBOM artifact; generated CI renders valid scan/sign
  jobs; security headers present on responses; CORS default is restrictive with a documented opt-in.
- **CI:** existing framework rows (render-gate covers the new workflow YAML) + a header-presence test.

---

## Wave 1 — security & reliability foundations

### P3 · Auth session hardening  🔴
- **Scope:** short access + **rotating refresh tokens** (reuse detection), **Redis JTI denylist**,
  logout-everywhere, token-version bump on password reset. Retrofit of `users`.
- **Toggle/Port:** part of `users`; lays the groundwork for `AuthnPort` (P13).
- **Implies/Deps:** users. Uses Redis when present — **denylist degrades gracefully (best-effort,
  P4-style) with no Redis** so the ALONE/no-infra leg passes.
- **DoD:** refresh rotates + detects reuse; revoked token rejected; logout-all works; no-Redis path
  still authenticates (denylist no-ops with a logged warning).
- **CI:** `users` row asserts rotation + revocation under **unreachable Redis**.

### P4 · Tenancy RLS backstop  🔴
- **Scope:** Postgres RLS as a second isolation layer — session GUC `app.current_tenant` set per
  transaction via a SQLAlchemy hook; `CREATE POLICY` + `FORCE ROW LEVEL SECURITY` on tenant tables;
  PgBouncer transaction-mode note. Retrofit of `tenancy`.
- **Toggle/Port:** `include_rls` (default true with tenancy) — or always-on with tenancy.
- **Implies/Deps:** tenancy. Additive Alembic migration.
- **DoD:** a query that *omits* the app-level `WHERE org_id` still cannot read another tenant's rows;
  tests run as a **low-privilege app role** (not superuser); RLS round-trips in the migration.
- **CI:** `tenancy` / `*_full` rows + a **cross-tenant-leak test** proving RLS blocks; sqlite test
  path tolerates RLS-absent (Postgres-only enforcement documented).

---

## Wave 2 — reliability spine (prerequisites for metering)

### P5 · Transactional outbox  🔴
- **Scope:** `outbox_events` table written **in the business transaction**; an arq relay drains it
  with retry/dead-letter. Rewire webhook + audit fan-out through it. Fixes the shipped dual-write race.
- **Toggle/Port:** internal (no vendor port); ships with db + worker.
- **Implies/Deps:** db; worker (relay). Pairs with webhooks/audit.
- **DoD:** an event enqueued in the same txn is never lost if the process dies before publish; relay
  is idempotent; dedup via `(source,event_id)`.
- **CI:** `webhooks` row asserts outbox publish + replay-safety under no infra (fake pool).

### P6 · Idempotency keys  🔴
- **Scope:** `Idempotency-Key` header support on mutating endpoints; Postgres unique-constraint store;
  cached-response replay; `IdempotencyPort` + FastAPI dependency.
- **Toggle/Port:** `include_idempotency` (default true); `IdempotencyPort`.
- **Implies/Deps:** db.
- **DoD:** a duplicate key returns the original response with no second effect; TTL/cleanup job;
  concurrent duplicates serialize safely.
- **CI:** `idempotency` row (ALONE, db) — duplicate POST → one effect.

---

## Wave 3 — the priority: usage billing

### P7 · Usage metering + rating + invoicing  🔴 ⭐
- **Scope:** Postgres-native **`MeteringPort` + `BillingPort`**: `UsageEvent` (idempotent ingest via
  P6) → `UsageOutbox` (via P5) → aggregation → rating engine (base + included quota + overage) →
  `Invoice`; prepaid `CustomerWallet`/`WalletTransaction`; burn-rate alerts (via notifications); charge
  through the existing `PaymentsPort`. Managed adapters (Lago/OpenMeter/Stripe-Meters) as stubs behind
  the port. Extends/retrofits `billing`.
- **Toggle/Port:** `include_metering` (implies billing); `MeteringPort`, `BillingPort`,
  `metering_provider` setting.
- **Implies/Deps:** billing (→ tenancy/users/db/payments); **P5 outbox + P6 idempotency** (hard deps).
- **DoD:** end-to-end ingest→rate→invoice→charge works on sqlite/no-infra with the default adapter;
  idempotent ingest; wallet debit is atomic; an invoice syncs to a `PaymentsPort` charge; burn-rate
  alert fires. **India note documented**: meter in-app, charge on Razorpay/Stripe.
- **CI:** `metering` (ALONE: metering+billing minimal) + `metering_full` (+webhooks +audit +
  notifications) rows; alembic round-trip of the new tables.

---

## Wave 4 — platform seams (value-ordered; mostly independent)

### P8 · Per-tenant rate limiting & quotas  🟠
- **Scope:** `RateLimitPort` (Redis token-bucket via `fastapi-limiter`), keyed `tenant:plan:endpoint`;
  Postgres quota counters tied to entitlements (when billing present).
- **Toggle/Port:** `include_ratelimit` (implies cache); `RateLimitPort`.
- **Implies/Deps:** cache. Optional tie-in to billing entitlements.
- **DoD:** per-tenant limits enforced; plan tiers map to limits; degrades open if Redis down (P4);
  **auth endpoints get abuse protection** (login/refresh throttling + lockout on repeated failures —
  *skeptic-review addition: credential-stuffing/brute-force defense belongs with rate-limiting*).
- **CI:** `ratelimit` row (ALONE, cache) under unreachable Redis (fails-open path); an auth-throttle
  test.

### P9 · Notifications (multi-channel)  🟠
- **Scope:** `NotificationPort` generalizing `EmailPort` (email becomes one adapter); **in-app feed
  (Postgres)** + email defaults; SMS (MSG91), WhatsApp (Gupshup), push (FCM) adapters; per-user
  preferences + quiet hours; Novu orchestrator as a seam. Retrofit of `email`.
- **Toggle/Port:** `include_notifications` (generalizes email); `NotificationPort`,
  `notification_provider` per channel.
- **Implies/Deps:** email; db (in-app feed + prefs). DLT registration is an ops doc.
- **DoD:** email + in-app send via the port; SMS/WhatsApp/push adapters no-op-when-unconfigured;
  preference/opt-out honored; quiet hours respected.
- **CI:** `notifications` (ALONE: email+db) + `notifications_full` (+users) rows; no live providers.

### P10 · Authorization port (ReBAC seam)  🟡
- **Scope:** thin `AuthorizationPort` (`check(subject, action, resource)`) wrapping the current role
  hierarchy as the default adapter; a Cerbos adapter **stub**. Retrofit of `rbac`.
- **Toggle/Port:** `authz_engine` setting (default `rbac`); `AuthorizationPort`.
- **Implies/Deps:** rbac.
- **DoD:** existing role checks route through the port unchanged; stub raises NotImplemented; no
  behavior change (byte-identity of role decisions).
- **CI:** `authz` row (ALONE) — role checks via the port.

### P11 · Durable workflows  🟠
- **Scope:** `WorkflowPort` for long multi-step flows; arq adapter (simple) + **DBOS Transact**
  adapter (Postgres-native durable). Keep `enqueue()` as the simple `TaskQueuePort`.
- **Toggle/Port:** `include_workflows` (implies jobs + db); `WorkflowPort`, `workflow_engine` setting.
- **Implies/Deps:** jobs (worker) + db.
- **DoD:** a multi-step workflow survives a mid-run crash (durable adapter); arq adapter covers the
  simple case; no-infra test uses the in-Postgres durable path on sqlite or a fake.
- **CI:** `workflows` row.

### P12 · Datasource bridge (tenant→DB)  🟠
- **Scope:** `DatasourcePort` (`get_session_factory(tenant_id)`) with a pooled-shared default and a
  silo adapter (per-tenant engine registry). Pairs with P4 RLS. Retrofit of `tenancy`/`db.session`.
- **Toggle/Port:** `DatasourcePort` (pooled default); silo via config registry.
- **Implies/Deps:** tenancy. Silo adapter unit-tested with a mock (no second DB in CI).
- **DoD:** all queries go through the port; pooled default unchanged; silo routing covered by a
  mock-engine test; no query-site changes.
- **CI:** `tenancy` rows (pooled) + a datasource-port unit test.

### P13 · Enterprise identity (SSO/MFA)  🟠
- **Scope:** `AuthnPort` + an OIDC adapter (authlib); SAML/SCIM stubs; self-host Authentik seam doc;
  **TOTP MFA** (`pyotp`) behind a toggle; passkeys later. Builds on P3.
- **Toggle/Port:** `include_sso` (OIDC), `include_mfa` (TOTP); `AuthnPort`, `authn_provider` setting.
- **Implies/Deps:** users (+ P3).
- **DoD:** OIDC login flow works against a mock IdP; TOTP enroll+verify; default jwt path unchanged;
  no-infra tests use a fake OIDC discovery doc.
- **CI:** `sso` + `mfa` rows (ALONE, users) — no live IdP.

### P14 · Secrets provider seam  🟠
- **Scope:** `SecretsPort` with the env/`.env` default adapter + an Infisical adapter stub.
- **Toggle/Port:** `secrets_provider` setting (default `env`); `SecretsPort`.
- **Implies/Deps:** none.
- **DoD:** `get_settings()` sources through the port; env adapter byte-identical to today; stub
  documented.
- **CI:** `secrets` row (ALONE) — env adapter.

### P15 · PII field-level encryption  🟠
- **Scope:** `EncryptionPort` + SQLAlchemy `EncryptedType`; envelope encryption with a local DEK
  default + a KMS adapter seam; apply to sensitive columns when on.
- **Toggle/Port:** `include_pii_encryption`; `EncryptionPort`/`KMSPort`.
- **Implies/Deps:** db. India-region hosting documented.
- **DoD:** encrypt/decrypt round-trips transparently via the ORM; off = plaintext byte-identical;
  KMS adapter stubbed; latency noted.
- **CI:** `pii_encryption` row — round-trip on sqlite.

### P16 · Data-subject rights (export + erasure)  🟠
- **Scope:** export (async arq job → signed URL) + **crypto-shredding** erasure (drop the P15 key) +
  soft-delete + weekly purge; per-subject data map; audit-logged.
- **Toggle/Port:** `include_data_rights`.
- **Implies/Deps:** db; **P15 (encryption) + P5 (outbox)**.
- **DoD:** export produces a complete per-subject bundle; erasure renders PII unreadable without
  mutating the append-only audit log; actions audited first.
- **CI:** `data_rights` row.

### P17 · API versioning & pagination conventions  🟠
- **Scope:** URL `/v1` versioning, cursor/keyset pagination helper (`fastapi-pagination`),
  RFC-8594/9745 Deprecation/Sunset middleware.
- **Toggle/Port:** `include_api_conventions` (or fold into the `api` extra).
- **Implies/Deps:** none.
- **DoD:** versioned mount + cursor params + deprecation headers on an example route; docs.
- **CI:** `api` row.

### P18 · Feature flags  🟡
- **Scope:** `FeatureFlagPort` with a Postgres flag-table default adapter (OpenFeature-shaped); Unleash
  adapter seam.
- **Toggle/Port:** `include_feature_flags`; `FeatureFlagPort`, `flags_provider` setting.
- **Implies/Deps:** db.
- **DoD:** flag eval via the port (cached); DB adapter default; Unleash stub.
- **CI:** `feature_flags` row.

### P19 · Search port  🟡
- **Scope:** thin `SearchPort` over Postgres-native full-text (`tsvector`/GIN) + `pgvector`; external
  engine (Meilisearch/Qdrant) as a documented seam, **not built**.
- **Toggle/Port:** `include_search`; `SearchPort`, `search_backend` setting.
- **Implies/Deps:** db.
- **DoD:** full-text + vector query via the port on Postgres; external adapter stubbed.
- **CI:** `search` row.

### P20 · Cost & ops defaults  🟡 (mostly docs + light code)
- **Scope:** document **Cloudflare R2 (zero-egress)** as the recommended storage default endpoint;
  document the managed-observability free-tier seam (Axiom/SigNoz); add the **SLO/error-budget** doc +
  extended `/readyz` timeout-bounded checks + graceful-degradation/circuit-breaker on flaky externals.
- **Toggle/Port:** none new (uses existing storage/observability seams).
- **Implies/Deps:** none.
- **DoD:** README/`.env.example` recommend R2; `/readyz` checks are timeout-bounded; SLO doc shipped;
  a **backup/DR + data-retention posture** doc (PITR/snapshot guidance + per-data-class retention
  windows tied to DPDP) — *skeptic-review addition: durability/retention was implied but unstated*.
- **CI:** existing rows; readyz test asserts timeout behavior.

---

## Wave 5 — AI-native application layer (the usage-priced AI product surface)

Specs in [AI-AGENTIC-STACK.md](AI-AGENTIC-STACK.md). Inherits the P3 matrix; **no-infra tests mock
LLM calls** (no live provider keys). The throughline: the gateway/engines are seams, the **token
cost-metering is the core** (ties to P7).

### P21 · LLM gateway + per-tenant token metering  🔴 ⭐
- **Scope:** `LLMPort` (LiteLLM **SDK in-process** default) with provider routing + fallback,
  **prompt caching** + **semantic caching** (Redis), and a **token-usage → `MeteringPort`** bridge
  with per-tenant **budget caps (429 on exceed)**. Charge via the existing `PaymentsPort`.
- **Toggle/Port:** `include_llm_gateway` (implies `llm`); `LLMPort`, `llm_gateway` setting.
- **Implies/Deps:** llm; **P7 metering** (for billing tie-in — degrades to log-only when metering
  absent); cache (Redis) for caching.
- **DoD:** per-call usage parsed (input/output/cache tokens → cost) and metered per tenant; a tenant
  over budget gets 429; caching demonstrably reduces tokens; works against a **mocked provider** (no
  live key).
- **CI:** `llm_gateway` row (ALONE: llm+cache) + `llm_gateway_full` (+billing metering) under a fake
  provider + unreachable Redis (caching degrades open).

### P22 · Agent runtime seam + GenAI tracing  🟠
- **Scope:** a thin **`AgentRuntime`/`AgentPort`** wrapping the framework toggles (pydantic-ai default;
  retrofit `example_agent.py`); emit **OTel GenAI spans** (tokens/cost/model/tool calls) via the
  existing observability seam; per-call cost + usage-cap; long runs wrap **`WorkflowPort` (P11)**.
- **Toggle/Port:** uses `agent_framework` + `include_observability`; `AgentPort`.
- **Implies/Deps:** an agent framework extra; observability (for GenAI spans, gated).
- **DoD:** the `/agent` route runs via the port for each framework; GenAI spans emitted when
  observability on; no behavior change when off (byte-identity); durable variant checkpoints via P11.
- **CI:** framework matrix rows assert the runner + (when observability) span attributes, mocked LLM.

### P23 · RAG / RetrievalPort  🟠
- **Scope:** build the `rag` module — `RetrievalPort` with a **pgvector-native** hybrid search
  (tsvector + vector, RRF) + ingestion (`pypdf` + `semantic-text-splitter`) + `EmbeddingPort`
  (`text-embedding-3-small` default) + optional `RerankPort`; Qdrant adapter seam.
- **Toggle/Port:** `include_rag` (implies db + pgvector); `RetrievalPort`/`EmbeddingPort`/`RerankPort`.
- **Implies/Deps:** db (pgvector). DPDP-cascade delete by collection.
- **DoD:** ingest→chunk→embed→store→hybrid-retrieve works on sqlite/pgvector test path with a mocked
  embedder; rerank optional; tenant-scoped + erasable.
- **CI:** `rag` row (db) with a fake embedding function.

### P24 · Agent memory / MemoryPort  🟠
- **Scope:** `MemoryPort` — Postgres `threads`/`messages`/`memory_facts` (+ pgvector long-term),
  RLS-isolated, **DPDP TTL + audit + erasure**; composes with `RetrievalPort` (P23) + `WorkflowPort`
  (P11); Mem0/Zep adapter seams.
- **Toggle/Port:** `include_memory` (implies db); `MemoryPort`, `memory_provider` setting.
- **Implies/Deps:** db; pairs with P23/P11; erasure ties to P16.
- **DoD:** add/fetch thread + semantic fact retrieval via the port; tenant-isolated; TTL/erase works;
  mocked embedder for no-infra.
- **CI:** `memory` row (db).

### P25 · LLM evals + eval-gate + tracing backend  🔴
- **Scope:** a **DeepEval** harness (`evals/`) + a CI **eval-gate** (accuracy/safety/cost-delta
  thresholds, LLM-as-judge) wired into the `generate (capability)` gate; a Langfuse/Phoenix
  tracing-backend adapter behind the OTLP seam (off by default).
- **Toggle/Port:** `include_evals` extra; tracing backend via `OTEL_*` endpoint.
- **Implies/Deps:** an agent framework (evals target model calls). Uses a **mocked/cheap judge** in CI.
- **DoD:** `just evals` runs locally; the CI gate blocks a regression beyond threshold; baselines
  stored in-repo; no live provider needed (recorded fixtures / mock judge).
- **CI:** an `evals` leg on framework rows (skips `none`); thresholds gate merge.

### P26 · Guardrails + prompts + MCP tool safety  🟠
- **Scope:** `GuardrailPort` (`instructor` + LLM-Guard PII/injection + Guardrails AI; PII redaction
  ties to P15); `PromptPort` (Postgres prompt registry + versioning + A/B via `FeatureFlagPort` P18);
  `MCPToolPort` (per-tenant tool scoping + **SSRF guard reused from P1** + sandboxed-execution seam).
- **Toggle/Port:** `include_guardrails`, `include_prompts`; extends `include_mcp`.
- **Implies/Deps:** llm; P1 (SSRF), P15 (PII), P18 (flags) where present.
- **DoD:** injection/PII scan on the prompt boundary; schema-enforced output; prompt fetch-by-label;
  MCP tools scoped per tenant + URL-fetch tools SSRF-guarded; all no-op-safe when unconfigured.
- **CI:** `guardrails` + `mcp` rows (mocked LLM; SSRF unit test).

---

## Wave 6 — client surface, agent-safety & alternative payments

The 360°-coverage additions ([COVERAGE-MATRIX.md](COVERAGE-MATRIX.md)). Each inherits the P3 matrix;
cross-wave deps noted. **P29 is security-critical and gates production agents.**

### P27 · Real-time updates  🟠
- **Scope:** `RealtimePort` + a **FastAPI WebSocket/SSE** default adapter over a **Redis pub/sub
  backplane** (channels `tenant:{id}:{channel}`); presence (Redis-TTL); **missed-message backfill
  from the transactional outbox (P5)**; per-tenant channel **authorization via `AuthorizationPort`
  (P10)**; connection/message rate-limit via `RateLimitPort` (P8); graceful degrade when Redis down.
- **Toggle/Port:** `include_realtime` (implies cache); `RealtimePort`, `realtime_provider` setting.
- **Implies/Deps:** cache (Redis backplane); db + **P5 outbox** (reliable backfill).
- **Alternatives/seam:** self-host **Centrifugo** (BSD) / Soketi; managed **Ably/Pusher** (6-10× cost).
- **DoD:** WS connect/subscribe/publish/presence/backfill; JWT auth + per-channel authz; backfill from
  outbox; rate-limit present; **mocked Redis** in the no-infra test (degrades to single-worker).
- **CI:** `realtime` row (ALONE: cache) with a fake WS client + mocked pub/sub.

### P28 · Mobile / BFF backend support  🟠
- **Scope (BUILD-NOW backend caps):** a **version-gate `/config`** endpoint (force-upgrade /
  min-version), an **APNs** adapter alongside FCM (extends `NotificationPort`, P9), **app-attestation
  verify** (Play Integrity / Apple App Attest — block tampered clients), OAuth2 **PKCE** for native +
  **deep/universal-link** resolution. **SEAM-NOW:** an offline-first **`SyncPort`** (delta sync +
  change-tokens). **Out-of-scope:** the app itself.
- **Toggle/Port:** `include_mobile` (+ `mobile_capabilities`); `MobileConfigPort`, `AttestationPort`,
  `SyncPort` (stub).
- **Implies/Deps:** users (auth) + notifications (push). Attestation uses free Google/Apple APIs.
- **Alternatives (sync seam):** **PowerSync** (OSS self-host) / **ElectricSQL** (Postgres-native) /
  Replicache — built only when a mobile service needs offline.
- **DoD:** `/config` returns version policy; attestation token verified (fail-open + logged on first
  pass); APNs adapter no-ops unconfigured; PKCE flow; `SyncPort` stub documented. Mocked attestation
  in CI.
- **CI:** `mobile` row (users) — version-gate + attestation verify (mocked), no live Apple/Google.

### P29 · AI agent **system-safety** (jailbreak / least-privilege)  🔴 ⭐ (gates production agents)
- **Scope:** defense-in-depth against a jailbroken / prompt-injected agent **acting on the system**
  (the "lethal trifecta": private-data access + untrusted content + exfiltration), layered onto the
  existing ports — **no new infra**. Six BUILD-NOW controls:
  1. **`AgentPolicy` (least-privilege):** agent identity distinct from the user; per-tenant scoped
     **capability tokens** (allow/deny tool lists, short TTL); **no raw DB/secret access**;
     kill-switch. (seam: AuthnPort + AuthorizationPort/P10)
  2. **MCP tool hardening:** per-tenant tool scoping, **tool-description signature** (anti-poisoning),
     **strict arg-schema validation**, output PII redaction, **SSRF egress reuse (P1)**. (seam: MCPToolPort/P26)
  3. **Human-in-the-loop approval** for destructive/irreversible/high-value actions (plan-then-execute,
     2FA on HIGH/CRITICAL, logged). (seam: AuthorizationPort + AuditPort + NotificationPort)
  4. **Memory admission control** (anti-MINJA): trust-scored ingestion, consistency check, TTL,
     causal attribution. (seam: MemoryPort/P24)
  5. **Per-agent spend caps + runaway-loop detection** (hard 429 at budget; anomaly pause at ≥3×
     baseline). (seam: MeteringPort/P21 + RateLimitPort/P8)
  6. **Immutable agent-action audit** (every tool call + cost + risk + injection-score; OTel GenAI
     span). (seam: AuditPort)
  Mapped to **OWASP Agentic Top-10 (2025)** + **MITRE ATLAS**.
- **Toggle/Port:** ships with the agent capability; `AgentPolicy` + the control hooks on existing ports.
- **Implies/Deps:** an agent framework; P10 (authz), P26 (MCP/guardrails), P1 (SSRF), P21 (spend),
  audit. **Must land before any production agent with tools/memory** (P22+).
- **DoD:** an agent cannot call a tool outside its capability list; a destructive action requires
  approval; a poisoned tool signature is rejected; a budget-exceeded agent gets 429 + pause; every
  action is audited; threat-sim tests (injection, memory-poison, runaway) pass — all against a
  **mocked LLM**, ₹0 infra.
- **CI:** `agent_safety` row — capability-deny, arg-injection-reject, spend-cap, approval-gate tests.

### P30 · Crypto / blockchain payments  🟠 (+ ⚠ India compliance gate)
- **Scope:** a **`CryptoPaymentAdapter` behind the existing `PaymentsPort`** (Option A — crypto is
  just another method). Default **self-host BTCPay Server** (non-custodial, **0% fee**, MIT) for
  BTC/Lightning + **Beldex (BDX)** via its AEON-Pay/BTCPayServer integration; **NOWPayments** +
  **stablecoins (USDC/USDT on Polygon/Solana)** as the practical low-fee path; **idempotent
  on-confirmation webhook reuses `ProcessedEvent`** (`(provider,invoice_id,status)` dedupe on N
  confirmations).
- **Toggle/Port:** `include_crypto_payments`; `PaymentsPort` crypto adapter, `crypto_provider` setting.
- **Implies/Deps:** billing/payments. Web3.py for EVM stablecoins; httpx for BTCPay Greenfield / Beldex RPC.
- **⚠ COMPLIANCE GATE (DECISIONS-NEEDED D14):** India VDA law — **30% tax + 1% TDS**, **mandatory
  FIU-IND registration** for VDA service providers (PMLA), **FEMA** does *not* recognize crypto as
  forex (an Indian exporter accepting crypto loses FIRC → GST export benefit), and **privacy coins
  (Beldex) draw AML scrutiny**. Ship the adapter **off by default** with the compliance caveats
  documented; enabling it for Indian flows needs counsel.
- **DoD:** checkout → on-confirmation idempotent webhook → `Subscription`/invoice sync via PaymentsPort;
  BTCPay + a stablecoin adapter; signature-verified, replay-safe; no-op-when-unconfigured; the
  compliance caveat surfaced in README + DECISIONS-NEEDED. Mocked chain/webhook in CI.
- **CI:** `crypto_payments` row (billing) — signature verify + idempotent confirmation, mocked.

---

## Wave 7 — growth & distribution (custom domains, backend SEO)

The acquisition/distribution surface (vs the production pipeline, which is covered). Scope discipline:
the backend owns infrastructure + data + seams; **the frontend/marketing site owns rendering, content,
on-page meta, and Core-Web-Vitals-frontend** (out of scope — separate repo).

### P31 · Custom domains + automated TLS  🟠 (white-label + the SEO enabler)
- **Scope:** `DomainPort` — per-tenant **subdomains** (`*.app.com`) **and customer custom domains**
  (`app.theirbrand.com` via CNAME); a `domains` table (tenant, domain, verified, primary, strategy);
  **Host-header → tenant** resolution feeding the tenant-context middleware + RLS (P4); **DNS TXT/CNAME
  domain verification**; **automated certificate issuance at scale**. Default adapter = **Caddy
  on-demand TLS / CertMagic** (self-host, ACME, ask-endpoint validates ownership before issuing);
  managed seams = **Approximated.app** / **Cloudflare for SaaS**.
- **Toggle/Port:** `include_custom_domains`; `DomainPort`, `domain_strategy` setting (caddy|approximated|cloudflare).
- **Implies/Deps:** tenancy + **P4 RLS** (Host→tenant→RLS); ingress (Caddy/edge). DPDP: self-host
  Caddy in an India DC for residency; managed = cross-border (D2/D17).
- **Security (BUILD-NOW within the phase):** **host-header allowlist** (`TrustedHostMiddleware` against
  verified domains — reject unknown Host), **dangling-DNS / subdomain-takeover** prevention
  (require DNS-record removal before decommission, token rotation, periodic resolver audit, cert
  revocation on takeover) — ties to P6/P29.
- **DoD:** subdomain + custom-domain routing → correct tenant (RLS-scoped); DNS verification flow;
  cert auto-issued/renewed via the default adapter (mocked ACME in CI); unknown Host rejected; per-tenant
  isolation proven. No live ACME in CI.
- **CI:** `custom_domains` row — Host→tenant resolution + allowlist-reject + verification-state tests (mocked DNS/ACME).

### P32 · Backend SEO surface  🟡
- **Scope (BUILD-NOW in-phase):** dynamic **`sitemap.xml`** (sitemap-index for >50k URLs, lastmod,
  **per-tenant / per-domain** sitemaps, cached/regenerated) + **`robots.txt`** (per-tenant/per-env);
  **canonical-URL + trailing-slash** normalization middleware; **301 redirect** manager (`RedirectPort`
  + table, audited). **SEAM-NOW:** a **`SeoMetadataPort`** serving **JSON-LD (schema.org)** + Open
  Graph + **hreflang/i18n** metadata for an SSR/SSG frontend to embed; pSEO **thin/duplicate-content
  audit** (reporting, not a gate). **OUT-OF-SCOPE:** prerendering / dynamic-rendering for crawlers —
  Google deprecated dynamic rendering (2025) and AI crawlers don't run JS, so the *frontend SSR/SSG*
  owns rendering; the backend just serves the data + structured-data *source*.
- **Toggle/Port:** `include_seo` (sitemap/robots/canonical/redirects); `SeoMetadataPort` (structured
  data, seam); `seo_trailing_slash_mode` setting.
- **Implies/Deps:** db; **pairs with P31** (per-custom-domain sitemaps + canonical). TTFB/Core-Web-Vitals
  backend contribution already covered (caching P20 + observability).
- **DoD:** valid sitemap-index + per-tenant sitemap; robots.txt per env; canonical/trailing-slash
  enforced (301); redirect manager round-trips; JSON-LD endpoint returns valid schema.org; prerendering
  documented as frontend-owned. Validated with golden-file sitemap/robots + schema validation.
- **CI:** `seo` row — sitemap/robots well-formedness + canonical-redirect + JSON-LD schema-valid tests.

---

## Wave 8 — platform completeness (the final no-gaps sweep)

The remaining genuine platform subsystems found by an adversarial audit ([COMPLETENESS-AUDIT.md](COMPLETENESS-AUDIT.md)).

### P33 · Tax & invoicing compliance  🔴 (India e-invoicing is a legal requirement)
- **Scope:** a **`TaxPort`** behind the billing layer (calculate tax for a sale; validate tax-ids;
  generate compliant invoice). Default = **self-calc** (India **GST 18%**, SAC-998361, place-of-supply
  B2B/B2C, **GSTIN validation**, sequential numbering, retention) + a **GSTN IRP e-invoicing/IRN**
  adapter (**mandatory at AATO ≥₹5Cr**, 30-day rule); compliant **invoice PDF** (WeasyPrint). Managed
  seams: **Stripe Tax / Anrok / Avalara**; global **VAT (OSS/VIES)** + **US nexus**.
- **Toggle/Port:** `include_tax` (implies billing); `TaxPort`, `tax_engine` setting; `InvoiceGenerator`.
- **Implies/Deps:** billing/payments. India e-invoicing flagged in **D18**.
- **DoD:** correct GST per place-of-supply; GSTIN validation; sequential gap-free invoice numbers;
  compliant PDF; IRN adapter stubbed/mocked; VAT/nexus via the managed seam. Golden-invoice + tax-calc tests.
- **CI:** `tax` row (billing) — GST calc + GSTIN-validate + invoice-numbering (mocked IRP).

### P34 · Analytics & reporting  🟠
- **Scope:** `AnalyticsPort` (per-tenant metrics/time-series — **Postgres-native continuous aggregates /
  TimescaleDB**, RLS-isolated) + `ReportPort` (**WeasyPrint** PDF, **Polars** Excel/CSV, **streaming
  exports**, **scheduled reports** via arq). Event rollup tables. Seams: DuckDB embedded dashboards,
  Metabase/Cube embedded, ClickHouse (>1M events/day).
- **Toggle/Port:** `include_analytics`, `include_reports`; `AnalyticsPort`, `ReportPort`.
- **Implies/Deps:** db (+ cache); jobs (scheduled reports). DPDP: data-classification on event schema.
- **DoD:** time-series query + dimensional breakdown (RLS-scoped); streaming CSV/XLSX export (memory-safe);
  scheduled PDF via worker; mocked data in CI.
- **CI:** `analytics` row — aggregate query + streaming export + PDF render.

### P35 · Public API / developer platform  🟠
- **Scope:** be an **OAuth 2.1 / OIDC provider** (Authlib + `oauth_clients`/consent tables;
  `/oauth/authorize|token|revoke`) so third-party apps act on behalf of users (the *provider* side of
  `AuthnPort`); a generalized **inbound-webhook receiver** (HMAC verify → outbox P5) + **app registry /
  marketplace** seam; **SDK generation in CI** (OpenAPI Generator default; Speakeasy seam); a
  self-host **Scalar** developer portal; `ConnectorPort` for native connectors.
- **Toggle/Port:** `include_oauth_provider`, `include_inbound_webhooks`, `include_sdk_generation`,
  `developer_portal` setting.
- **Implies/Deps:** users (OAuth); db (app registry); P17/P8/P7 (versioning/quota/metering); P1/P5 (webhooks).
- **DoD:** authorization-code+PKCE flow (mock client); token issue/revoke; inbound webhook HMAC-verify→outbox;
  app registry CRUD + revoke; SDK generated in CI; Scalar docs served. No live third-party in CI.
- **CI:** `dev_platform` row — OAuth flow + inbound-webhook verify + SDK-gen smoke.

### P36 · i18n / l10n / multi-currency / timezones  🟠
- **Scope:** `LocalizationPort` — backend string i18n (**Babel/gettext**, ICU plurals), locale
  resolution middleware (Accept-Language → user → org → default), **JSONB-per-locale** translatable
  content; **multi-currency** money type (**py-moneyed + Decimal**, never float), per-region pricing,
  FX-rate source (Frankfurter/ECB); **timezones** (UTC storage + `zoneinfo` per-user). Translation-mgmt
  seam = **Weblate** self-host. Out-of-scope: RTL/number-date display (frontend).
- **Toggle/Port:** `include_localization`; `LocalizationPort`, money type, locale middleware.
- **Implies/Deps:** none core (db for content/prefs). Ties to billing/tax (currency) + SEO (hreflang P32).
- **DoD:** locale resolves + fallback chain; translated email/error strings; JSONB content served per
  locale; money math currency-safe; UTC stored + tz-converted on read. Babel extract/compile in CI.
- **CI:** `localization` row — locale-resolution + money-currency-safety + tz-conversion tests.

### P37 · File / media processing  🟠 (malware scan = security gate)
- **Scope:** `MediaProcessingPort` on top of object storage — **presigned direct-to-S3 upload** +
  **magic-byte/content-type validation** + size limits; **malware/virus scanning** (**ClamAV**
  self-host default; VirusTotal seam) with **quarantine + audit** (a real security gate); **image
  processing** (**pyvips** in-process / **imgproxy** sidecar — resize/convert/optimize); **document
  OCR** (**Docling**/Tesseract → ties to RAG P23). Video transcoding = out-of-scope (managed seam).
- **Toggle/Port:** `include_media_processing` (implies storage); `MediaProcessingPort` + scan/image/doc adapters.
- **Implies/Deps:** storage; jobs (post-upload worker). Malware scan ties to P29 (untrusted input) + audit.
- **DoD:** presign + magic-byte reject of spoofed types; ClamAV scan → quarantine + audit on infected
  (mock clamd in CI); pyvips resize/convert; OCR extract (mock). No live AV/network in CI.
- **CI:** `media` row (storage) — validation-reject + scan-quarantine + resize (mocked).

### P38 · Tenant lifecycle & onboarding automation  🟠
- **Scope:** a tenant **state machine** (`PENDING_PAYMENT → ACTIVE → TRIAL → SUSPENDED → OFFBOARDED →
  DELETED`) + provisioning (create org → seed defaults → first-admin invite), **trial** management +
  expiry (arq scheduler), **plan up/downgrade + proration** (via PaymentsPort/Stripe), **suspension/
  reactivation** (status middleware, data preserved), and **DPDP offboarding** (export-window → purge,
  cascade delete + S3 cleanup, **1-yr audit-log retention**) — composes P16 (data-rights) + audit.
- **Toggle/Port:** `include_tenant_lifecycle` (implies tenancy + billing); lifecycle service + state enum.
- **Implies/Deps:** tenancy; billing (trial/plan/proration); **P16** (export/erasure); audit.
- **DoD:** state transitions audited; trial-expiry job; up/downgrade proration via the payments port;
  suspend blocks writes/allows reads; offboard exports-then-purges with retained audit trail. Mocked clock/Stripe.
- **CI:** `tenant_lifecycle` row — state-machine transitions + suspend-blocks-writes + offboard-purge tests.

---

## Deliberately deferred (seams exist; do NOT build until a real trigger)

Listed so "not building these" is a *recorded decision*, not an omission ([PRINCIPLES.md#P9](PRINCIPLES.md)):

| Item | Seam already planned | Build trigger |
|---|---|---|
| Cerbos/OpenFGA **live** authz engine | `AuthorizationPort` (P10) | a customer needs ABAC/ReBAC |
| Temporal **cluster** | `WorkflowPort` (P11) | throughput/tenant-isolation beyond DBOS |
| Per-tenant **DB silos** (live) | `DatasourcePort` (P12) | a high-ARR tenant demands isolation |
| **Authentik/WorkOS** live SSO | `AuthnPort` (P13) | first enterprise SSO deal |
| **Vault/Infisical** live | `SecretsPort` (P14) | audit/rotation requirement |
| **Svix** webhook infra | `WebhookPort` seam | replay-UI/rotation worth $490/mo |
| **Meilisearch/Qdrant** | `SearchPort` (P19) | >~50M vectors / FTS scale |
| **Caching** subsystem | optional `CachePort` | a measured hot path |
| **Debezium/Kafka** CDC | outbox relay (P5) | >~1M events/day |
| Managed metering (Lago/Orb) | `MeteringPort` (P7) | volume justifies 2-4% revenue share |
| **LiteLLM proxy / Portkey** gateway | `LLMPort` (P21) | >100 tenants need central governance |
| Dedicated **vector DB** (Qdrant/Weaviate) | `RetrievalPort` (P23) | >~50M vectors / filter-heavy |
| Managed **memory** (Mem0/Zep) | `MemoryPort` (P24) | entity-extraction/temporal reasoning is a revenue lever |
| Self-host **Langfuse** cluster | OTLP GenAI seam (P25) | data-residency mandate / team scale |
| **LangGraph/OpenAI-Agents** as default | `AgentPort` (P22) | a branching/HITL or GPT-committed product |
| Managed real-time (Ably/Pusher) · Centrifugo | `RealtimePort` (P27) | scale/ops beyond FastAPI-WS+Redis |
| Offline-first **sync engine** (PowerSync/ElectricSQL) | `SyncPort` (P28) | a mobile service needs offline |
| Tool **sandbox** infra (Modal/gVisor/E2B) | MCPToolPort (P26/P29) | agents execute untrusted code |
| Custodial crypto (Coinbase/BitPay) · INR off-ramp | `PaymentsPort` crypto (P30) | a deliberate compliance decision (D14) |
| Managed custom-domains (Cloudflare-for-SaaS/Approximated) | `DomainPort` (P31) | scale/ops beyond self-host Caddy, or DDoS need |
| **Frontend SEO**: rendering, meta-injection, content, Core-Web-Vitals-frontend, prerendering | frontend repo (SSR/SSG) | **out of scope** — not a backend-template concern |
| pSEO content generation (the pages themselves) | `SeoMetadataPort` data (P32) | a content/product decision |
| Managed tax (Stripe Tax/Anrok/Avalara) | `TaxPort` (P33) | global VAT/nexus complexity or scale |
| ClickHouse / Cube / Metabase analytics | `AnalyticsPort` (P34) | >1M events/day or formal BI contract |
| Speakeasy SDKs · ReadMe portal · Svix · Authentik | P35 seams | SDK-as-product / enterprise SSO / replay-UI need |
| Weblate translation server · managed FX | `LocalizationPort` (P36) | translators join / high FX volume |
| imgproxy sidecar · Docling OCR · video transcoding | `MediaProcessingPort` (P37) | resize >1M/day · RAG docs · video (managed) |
| SCIM provisioning | tenant-lifecycle (P38) + P13 | enterprise directory-sync deal |

---

## Dependency graph (ship order)

```
P1 SSRF ─┐
P2 CI ───┤ (independent quick wins)
P3 Auth ─┤
P4 RLS ──┘
            P5 Outbox ──┐
            P6 Idem ────┴──► P7 METERING ⭐
P8 RateLimit · P9 Notify · P10 Authz · P11 Workflows · P12 Datasource ·
P13 SSO/MFA · P14 Secrets · P15 PIIEnc ──► P16 DataRights · P17 APIv ·
P18 Flags · P19 Search · P20 Cost/Ops      (P16 also needs P5)

Wave 5 (AI):  P21 LLM-gateway+metering ⭐ (needs P7) ─┐
              P22 AgentRuntime+GenAI-tracing (needs P11 for durable)
              P23 RAG ─► P24 Memory (also needs P11)
              P25 Evals+tracing · P26 Guardrails+prompts+MCP (needs P1/P15/P18)
Wave 6:       P27 Real-time (needs P5+cache) · P28 Mobile/BFF (needs users+P9)
              P29 Agent-safety ⭐ (needs P10/P26/P1/P21 — GATES production agents)
              P30 Crypto payments (needs billing; ⚠ D14 compliance gate)
Wave 7:       P31 Custom domains+auto-TLS (needs tenancy+P4) ─► P32 Backend SEO (per-domain sitemaps)
Wave 8:       P33 Tax+invoicing ⚖ (needs billing; ⚠ D18 India e-invoicing) · P34 Analytics+reporting
              P35 Public-API/dev-platform (OAuth provider; needs users) · P36 i18n/l10n/currency/tz
              P37 Media processing (malware scan; needs storage) · P38 Tenant lifecycle (needs tenancy+billing+P16)
```

Waves 0-1 are parallel-safe; Wave 2 gates Wave 3; Wave 4 is value-ordered and largely independent
(only P16 has an intra-wave dep on P15+P5). **Wave 5 (AI)** rides the platform: P21 needs P7
metering, P22's durable path needs P11, P24 builds on P23, and P26 reuses P1/P15/P18 — but each is
still one shippable `feat:` PR once its deps land. Each phase is its own `feat:` PR + version bump;
arm squash auto-merge per the standing rules.

---

## STEP 5 — skeptic self-review (what I checked)

- **Any SaaS stage missing?** Re-ran a full-platform checklist against the phases. Four small gaps
  found and folded in (ingress security headers + CORS → P2; auth abuse protection → P8; admin-action
  audit → P10 note; backup/DR + retention → P20), plus an org-invitations completeness check (P9).
  Nothing else material uncovered: signup/verify/reset (shipped), multi-currency (Razorpay/INR via the
  payments port), i18n of notifications (a future `NotificationPort` adapter concern, deferred), and
  status-page/incident-comms (ops, out of template scope). **The AI-native application layer**
  (LLM gateway + token metering, RAG, agent memory, evals/tracing, guardrails/MCP-safety) was the
  one substantial omission of the first spec pass — now covered as **Wave 5 (P21-P26)** with its own
  research doc [AI-AGENTIC-STACK.md](AI-AGENTIC-STACK.md).
- **Any STEP-2 requirement uncovered?** All 8 subsystem clusters + all 13 cross-cutting items map to a
  phase or a FINE-AS-IS verdict (cross-checked against [GAP-ANALYSIS.md](GAP-ANALYSIS.md)).
- **Any phase not independently validatable?** Each has a concrete CI row or render-gate/test, and the
  inherited P3 matrix. Dependency-ordered phases (P7 after P5+P6; P16 after P15+P5) are *sequenced*,
  not co-dependent — each still ships as one PR once its deps have landed.
- **Any choice not cost-justified?** Every ADR in [LIBRARY-DECISIONS.md](LIBRARY-DECISIONS.md) carries
  small+large cost, license, and lock-in; defaults are the cheapest credible self-hostable option, with
  the managed swap recorded. The genuinely consequential calls are escalated to
  [DECISIONS-NEEDED.md](DECISIONS-NEEDED.md) rather than guessed.

Verdict: spec is internally consistent, fully covers the brief, and is buildable phase-by-phase on the
existing gate. **No building begins until the founder reviews this set** (esp. D1-D3).
