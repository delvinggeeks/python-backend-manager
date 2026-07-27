# COVERAGE-MATRIX.md — the 360° SaaS-subsystem checklist

> An honest, exhaustive cross-check: every subsystem a modern SaaS platform may need, mapped to its
> status here. The adversarial *no-gaps proof* (every subsystem specced or consciously out-of-scope)
> is [COMPLETENESS-AUDIT.md](COMPLETENESS-AUDIT.md). No hand-waving — if something is missing or out-of-scope, it says so. Legend:
> **✅ shipped** (in the template today) · **📋 spec'd** (a ROADMAP phase) · **🆕 adding** (this round —
> phases P27-P30, specs land as the in-flight research completes) · **➖ noted gap** (small fold or
> deliberate defer) · **⛔ out-of-scope** (frontend/business/ops, not a backend-template concern).
> Full reasoning in [GAP-ANALYSIS.md](GAP-ANALYSIS.md) / [AI-AGENTIC-STACK.md](AI-AGENTIC-STACK.md).
>
> **This file is the single home for "is it shipped?".** Other documents point here rather than
> keeping their own inventory — a fact with three homes is a fact that goes stale in two of them,
> which is exactly what happened to the rows below before this sweep.

---

## 1 · Identity & access
| Subsystem | Status | Where |
|---|---|---|
| Auth: register / login / reset / verify (JWT, argon2) | ✅ | `users` |
| Session hardening: refresh rotation, revocation, logout-all | ✅ | `users` (P3, v0.30.0) |
| MFA (TOTP) / passkeys (WebAuthn) | 📋 | P13 |
| Enterprise SSO (SAML/OIDC) · SCIM · JIT | 📋 | P13 (AuthnPort) |
| Authorization: role hierarchy → ReBAC/ABAC seam | ✅/📋 | rbac + P10 |
| API keys / service tokens | ✅ | `api_keys` |
| Mobile **app attestation** / anti-bot (Play Integrity, App Attest) | 🆕 | P28 |

## 2 · Multi-tenancy & data
| Subsystem | Status | Where |
|---|---|---|
| Tenancy (orgs/memberships, app-scoping) | ✅ | `tenancy` |
| Postgres **RLS** isolation backstop | 📋 | P4 |
| Tenant→datasource bridge / per-tenant silos | 📋 | P12 |
| Migrations (Alembic), schema discipline | ✅ | `migrations` |
| Caching (cache-aside + stampede) | ➖ | FINE-AS-IS / CachePort |
| Search: full-text + vector | ✅/📋 | pgvector + P19/P23 |
| Backup/DR + data retention posture | 📋 | P20 |

## 3 · Billing & monetization
| Subsystem | Status | Where |
|---|---|---|
| Subscriptions (Stripe + Razorpay, port) | ✅ | `billing` |
| Usage metering → rating → invoicing | 📋 | P7 |
| Entitlements / feature gating; quotas→plans | ✅/📋 | billing + P8/P18 |
| **Crypto / blockchain payments** (Beldex, stablecoins) | 🆕 | P30 (PaymentsPort adapter) |

## 4 · Communication & real-time
| Subsystem | Status | Where |
|---|---|---|
| Transactional email (SMTP/SES port) | ✅ | `email` |
| Multi-channel notifications (SMS/WhatsApp/push/in-app) | 📋 | P9 |
| **Real-time updates** (WebSocket/SSE + backplane) | 🆕 | P27 (RealtimePort) |
| Outbound webhooks (HMAC) + SSRF guard | ✅/📋 | `webhooks` + P1 |
| Inbound 3rd-party webhook receiving (generalized) | ➖ | partial (billing); fold into P5 outbox/idempotency |

## 5 · Async & reliability
| Subsystem | Status | Where |
|---|---|---|
| Background jobs (arq) + cron | ✅ | `jobs` |
| Durable workflows (DBOS/Temporal) | 📋 | P11 |
| Transactional outbox | 📋 | P5 |
| Idempotency keys | 📋 | P6 |

## 6 · AI / agentic (Wave 5)
| Subsystem | Status | Where |
|---|---|---|
| Agent frameworks (pydantic-ai/langgraph/openai-agents) | ✅ | `agents` |
| LLM gateway + per-tenant token metering | 📋 | P21 |
| Agent runtime seam + GenAI tracing | 📋 | P22 |
| RAG / retrieval (pgvector-native) | 📋 | P23 |
| Agent memory / state | 📋 | P24 |
| Evals + CI eval-gate | 📋 | P25 |
| Guardrails · structured output · prompt mgmt · MCP-tool safety | 📋 | P26 |
| **AI *system* safety: jailbreak / agent least-privilege** | 🆕 | P29 (AgentPolicy) |

## 7 · Storage & media
| Subsystem | Status | Where |
|---|---|---|
| Object storage (S3-compat; R2 zero-egress default) | ✅/📋 | `storage` + P20 |
| Media processing (image resize / **virus-scan on upload** / OCR) | 🆕 | P37 (`MediaProcessingPort`) — video transcoding stays ⛔ managed |
| CDN | ➖ | via R2/edge (config, not code) |

## 8 · Observability & ops
| Subsystem | Status | Where |
|---|---|---|
| Logs + metrics + traces (OTel three pillars) | ✅ | `observability` |
| Health / readiness probes | ✅ | `observability` |
| SLO / error-budget + graceful degradation | 📋 | P20 |
| Error tracking (Sentry seam) | ✅ | `observability` |
| GenAI/agent tracing (OTel GenAI) | 📋 | P22/P25 |
| **Frontend RUM / session replay** | ➖ | noted gap — OTel browser SDK / self-host OpenReplay; fold into P20 |
| **Synthetic / uptime monitoring** | ➖ | mostly external (Better Stack/Uptime Kuma self-host); doc in P20 |
| Admin / control panel (sqladmin) | ✅ | `admin` |
| Append-only audit log | ✅ | `audit` |

## 9 · Security & compliance
| Subsystem | Status | Where |
|---|---|---|
| Secrets management (env → Infisical/KMS seam) | 📋 | P14 |
| PII field-level encryption + KMS | 📋 | P15 |
| Data residency (India / DPDP 2023) | 📋 | P15 |
| GDPR/DPDP export + right-to-be-forgotten | 📋 | P16 |
| Webhook **SSRF egress guard** | ✅ | `webhooks` (P1, v0.19.0) |
| Ingress security headers + CORS lockdown | ✅ | base (P2, v0.20.0) |
| Supply-chain (SBOM · Trivy · Cosign · SHA-pin) | ✅ | CI (P2c, v0.27-29) |
| Rate limiting + auth-abuse protection | ✅ | `ratelimit` (P8) |
| **AI agent system-safety** (least-privilege, sandbox, HITL approval) | 🆕 | P29 |

## 10 · API & platform primitives
| Subsystem | Status | Where |
|---|---|---|
| API versioning + cursor pagination + deprecation headers | 📋 | P17 |
| Idempotency | ✅ | `idempotency` (P6, v0.33.0) |
| Feature flags | 📋 | P18 |
| **Mobile / BFF backend support** (offline-sync, version-gate, APNs, attestation) | 🆕 | P28 |
| **Real-time** | 🆕 | P27 |

## 11 · Frontend / client (a backend template provides the *support*, not the app)
| Subsystem | Status | Where |
|---|---|---|
| Mobile apps (iOS/Android/PWA) — **backend support** | 🆕 | P28 |
| Mobile apps — the app itself | ⛔ | frontend, separate repo |
| Web frontend / SPA | ⛔ | frontend |
| i18n / l10n + multi-currency + timezones (backend) | 🆕 | P36 (`LocalizationPort`) — RTL/display ⛔ frontend |

## 12 · Engineering discipline / SDLC (how it's built — full traceability)
| Subsystem | Status | Where |
|---|---|---|
| SDLC process + per-phase artifact gates (DoR/DoD) | 📋 | [SDLC.md](SDLC.md) |
| Requirements traceability matrix (req→component→test→deploy→SLO) | 📋 | [TRACEABILITY.md](TRACEABILITY.md) |
| System/component design — C4 + sequence + ER (diagrams-as-code) | 📋 | [SYSTEM-DESIGN.md](SYSTEM-DESIGN.md) |
| CI/CD + DevSecOps gates (SAST/SCA/secret/SBOM/sign/SLSA) | ✅/📋 | [CICD-PIPELINE.md](CICD-PIPELINE.md) (P2) |
| **Code quality + coverage gates** (ruff/mypy-strict/import-linter/complexity/dead-code/patch-cov) | ✅/📋 | [CODE-QUALITY.md](CODE-QUALITY.md) (P2) |
| **Deterministic / high-assurance code** (Hypothesis/Schemathesis/mutmut/pytest-randomly/reproducible builds) | ✅/📋 | [CODE-QUALITY.md](CODE-QUALITY.md) (P2) |
| Deployment topology + networking + IaC (cloud/hybrid/self-host) | 📋 | [INFRA-TOPOLOGY.md](INFRA-TOPOLOGY.md) |
| Custom MCP servers (FastMCP, OAuth2.1, per-tenant) | 📋 | [MCP-SERVERS.md](MCP-SERVERS.md) |
| Threat modeling (STRIDE per component) · ADRs · contract tests · SLOs | 📋 | SDLC.md + per-phase |

## 13 · Growth & distribution (backend surface)
| Subsystem | Status | Where |
|---|---|---|
| **Custom domains + automated TLS** (white-label, per-tenant) | 🆕 | P31 (`DomainPort`) |
| Backend SEO — **sitemap.xml / robots.txt** (per-tenant/domain) | 🆕 | P32 |
| Backend SEO — **canonical / trailing-slash / 301 redirects** | 🆕 | P32 (`RedirectPort`) |
| Backend SEO — **JSON-LD / OG / hreflang metadata API** | 🆕 | P32 (`SeoMetadataPort`, seam) |
| Programmatic-SEO data serving + thin-content audit | 🆕 | P32 (seam) |
| TTFB / Core-Web-Vitals (backend contribution) | ✅/📋 | caching P20 + observability |
| **Frontend SEO** (rendering, meta-injection, content, CWV-frontend, prerendering) | ⛔ | frontend repo (SSR/SSG) — Google deprecated dynamic rendering 2025 |
| Product analytics (PostHog) | ➖ | seam via FeatureFlagPort/events; mostly external |
| A/B testing | 📋 | P18 (flags) + P26 (prompts) |
| CRM · helpdesk · marketing site · status page | ⛔ | external SaaS / ops |

---

## This round's additions (P27-P30 — ✅ specs now written: ROADMAP Wave 6 + ADR-24..27 + D14-D16)

| Phase | Subsystem | Default (cost-effective / self-host) | Verdict |
|---|---|---|---|
| **P27** | Real-time updates | `RealtimePort` — FastAPI WS/SSE + **Redis pub/sub backplane** (self-host); Centrifugo seam; managed Ably/Pusher seam | SEAM-NOW |
| **P28** | Mobile / BFF support | version-gate `/config` endpoint, **APNs** adapter (NotificationPort), **app-attestation verify** (Play Integrity/App Attest) BUILD-NOW; offline-sync engine (ElectricSQL/PowerSync) SEAM-NOW | mixed |
| **P29** | AI agent **system safety** | `AgentPolicy` — least-privilege scoped tools, **HITL approval** for destructive actions, tool sandbox + egress control, per-agent spend/rate caps, immutable action audit (hardens P22/P26 + AuthorizationPort) | BUILD-NOW (security) |
| **P30** | Crypto / blockchain payments | `PaymentsPort` crypto adapter — self-host **BTCPay Server** (non-custodial) default; **Beldex (BDX)** + stablecoins (USDC/USDT); idempotent on-confirmation webhook (reuse `ProcessedEvent`); **India VDA tax/FIU compliance = DECISIONS-NEEDED** | SEAM-NOW + ⚠ compliance |

## Gaps from earlier rounds — now closed in Wave 8 (P33-P38)
- **Tax & invoicing** (GST/e-invoicing/VAT) → **P33**. · **Analytics & reporting** (metrics + PDF/Excel)
  → **P34**. · **Public API / OAuth-provider / SDKs / inbound-webhooks** → **P35**. · **i18n/l10n +
  multi-currency + timezones** → **P36**. · **Media processing** (virus-scan/image/OCR) → **P37**. ·
  **Tenant lifecycle + onboarding/offboarding** → **P38**.

## Still deliberately out-of-scope (frontend / external — not gaps)
- **Frontend RUM + session replay** → OTel browser SDK / self-host OpenReplay (frontend-adjacent; doc'd in P20).
- **Synthetic / uptime monitoring** → external (Uptime Kuma self-host); a doc, not template code.
- **Video transcoding** → managed (Cloudflare Stream / MediaConvert) seam, not a build (P37).
- **Frontend apps themselves** (web/mobile/desktop), marketing site, content/SEO copy → separate repos.

See [COMPLETENESS-AUDIT.md](COMPLETENESS-AUDIT.md) §L for the full out-of-scope list with reasoning.

**Verdict:** with Wave 5 (AI) + P27-P30 (real-time, mobile, agent-safety, crypto) + the small folds
above, the backend platform is **360° across every subsystem a modern SaaS needs** — robust where it
matters (security, isolation, billing, reliability, AI safety), lean where it doesn't (no media
pipeline / RUM cluster / multi-agent framework before a real need), every choice cost-justified and
swappable behind a port.
