# COVERAGE-MATRIX.md — the 360° SaaS-subsystem checklist

> An honest, exhaustive cross-check: every subsystem a modern SaaS platform may need, mapped to its
> status here. No hand-waving — if something is missing or out-of-scope, it says so. Legend:
> **✅ shipped** (in the template today) · **📋 spec'd** (a ROADMAP phase) · **🆕 adding** (this round —
> phases P27-P30, specs land as the in-flight research completes) · **➖ noted gap** (small fold or
> deliberate defer) · **⛔ out-of-scope** (frontend/business/ops, not a backend-template concern).
> Full reasoning in [GAP-ANALYSIS.md](GAP-ANALYSIS.md) / [AI-AGENTIC-STACK.md](AI-AGENTIC-STACK.md).

---

## 1 · Identity & access
| Subsystem | Status | Where |
|---|---|---|
| Auth: register / login / reset / verify (JWT, argon2) | ✅ | `users` |
| Session hardening: refresh rotation, revocation, logout-all | 📋 | P3 |
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
| Media processing (image resize / transcode / **virus-scan on upload**) | ➖ | noted gap — fold a `storage` processing seam into P20/P23 |
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
| Webhook **SSRF egress guard** | 📋 | P1 |
| Ingress security headers + CORS lockdown | 📋 | P2 |
| Supply-chain (SBOM · Trivy · Cosign · SHA-pin) | 📋 | P2 |
| Rate limiting + auth-abuse protection | 📋 | P8 |
| **AI agent system-safety** (least-privilege, sandbox, HITL approval) | 🆕 | P29 |

## 10 · API & platform primitives
| Subsystem | Status | Where |
|---|---|---|
| API versioning + cursor pagination + deprecation headers | 📋 | P17 |
| Idempotency | 📋 | P6 |
| Feature flags | 📋 | P18 |
| **Mobile / BFF backend support** (offline-sync, version-gate, APNs, attestation) | 🆕 | P28 |
| **Real-time** | 🆕 | P27 |

## 11 · Frontend / client (a backend template provides the *support*, not the app)
| Subsystem | Status | Where |
|---|---|---|
| Mobile apps (iOS/Android/PWA) — **backend support** | 🆕 | P28 |
| Mobile apps — the app itself | ⛔ | frontend, separate repo |
| Web frontend / SPA | ⛔ | frontend |
| i18n / l10n + multi-currency | ➖ | deferred; multi-currency via payments port |

## 12 · Growth / business (mostly external SaaS, not template code)
| Subsystem | Status | Where |
|---|---|---|
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

## Honest gaps remaining after P27-P30 (small folds / deliberate defers)
- **Media processing** (upload virus-scan, image/video transform) → a `storage` processing seam (fold into P20/P23). Real but low-urgency.
- **Frontend RUM + session replay** → OTel browser SDK / self-host OpenReplay; documented in P20 (frontend-adjacent).
- **Synthetic / uptime monitoring** → mostly external (Uptime Kuma self-host); a doc, not template code.
- **Generalized inbound-webhook receiving** → the billing webhook pattern + idempotency (P6) generalizes; fold a helper into P5/P6.
- **i18n/l10n + multi-currency** → deferred; multi-currency rides the payments port; notification i18n is a NotificationPort concern.
- **Frontend apps themselves** (web/mobile/desktop) → out of scope for a backend template (separate repos consume this backend).

**Verdict:** with Wave 5 (AI) + P27-P30 (real-time, mobile, agent-safety, crypto) + the small folds
above, the backend platform is **360° across every subsystem a modern SaaS needs** — robust where it
matters (security, isolation, billing, reliability, AI safety), lean where it doesn't (no media
pipeline / RUM cluster / multi-agent framework before a real need), every choice cost-justified and
swappable behind a port.
