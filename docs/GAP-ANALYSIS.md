# GAP-ANALYSIS.md — current vs researched best, per subsystem

> Method: for each subsystem, *current state* (from [CURRENT-STATE.md](CURRENT-STATE.md)) vs the
> *2025-2026 researched best* (cited in [LIBRARY-DECISIONS.md](LIBRARY-DECISIONS.md)), a **severity**
> (how much the gap hurts a real platform), and a **verdict**: **BUILD-NOW** (close it), **SEAM-NOW**
> (add the port + a default/stub, build the heavy impl later), or **FINE-AS-IS** (no action — or a
> doc tweak). The discipline cuts both ways ([PRINCIPLES.md#P9](PRINCIPLES.md)): every BUILD-NOW is
> justified by real risk/revenue, and gold-plating is explicitly **rejected**. Sequenced in
> [ROADMAP.md](ROADMAP.md).

Severity: 🔴 high (security/correctness/revenue-blocking) · 🟠 medium (real, not urgent) · 🟡 low.

---

## Summary table

| # | Subsystem | Current | Researched best | Sev | Verdict |
|---|---|---|---|---|---|
| 1 | **Usage metering/billing** | subscription-only | metering→rating→invoice + credits/burn-rate | 🔴 | **BUILD-NOW** (priority) |
| 2 | **Transactional outbox** | dispatch enqueues *after* commit (dual-write race) | outbox table + relay (exactly-once publish) | 🔴 | **BUILD-NOW** |
| 3 | **Idempotency keys** | only webhook `ProcessedEvent` | `Idempotency-Key` on mutations (Postgres) | 🔴 | **BUILD-NOW** |
| 4 | **Webhook SSRF guard** | none (tenant URL → metadata/private IPs) | resolve-then-pin egress guard | 🔴 | **BUILD-NOW** |
| 5 | **Auth session hardening** | access-only JWT, no revocation | refresh rotation + Redis denylist + logout-all | 🔴 | **BUILD-NOW** |
| 6 | **Tenancy RLS backstop** | app-level `org_id` only | shared-schema + Postgres RLS (2nd layer) | 🔴 | **BUILD-NOW** |
| 7 | **Supply-chain hardening** | uv lock + Renovate | + SBOM, image scan, sign, SHA-pin actions | 🟠 | **BUILD-NOW** (CI-only, cheap) |
| 8 | **Multi-channel notifications** | email only | NotificationPort: in-app/SMS/WhatsApp/push | 🟠 | **SEAM-NOW** |
| 9 | **Per-tenant rate-limit/quotas** | none (lib present) | Redis token-bucket, plan-tiered | 🟠 | **SEAM-NOW** |
| 10 | **Durable workflows** | arq only | WorkflowPort + DBOS (Postgres-native) | 🟠 | **SEAM-NOW** |
| 11 | **Datasource bridge (silo)** | single shared DB | DatasourcePort: pooled→silo | 🟠 | **SEAM-NOW** |
| 12 | **Enterprise SSO/SCIM + MFA** | none | AuthnPort + OIDC/SAML; TOTP/passkeys | 🟠 | **SEAM-NOW** |
| 13 | **Secrets management** | env/.env | SecretsPort + Infisical/cloud seam | 🟠 | **SEAM-NOW** |
| 14 | **PII field encryption + residency** | none | EncryptionPort + KMS seam; India-region | 🟠 | **SEAM-NOW** |
| 15 | **GDPR/DPDP export + erasure** | none | export job + crypto-shredding | 🟠 | **SEAM-NOW** |
| 16 | **API versioning + pagination** | ad-hoc | URL `/v1` + cursor + Deprecation/Sunset | 🟠 | **SEAM-NOW** |
| 17 | **Authorization model** | role hierarchy | AuthorizationPort; ReBAC engine later | 🟡 | **FINE-AS-IS** + SEAM-NOW |
| 18 | **Feature flags** | none | FeatureFlagPort; DB default / Unleash | 🟡 | **SEAM-NOW** |
| 19 | **Search** | pgvector + tsvector present | Postgres-native; engine only at scale | 🟡 | **FINE-AS-IS** + thin SearchPort |
| 20 | **Caching** | Redis present, no patterns | cache-aside + dogpile lock | 🟡 | **FINE-AS-IS** |
| 21 | **Webhook delivery infra** | hand-rolled HMAC + retry | adequate; Svix only at scale | 🟡 | **FINE-AS-IS** + WebhookPort seam |
| 22 | **Object storage default** | S3-compat, AWS-default | R2 zero-egress default | 🟡 | **FINE-AS-IS** (doc the default) |
| 23 | **Observability** | OTLP + self-host stack + Sentry | cost-right; managed free-tier seam | 🟡 | **FINE-AS-IS** (doc) |
| 24 | **Admin** | sqladmin | adequate to ~PMF | 🟡 | **FINE-AS-IS** |
| 25 | **Health/SLO posture** | /healthz /readyz | + SLO doc + graceful degradation | 🟡 | **SEAM-NOW** (light) |

---

## The BUILD-NOW cases (real gaps — close them)

**1 · Usage metering/billing 🔴 (the priority).** The founder's products are usage-priced; the
template can only do flat subscriptions. This is *product-blocking*, not a nice-to-have. Build a
**Postgres-native** metering→rating→invoice core behind a `MeteringPort` + `BillingPort`:
`UsageEvent` (idempotent ingest) → `UsageOutbox` → aggregation → a simple rating engine (base +
included quota + overage) → `Invoice`, plus prepaid `CustomerWallet`/`WalletTransaction` and
burn-rate alerts; charge through the **existing `PaymentsPort`** (Razorpay/Stripe). Why Postgres-native
default, not Lago/Stripe-Meters first: it's the cheapest, license-clean, no-new-infra option and it
dodges the **India payment reality** (Razorpay has *no* metering engine; Stripe India is
invite-only/entity-gated) — you meter yourself and charge on whatever rail works. Lago/OpenMeter/Orb
become `MeteringPort` adapters when volume justifies. Depends on outbox (#2) + idempotency (#3).

**2 · Transactional outbox 🔴.** Today `dispatch()` enqueues *after* the DB commits — a crash
between commit and enqueue **silently loses the event** (the classic dual-write bug). This is a
correctness defect in the shipped webhooks, and it's the reliability backbone metering/notifications
need. Add an `outbox_events` table written **in the same transaction** as the state change; an arq
relay drains it. Rewire webhooks + audit fan-out through it.

**3 · Idempotency keys 🔴.** Only inbound *webhooks* are deduped today. Money-mutating endpoints
(checkout, credit grants, usage submission) need a Stripe-style `Idempotency-Key` so a client retry
can't double-charge. Postgres unique-constraint store (no Redis needed); replay returns the cached
response. Prereq for safe metering ingest.

**4 · Webhook SSRF egress guard 🔴.** A tenant can register a webhook URL pointing at
`169.254.169.254` (cloud metadata), `127.0.0.1`, or RFC-1918 hosts and turn your worker into an SSRF
proxy. Add a resolve-then-pin guard (block private/link-local/loopback/metadata; re-validate on
redirect; DNS-rebinding-safe). ~150 lines of stdlib `ipaddress` + `socket`; pure security hygiene.

**5 · Auth session hardening 🔴.** Access-only JWTs with no revocation means a stolen token is valid
until expiry and "log out everywhere" / "force logout on password reset" are impossible. Add
short access + rotating refresh tokens with reuse detection, a Redis JTI denylist, and a
token-version bump on reset. Redis already ships; no new infra. (MFA/SSO are separate, lower-severity
seams — see #12.)

**6 · Tenancy RLS backstop 🔴.** App-level scoping is one missing `WHERE org_id=` away from a
cross-tenant leak. Add Postgres RLS as an **independent** second layer (session GUC
`app.current_tenant` set per transaction via a SQLAlchemy hook; `FORCE ROW LEVEL SECURITY`; PgBouncer
transaction mode). Additive migration, ~1-3% overhead with indexed `org_id`. Defense-in-depth (P6).

**7 · Supply-chain hardening 🟠 → BUILD-NOW because it's nearly free.** uv-lock + Renovate is a good
base but there's no SBOM, image scan, signing, or action SHA-pinning. These are **CI-only** additions
(CycloneDX/Syft SBOM, Trivy scan, Cosign keyless signing, pinned action SHAs) with zero app code and
high compliance ROI — apply to both the template's own CI and the generated service's CI. Cheap
enough that deferring is the wrong call.

---

## The SEAM-NOW cases (add the seam now, build the heavy impl later)

Each is real but not urgent; the **port is cheap insurance** against a later refactor, and the
default adapter is the lean option:

- **8 · Notifications** — generalize `EmailPort` into a `NotificationPort` (email stays one adapter);
  ship **in-app (Postgres feed)** + keep email as the working defaults; SMS (MSG91), WhatsApp
  (Gupshup — often *cheaper & higher-engagement than SMS in India*), push (FCM, free), and a Novu
  self-host orchestrator become adapters. India **DLT registration** is an ops prerequisite for SMS.
- **9 · Rate-limit & quotas** — `fastapi-limiter` is already available; add a `RateLimitPort` with a
  Redis token-bucket keyed per tenant/plan, with quota counters tied to entitlements.
- **10 · Durable workflows** — keep arq for simple jobs; add a `WorkflowPort` for long multi-step AI
  flows (retries, human-in-the-loop, sagas). Default durable adapter = **DBOS Transact** (runs on the
  existing Postgres, no new cluster); Temporal is the heavy seam. Do this *before* shipping
  multi-step agent flows.
- **11 · Datasource bridge** — a `DatasourcePort` (pooled shared default; per-tenant silo adapter)
  so a high-value tenant can move to a dedicated DB with zero query changes. Build the silo adapter
  only when a paying tenant needs it (building silos now = gold-plating).
- **12 · Enterprise identity** — `AuthnPort` + an OIDC adapter stub now; full SAML/SCIM and the
  self-host **Authentik** seam later, when the first enterprise deal lands. Add an MFA toggle (TOTP
  via `pyotp` first; passkeys later). Building SSO/SCIM now with no enterprise customer = gold-plating;
  the seam is the cheap hedge.
- **13 · Secrets** — `SecretsPort` with the env/`.env` default (discipline) + an Infisical/cloud
  adapter seam. Don't stand up Vault now (BSL license + ops cost).
- **14 · PII encryption + residency** — `EncryptionPort` + a SQLAlchemy `EncryptedType` for sensitive
  columns, local-key default, **KMS envelope seam**; India-region hosting documented. Full field
  encryption only when handling sensitive PII / SDF classification.
- **15 · Data-subject rights** — export (async job → signed URL) + erasure via **crypto-shredding**
  (drop the per-subject key) + purge schedule. Depends on #14 (encryption) and #2 (outbox).
- **16 · API versioning + pagination** — adopt URL `/v1` + **cursor pagination** + RFC-8594/9745
  Deprecation/Sunset headers as conventions now, while there are few clients to migrate.
- **18 · Feature flags** — `FeatureFlagPort` with a DB-table default (zero new infra); Unleash
  (Apache-2, self-host) as the managed-ish adapter.
- **25 · Health/SLO** — light: an SLO/error-budget doc, extended `/readyz` dependency checks with
  timeouts, and graceful-degradation patterns on best-effort paths (mostly already true via P4).

---

## The FINE-AS-IS cases (gold-plating rejected — do not build)

- **17 · Authorization** — the role hierarchy is correct and <0.1 ms for a bootstrapped SaaS; a
  Zanzibar engine is overkill. Add only a thin `AuthorizationPort` wrapping the current RBAC so a
  Cerbos/OpenFGA adapter is a future swap. **Don't deploy an authz service now.**
- **19 · Search** — Postgres `tsvector`/GIN + `pgvector` (already present) covers full-text and
  vector search well past early scale (pgvector beats standalone Qdrant under ~50M vectors). A thin
  `SearchPort` marks the seam; **adding Meilisearch/Qdrant now is gold-plating.**
- **20 · Caching** — Redis is present; cache-aside + dogpile protection are a *pattern to apply when
  load testing shows contention*, not a subsystem to pre-build. **No phase until there's a hot path.**
- **21 · Webhook delivery infra** — hand-rolled HMAC + retry/backoff is adequate; **Svix at
  $490/mo is unjustified** below real volume/compliance need. Keep it; an optional `WebhookPort`
  marks the seam. (The SSRF guard, #4, is the *only* webhook BUILD-NOW.)
- **22 · Object storage** — already S3-compatible and swappable; the only change is **documenting
  Cloudflare R2 (zero egress) as the recommended default endpoint** — a `.env`/README tweak, not code.
- **23 · Observability** — OTLP + self-host Grafana/Tempo/Loki/Prometheus + optional Sentry is
  cost-right; keep it, document the managed free-tier seam (Axiom/SigNoz) for solo founders. No code.
- **24 · Admin** — sqladmin is adequate to ~PMF; Retool/Appsmith are a later ops-scale decision, not
  a template concern.

---

## Skeptic-review additions (STEP 5 — found on second pass, folded into phases)

A full-SaaS-checklist re-read surfaced four small but real gaps not in the first pass; each is folded
into an existing phase rather than spawning a new one (lean, P9):
- **Ingress security headers + CORS lockdown** — only egress (SSRF) and a `["*"]` CORS dev-default
  existed; HSTS/CSP/`X-Frame-Options`/`Referrer-Policy` + restrictive CORS → **folded into P2**.
- **Auth-endpoint abuse protection** — login/refresh throttling + lockout (credential-stuffing/
  brute-force) → **folded into P8** (rate-limiting applied to auth).
- **Admin-action auditing** — sqladmin mutations aren't recorded; wire admin create/edit/delete to the
  append-only audit log → small retrofit, **note on P10/audit** (do when audit + admin co-present).
- **Backup/DR + data-retention posture** — durability/PITR and per-data-class retention (DPDP) were
  implied but undocumented → **folded into P20**.
- **Org invitations** — verify the shipped `tenancy` invite/accept flow is complete; if partial,
  a small retrofit (invite token + accept endpoint + notification). Confirm during P9 (notifications).

## Net

**7 BUILD-NOW** (1 priority + reliability/security foundations) + the four folded-in skeptic
additions, **13 SEAM-NOW** (ports + lean defaults), **5 FINE-AS-IS/doc** (gold-plating consciously
rejected). Nothing manufactured: every BUILD-NOW maps to a live security hole, a correctness bug, or
the revenue-blocking metering gap; every "defer" is a deliberate lean call with a cheap seam guarding
the upgrade path.
