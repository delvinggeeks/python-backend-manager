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
