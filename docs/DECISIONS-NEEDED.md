# DECISIONS-NEEDED.md — founder input before/whilst building

> Genuine judgement calls the spec should **not** guess. Each has a **recommended default** (so the
> build can proceed if you don't object) plus *what it changes*. Most are "confirm the default";
> the first three are genuinely consequential. Nothing here blocks Wave 0-2 (security/reliability
> foundations) — those proceed on the recommended defaults; these mostly shape Wave 3-4 adapters.

---

## D1 · Usage-billing engine + the India payment reality  ⭐ (highest impact)
**Question:** for the priority metering subsystem (P7), which is the default engine, and do you
accept the India rail constraint?
- **Recommended default:** **build the metering→rating→invoice core in Postgres** (own it),
  charging through the existing `PaymentsPort`. Seam Lago/OpenMeter/Stripe-Meters/Orb as
  `MeteringPort` adapters later.
- **Why:** **Razorpay has no usage-metering engine and Stripe India is invite-only/entity-gated**, so
  the metering must live in our app regardless of provider. Owning it is also the cheapest (no 2-4%
  revenue share) and license-clean. **Lago is AGPLv3** (+ commercial dual-license) — running it
  *unmodified as a separate service you call over HTTP* does **not** force you to open-source your
  app, but it's a question worth a deliberate yes/no; **OpenMeter is Apache-2** if you want a
  self-host engine without the AGPL conversation.
- **Affects:** P7 default adapter, the rating data model, and whether we ever stand up Lago/OpenMeter.
- **Need from you:** ✅ confirm "own-it-in-Postgres first", **or** name a managed engine to target.

## D2 · Hosting & data-residency baseline + DPDP posture
**Question:** what's the default deployment region/provider, and do we design for **Significant Data
Fiduciary (SDF)** obligations now?
- **Recommended default:** **India region (AWS Mumbai `ap-south-1` / GCP Mumbai)**; design seams for
  DPDP (India-resident, self-hostable adapters) but **don't assume SDF** until classified — keep
  PII-encryption (P15) and data-rights (P16) as opt-in toggles.
- **Why:** DPDP (enforcement ~May-2027) doesn't hard-mandate localization but penalizes
  cross-border-without-consent; India-region + self-host defaults keep compliance simple and cheap.
  SDF (DPO, DPIA, audits) is heavy — only when data scale/sensitivity triggers it.
- **Affects:** KMS/secrets/silo adapter choices, the storage default region, and whether P15/P16 are
  early or deferred.
- **Need from you:** ✅ confirm region + "not SDF yet", **or** flag a sector (fintech/health) that
  forces SDF + field-encryption early.

## D3 · Enterprise-auth seam target: self-host vs managed
**Question:** when the first enterprise SSO deal lands, do we point `AuthnPort` at **self-host
Authentik** or a **managed** provider (WorkOS/Scalekit/Stytch)?
- **Recommended default:** **self-host Authentik** (MIT, Python, India-resident, no per-connection
  "SSO tax"); keep a managed adapter as a fast-path for a specific deal.
- **Why:** managed SSO is ₹18k-3L+/mo at 10-50 connections (per-connection pricing) and US-hosted
  (DPDP friction); Authentik is ~₹1.4-2k/mo flat. But managed is faster to integrate for a single
  urgent enterprise contract.
- **Affects:** P13 adapter priority (which one we build first).
- **Need from you:** ✅ confirm Authentik-first, **or** "managed-first because speed > cost for the
  first enterprise deal."

## D4 · Primary India notification channel (beyond email)
**Question:** after email + in-app, which paid channel is the **first** adapter — **WhatsApp
(Gupshup)** or **SMS (MSG91)** — and who owns **DLT/Meta registration**?
- **Recommended default:** **WhatsApp-first (Gupshup)** for engagement/transactional, SMS (MSG91) for
  OTP/fallback.
- **Why:** in India WhatsApp often beats SMS on cost-per-engagement and deliverability; SMS needs
  TRAI **DLT registration** (₹5.9k + template approval) and WhatsApp needs Meta BSP onboarding —
  both are *ops* prerequisites someone must own.
- **Affects:** P9 default-beyond-email adapter + an onboarding checklist.
- **Need from you:** ✅ confirm WhatsApp-first, **or** SMS-first; and who runs the registrations.

## D5 · Durable-workflow engine default
**Question:** for long multi-step AI flows (P11), is the default durable adapter **DBOS Transact**
(Postgres-native) or **Temporal**?
- **Recommended default:** **DBOS Transact** (runs on existing Postgres, MIT, no new cluster);
  Temporal as the heavy seam.
- **Why:** Temporal self-host is a real ops tax (~$26k+/mo class) and Cloud scales to $2k+/mo; DBOS
  gives durability/retries/sagas with zero new infra.
- **Affects:** P11 default adapter.
- **Need from you:** ✅ confirm DBOS default, **or** "go straight to Temporal Cloud."

## D6 · Build-later ReBAC engine
**Question:** which engine does the `AuthorizationPort` stub target — **Cerbos** (embedded, Apache-2)
or **OpenFGA** (Zanzibar service, Apache-2)?
- **Recommended default:** **Cerbos embedded** (no new service, friendly YAML/CEL policies).
- **Why:** cheaper/lighter for a bootstrapped team; OpenFGA's Zanzibar consistency tokens are worth it
  only for high-compliance relationship graphs.
- **Affects:** the P10 stub's shape (cosmetic until a customer needs it).
- **Need from you:** ✅ confirm Cerbos, or OpenFGA.

## D7 · First secrets adapter beyond `.env`
**Question:** when we outgrow `.env`, is the first `SecretsPort` adapter **Infisical** (self-host,
MIT core) or a **cloud secret manager** (AWS/GCP)?
- **Recommended default:** **Infisical** if staying provider-neutral; **cloud manager** if firmly on
  one cloud (VPC-native, no extra service).
- **Why:** avoid HashiCorp **Vault** at bootstrap (BSL license + ops cost).
- **Affects:** P14 adapter choice (the env default ships regardless).
- **Need from you:** ✅ Infisical or cloud-native.

## D8 · RLS rollout scope
**Question:** apply Postgres RLS (P4) to **all** tenant tables at once, or **critical tables first**?
- **Recommended default:** **all tenant-scoped tables** in one migration (uniform backstop), since
  it's additive and the cost is ~1-3% with indexed `org_id`.
- **Why:** partial RLS leaves uncovered tables as silent gaps; uniform is simpler to reason about.
- **Affects:** P4 migration size.
- **Need from you:** ✅ all-at-once, or a critical-first list.

---

## AI-native layer decisions (Wave 5 — see [AI-AGENTIC-STACK.md](AI-AGENTIC-STACK.md))

## D9 · LLM gateway posture  ⭐ (AI unit-economics)
**Question:** default `LLMPort` = **LiteLLM SDK in-process** (+ prompt/semantic caching + token→
`MeteringPort`), with the LiteLLM **proxy**/Portkey as a later seam?
- **Recommended default:** **yes — SDK in-process now** (no separate tier; metering + caching owned),
  proxy/Portkey only when >100 tenants need central governance.
- **Why:** the product is usage-priced → metering is the core and must be owned; a standalone gateway
  adds ~$1.7k/mo ops at small scale for no benefit. Caching (prompt + semantic) is the biggest cost
  lever (70-95%).
- **Need from you:** ✅ confirm SDK-first + caching, or "run a gateway from day one."

## D10 · Default agent framework
**Question:** keep **pydantic-ai** as the default behind an `AgentPort` (LangGraph for HITL/durable,
OpenAI Agents only if GPT-committed)?
- **Recommended default:** **pydantic-ai** (typed, light, multi-provider, MCP-first); seam to LangGraph.
- **Why:** ~90% of agent use is near-linear; OpenAI Agents is ~3× Sonnet cost. Durable runs wrap the
  platform `WorkflowPort` (DBOS) regardless of framework.
- **Need from you:** ✅ confirm pydantic-ai default, or name another.

## D11 · Embedding model + vector store
**Question:** RAG/memory default = **pgvector** + **OpenAI `text-embedding-3-small`**, with self-host
BGE and Qdrant as seams?
- **Recommended default:** **pgvector + text-embedding-3-small** (cheap/quality, no new infra);
  **self-host BGE** (TEI) if PII/DPDP or cost demands embeddings stay in-house; Qdrant only >~50M vectors.
- **Why:** Postgres-native avoids new infra and gives RLS + DPDP-cascade delete free; managed embeddings
  are cheapest unless residency forces self-host.
- **Need from you:** ✅ managed embeddings ok, or self-host BGE for residency?

## D12 · Agent-memory engine
**Question:** default `MemoryPort` = **Postgres** (threads + facts + pgvector), with Mem0/Zep as seams?
- **Recommended default:** **Postgres-native**; adopt Mem0 (entity extraction) or Zep (temporal facts)
  only when that's a revenue lever.
- **Need from you:** ✅ Postgres-native default ok?

## D13 · Evals + GenAI tracing backend
**Question:** **DeepEval** CI eval-gate (block regressions on the existing gate) + GenAI spans over
OTLP; which tracing backend — **self-host Phoenix/Langfuse** vs managed vs **OTLP-into-existing-stack
only**?
- **Recommended default:** **DeepEval gate + OTel GenAI spans into the existing OTLP stack**; add a
  self-host **Arize Phoenix** (lean) or managed free-tier only when you need LLM-specific dashboards.
- **Why:** OTLP-first keeps the backend swappable; DeepEval is free/local and gates on the CI you
  already enforce.
- **Need from you:** ✅ confirm DeepEval + OTLP-only to start, or pick a tracing backend now.

---

### How to respond
A one-line answer per item (or "all defaults") unblocks the build. Defaults are chosen to be the
cost-effective, self-hostable, India-resident, low-lock-in option — so "all defaults" is a coherent,
shippable posture. Revisit D1-D3 before Wave 3; D4-D8 before their phases; **D9-D13 before Wave 5**
(D9, the LLM-gateway/metering posture, is the AI counterpart to D1 and the most consequential).
