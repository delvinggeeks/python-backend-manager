# TRACEABILITY.md — the end-to-end traceability matrix

> The living, in-repo **Requirements Traceability Matrix (RTM)**: a bidirectional thread from
> *requirement → design/component → code → test → CI gate → deploy → observability/SLO*, so no
> requirement, component, or pipeline stage is ever orphaned. Process in [SDLC.md](SDLC.md); diagrams
> in [SYSTEM-DESIGN.md](SYSTEM-DESIGN.md); gates in [CICD-PIPELINE.md](CICD-PIPELINE.md). The matrix is
> **machine-checked** — a CI script fails the build on any broken link (see §4).

---

## 1. Why a *living* RTM (not a spreadsheet)

A spreadsheet rots the day after it's written. Here the RTM is **YAML in the repo** (`.meta/rtm/PNN.yml`),
edited in the same PR as the code, with IDs referenced from tests and code comments, and rendered to
Markdown tables for review. Bidirectional means you can answer both "which test covers REQ-P7-002?" and
"what requirement does `app/metering/ports.py` satisfy?" — and CI proves every link resolves.

---

## 2. RTM schema (per phase: `.meta/rtm/PNN.yml`)

```
phase: P07_usage_metering
requirements:
  REQ-P7-001:
    title: "Idempotent usage-event ingest, metered per tenant"
    acceptance: "Given a tenant + Idempotency-Key, When the same event is POSTed twice,
                 Then it is recorded once and rated once."
    priority: P0
    components: [MeteringPort, UsageEvent, UsageOutbox]
    tests: [test_metering.py::test_ingest_idempotent]
    threat: [REQ-P7-001 in .meta/threat/P07.yml]
    ci_gate: "generate (metering)"
    deploy: "adds usage_events + usage_outbox tables (alembic); no new infra"
    slo: "ingest p99 < 50ms; 0 double-bills"
components:
  MeteringPort:
    layer: port
    code: "src/app/metering/ports.py"
    requirements: [REQ-P7-001]
    tests: [test_metering.py::test_port_contract]   # Pact-style contract test
```

**Columns (the trace):** `requirement → component(port/adapter) → code path → test(s) → threat-model
ref → CI capability row → deploy/infra delta → SLO/observability signal`. Every row must have all
eight; CI fails otherwise.

---

## 3. Master matrix — phase → port → CI row → tests → deploy → SLO

The phase-level backbone (the finer component rows live in each `PNN.yml`). This is the "you can't miss
a phase or its pipeline" view. *(Sev/verdict in [GAP-ANALYSIS.md](GAP-ANALYSIS.md); P-specs in
[ROADMAP.md](ROADMAP.md).)*

| Phase | Port / component | CI capability row | Primary tests | Deploy / infra delta | SLO / observability signal |
|---|---|---|---|---|---|
| P1 | webhook SSRF guard | `webhooks` | egress block (v4/v6/redirect/rebind) | none | blocked-egress count |
| P2 | CI + ingress hardening | framework rows | header-presence; SBOM/scan/sign | pinned actions; signed image | scan findings = 0 high |
| P3 | refresh/revocation (AuthnPort base) | `users` | rotation, reuse-detect, logout-all (no-Redis) | Redis denylist (optional) | auth p99; revoked-token rejects |
| P4 | Postgres RLS | `tenancy`/`*_full` | cross-tenant-leak blocked (app-role) | RLS policies migration; PgBouncer txn | 0 cross-tenant reads |
| P5 | transactional outbox | `webhooks` | crash-between-commit-and-publish safe | `outbox_events` table + relay | outbox lag; lost-events = 0 |
| P6 | IdempotencyPort | `idempotency` | duplicate key → one effect | `idempotency_keys` table | dup-replay rate |
| P7 ⭐ | MeteringPort + BillingPort | `metering`/`metering_full` | ingest idempotent, rate, invoice, wallet | usage/outbox/wallet/invoice tables | meter accuracy; 0 double-bill |
| P8 | RateLimitPort | `ratelimit` | per-tenant limit; fail-open no-Redis; auth-throttle | Redis | 429 rate; abuse blocked |
| P9 | NotificationPort | `notifications`/`_full` | email+in-app send; channel no-op unconfigured | prefs/feed tables | delivery rate per channel |
| P10 | AuthorizationPort | `authz` | role checks via port (no behavior change) | none | authz decision latency |
| P11 | WorkflowPort (DBOS) | `workflows` | durable run survives crash | DBOS tables on Postgres | workflow success/retry |
| P12 | DatasourcePort | `tenancy` + unit | pooled default; silo routing (mock) | per-tenant engine registry | datasource route correctness |
| P13 | AuthnPort SSO + MFA | `sso`,`mfa` | OIDC flow (mock IdP); TOTP enroll/verify | IdP config; no live IdP | SSO login success |
| P14 | SecretsPort | `secrets` | env adapter byte-identical | secret-manager seam | secret-fetch errors |
| P15 | EncryptionPort + KMS | `pii_encryption` | encrypt/decrypt round-trip; off=plaintext | KMS seam; India region | crypto errors = 0 |
| P16 | data-subject rights | `data_rights` | export bundle; crypto-shred erasure | purge job | export/erase SLA |
| P17 | API versioning + cursor pagination | `api` | `/v1`; cursor; Sunset/Deprecation headers | none | deprecation adoption |
| P18 | FeatureFlagPort | `feature_flags` | flag eval via port (cached) | flags table | flag-eval latency |
| P19 | SearchPort | `search` | pgvector + FTS via port (fake embedder) | GIN/HNSW indexes | search recall/latency |
| P20 | SLO/health + cost defaults | existing rows | readyz timeout-bounded | R2 default; backup/retention doc | /readyz accuracy; error budget |
| P21 ⭐ | LLMPort + token→metering | `llm_gateway`/`_full` | usage→meter; budget 429; caching (mock provider) | Redis cache | token cost/tenant; cache hit% |
| P22 | AgentRuntime + GenAI tracing | framework rows | runner per framework; GenAI spans (mock LLM) | none | agent span coverage; cost/run |
| P23 | RetrievalPort (RAG) | `rag` | ingest→hybrid-retrieve (fake embedder) | pgvector indexes | retrieval recall |
| P24 | MemoryPort | `memory` | thread + semantic recall; tenant-isolated; TTL | thread/fact tables | memory hit; erasure |
| P25 | evals + GenAI eval-gate | `evals` leg | DeepEval thresholds block regression | tracing backend (off) | eval pass-rate gate |
| P26 | GuardrailPort + PromptPort + MCPToolPort | `guardrails`,`mcp` | injection/PII scan; per-tenant tool scope; SSRF | prompt registry table | guardrail block rate |
| P27 | RealtimePort | `realtime` | WS subscribe/publish/presence/backfill (mock Redis) | Redis pub/sub | connection/msg rate |
| P28 | Mobile/BFF | `mobile` | version-gate; attestation verify (mock) | APNs config | attestation pass rate |
| P29 ⭐ | AgentPolicy (system-safety) | `agent_safety` | capability-deny; arg-inject reject; spend-cap; approval | none (hooks) | denied-action count; spend caps |
| P30 | PaymentsPort crypto adapter | `crypto_payments` | sig verify; idempotent on-confirmation (mock chain) | off-by-default; ⚠ D14 | confirmation dedupe |
| MCP-srv | MCP server seam | `mcp_server` | Inspector schema; per-tenant filter; HITL/role-gate | stateless HTTP `/mcp` | per-tenant isolation |
| P31 | DomainPort + auto-TLS | `custom_domains` | Host→tenant; allowlist-reject; verify (mock DNS/ACME) | `domains` table; Caddy on-demand TLS | cert-issue success; takeover alerts |
| P32 | SEO (sitemap/robots/canonical/RedirectPort/SeoMetadataPort) | `seo` | sitemap/robots well-formed; canonical 301; JSON-LD schema-valid | none (in-process) | crawl coverage; TTFB |
| P33 | TaxPort + InvoiceGenerator | `tax` | GST calc by place-of-supply; GSTIN-validate; gap-free numbering (mock IRP) | none | tax accuracy; invoice compliance |
| P34 | AnalyticsPort + ReportPort | `analytics` | RLS aggregate; streaming export; PDF render | continuous-aggregate views | query latency; export size |
| P35 | OAuth provider + inbound-webhook + SDK/portal | `dev_platform` | auth-code+PKCE; webhook HMAC→outbox; SDK-gen smoke | `oauth_clients`/`app_registry` tables | token issue/revoke; webhook dedupe |
| P36 | LocalizationPort + money/tz | `localization` | locale resolve+fallback; currency-safe math; tz convert | none | locale coverage |
| P37 | MediaProcessingPort | `media` | magic-byte reject; ClamAV quarantine; resize (mocked) | ClamAV/pyvips workers | infected-blocked; scan latency |
| P38 | tenant lifecycle state machine | `tenant_lifecycle` | state transitions; suspend-blocks-writes; offboard-purge+retain-audit | status enum + logs | lifecycle correctness; erasure SLA |

Every cell's "primary tests" run with **no live infra** (mocked provider / unreachable Redis / sqlite),
per the P3 matrix — so the trace is verifiable in CI, not aspirational.

---

## 4. The CI gate that keeps it honest

`scripts/check_rtm_coverage.py` (runs in the template CI and is generated into each service) fails the
build when, for any phase:
- a requirement has **no** component, **no** test, **no** CI row, **no** deploy note, or **no** SLO;
- a referenced **test path doesn't exist** or a referenced **code path doesn't exist**;
- a **threat** in `.meta/threat/PNN.yml` has no mitigating test;
- a **port** has no contract test.

It also renders `.meta/reports/rtm.md` (the human view) on every PR. Result: a requirement physically
**cannot** merge without its full trace — completeness is enforced, not promised.

---

## 5. How a phase appends to the matrix

A phase PR adds exactly one `.meta/rtm/PNN.yml` + `.meta/threat/PNN.yml` + its `docs/phases/PNN/`
design/runbook, adds its `generate (capability)` row to `ci.yml`, and updates the master-matrix row
here. The [SDLC.md](SDLC.md) Definition-of-Done blocks the squash-merge until all of that is green. The
matrix therefore grows monotonically and stays consistent with the code at every tag.
