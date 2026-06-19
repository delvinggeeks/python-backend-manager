# AI-AGENTIC-STACK.md — the AI-native application layer

> The platform spec ([ARCHITECTURE](ARCHITECTURE.md)/[ROADMAP](ROADMAP.md)/[LIBRARY-DECISIONS](LIBRARY-DECISIONS.md))
> hardens the SaaS *substrate*. This doc specs the **AI application layer** that rides on it — the
> reason the substrate exists, since the founder's products are **usage-priced AI**. It inherits all
> of [PRINCIPLES.md](PRINCIPLES.md) (ports-vs-toggles, gated byte-identity, the edge-validation
> matrix, best-effort/no-op, cost-effective self-hostable defaults). The AI phases live in
> [ROADMAP.md → Wave 5](ROADMAP.md); founder calls in [DECISIONS-NEEDED.md](DECISIONS-NEEDED.md).
> Researched 2025-2026, cited; treat fast-moving version numbers/acquisitions as *verify-at-build*.

---

## 1. Current AI surface (what ships at v0.18.0)

A **base**, not a platform layer:
- **`llm` extra** — `anthropic`, `openai`, `litellm`, `instructor`, `tiktoken`.
- **Agent frameworks** as *conflicting* copier extras (one per service): `pydantic-ai`
  (`pydantic-ai-slim[anthropic,openai]`), `langgraph` (+langchain, langchain-anthropic/openai),
  `openai-agents`.
- **`agents/example_agent.py`** — a thin tier-resolving runner (`pydantic-ai → raw Anthropic →
  AgentUnavailableError`), lazy imports, model from settings; `/agent` route.
- **Model cascade in settings** — `model_fast=claude-haiku-4-5`, `model_default=claude-sonnet-4-6`,
  `model_frontier=claude-opus-4-8` (current Claude tiers; keep latest).
- **`include_mcp`** — mounts FastMCP at `/mcp`.
- **`rag` extra** — `pypdf`, `qdrant-client`, `semantic-text-splitter` — **deps only, no module**.

**Absent (the gap):** LLM gateway / model router; **per-tenant token metering** (the unit-economics
link); prompt + semantic caching; a RAG/retrieval module; agent memory/state; agent tool/MCP
safety (per-tenant scoping, SSRF, sandbox); guardrails/PII-redaction; prompt management; GenAI
tracing (OTel GenAI spans) and an evals harness/CI gate; structured durability for long agent runs
(the `WorkflowPort` from platform P11 covers this once both land).

---

## 2. The one idea that ties AI to the platform: **metering is the core, the gateway is the seam**

For a usage-priced AI product, *a tenant's tokens are your cost of goods*. So the architecture is:

```
request (tenant ctx) → LLMPort (LiteLLM SDK default)
   → prompt cache (90% off cached input) + semantic cache (skip the call entirely)
   → provider (Anthropic default, fallback chain)
   → parse usage{input,output,cache_read,cache_creation} → cost
   → MeteringPort.record(tenant, model, tokens, cost)        ← the platform's P7 metering
   → budget check: spend > cap → 429                          ← real-time spend control
                                  ↓ nightly
                        BillingPort → invoice (Razorpay/Stripe)
```

The **gateway** (LiteLLM SDK ↔ proxy ↔ Portkey ↔ Cloudflare) is swappable behind `LLMPort`; the
**metering** path is not — if it breaks, revenue breaks. This is why P21 (below) is the highest-value
AI phase and why it depends on the platform's `MeteringPort` (P7). Caching is a BUILD-NOW multiplier:
prompt + semantic caching cut effective token spend **70-95%** with no UX change.

---

## 3. AI port catalog (the AI seams)

Legend: ➕ build-now · 🔌 seam-now · 🟢 fine-as-is. "Default" = cheapest self-hostable; no new infra.

| Port | Status | Default (self-host / no new infra) | Seam to (later) | Selected by |
|---|---|---|---|---|
| **LLMPort** (model router + cost) | ➕ | **LiteLLM SDK in-process** (MIT, already present) + prompt/semantic caching (Redis) | LiteLLM **proxy** · Portkey-OSS (Apache-2) · Cloudflare AI Gateway | `llm_gateway` setting |
| **AgentRuntime / AgentPort** | 🔌 | keep framework **toggles**; **pydantic-ai** default runner | LangGraph (HITL/durable) · OpenAI Agents (GPT) | `agent_framework` toggle |
| *(durable agent runs)* | — | → platform **WorkflowPort** (DBOS) [P11] | Temporal | `workflow_engine` |
| **RetrievalPort** (RAG) | ➕ | **pgvector-native** hybrid (tsvector+vector, RRF) + ingestion | Qdrant/Weaviate (>~50M vectors) | `search_backend` |
| **EmbeddingPort** | 🔌 | OpenAI `text-embedding-3-small` (cheap/quality) | self-host BGE/E5 (TEI) · Cohere/Voyage | `embedding_model` |
| **RerankPort** | 🟢/🔌 | off by default; optional Cohere rerank / bge-reranker | — | `rerank_provider` |
| **MemoryPort** (agent memory) | 🔌 | **Postgres** threads+messages+facts (+pgvector, RLS, TTL) | Mem0 · Zep · Letta · LangGraph Store | `memory_provider` |
| **GuardrailPort** | 🔌 | **instructor** (present) + LLM-Guard (PII/injection) + Guardrails AI | NeMo Guardrails · provider moderation | `guardrails` toggle |
| **PromptPort** (registry/versioning) | 🔌 | **Postgres** prompt registry (+ A/B via FeatureFlagPort) | Langfuse prompts | `prompt_provider` |
| **MCPToolPort** (tool registry/safety) | 🔌 | FastMCP (present) + per-tenant scoping + **SSRF guard (reuse P1)** + sandbox seam | hosted MCP / Modal/CF sandbox | — (extends `include_mcp`) |
| **GenAI tracing** | ➕ | extend **ObservabilityExport** w/ OTel **GenAI spans** (tokens/cost/model/tools) | Langfuse / Arize Phoenix (self-host) | `OTEL_*` endpoint |
| **Evals** (dev/CI, not runtime) | ➕ | **DeepEval** pytest harness + CI eval-gate | Confident AI / Braintrust (managed) | `include_evals` |

---

## 4. ADRs (one per AI subsystem)

Format — **Default** · *Alternatives (cost / license)* · **Why** · **Swap path**.

### AI-ADR-01 — LLM gateway, routing & per-tenant cost  ⭐
- **Default:** **LiteLLM SDK in-process** (MIT; already in the `llm` extra) behind an `LLMPort`, with
  **prompt caching** (`cache_control`, ~90% off cached input) + **semantic caching** (Redis/Qdrant),
  and a **token-usage → `MeteringPort`** bridge with per-tenant **budget caps (429)**.
- **Alternatives:** LiteLLM **proxy** (separate service — adds ops/labor ~$1.7k/mo, only worth it at
  scale); **Portkey** OSS (Apache-2, 1600+ models, native budgets/guardrails); **Cloudflare AI
  Gateway** (free tier, edge caching); **OpenRouter** (5.5% fee, no multi-tenant budgets, US data
  path — DPDP friction); **Kong AI Gateway** (enterprise $$$).
- **Cost:** in-process SDK ≈ ₹0 infra; caching cuts *model* spend 70-95%; managed gateways add fee
  or ops. At <10M tok/mo the **SDK (not a proxy)** is correct — no separate tier to run.
- **Why:** the product is usage-priced → metering is core and must be owned; the SDK gives routing +
  caching with zero new infra; the proxy/Portkey is a later swap when >100 tenants need central
  governance.
- **Swap path:** `LLMPort` (complete/stream + usage) → proxy/Portkey/Cloudflare adapter; the
  `MeteringPort` bridge is unchanged.

### AI-ADR-02 — Agent framework & runtime
- **Default:** keep the **conflicting toggles**; **pydantic-ai** as the default (typed, lightweight,
  multi-provider, MCP-first, native OTel) behind a thin **`AgentRuntime`/`AgentPort`** seam.
- **Alternatives:** **LangGraph** (MIT; best HITL + checkpointing + branching — pick for durable
  multi-agent); **OpenAI Agents SDK** (GPT-centric, ~3× Sonnet cost — only if GPT-committed); CrewAI
  (managed-cloud lock-in), Google ADK (Gemini), smolagents (code-synthesis niche).
- **Cost:** all OSS; model spend dominates. pydantic-ai lightest footprint.
- **Why:** 90% of agent use is near-linear → pydantic-ai's clarity + cost wins; the seam lets a
  service graduate to LangGraph without rewriting the route. Long-running/HITL runs wrap the
  platform **WorkflowPort** (DBOS/Temporal, P11) for durability (none of the frameworks are durable
  by themselves).
- **Swap path:** `AgentPort` adapter per framework, selected by the `agent_framework` toggle;
  `WorkflowPort` for durable execution.

### AI-ADR-03 — RAG / retrieval
- **Default:** **pgvector-native** (already in the template) behind a `RetrievalPort` — hybrid
  search (tsvector BM25 + vector, RRF merge in SQL), HNSW (pgvectorscale), ingestion via `pypdf` +
  `semantic-text-splitter`; **embedding default `text-embedding-3-small`**; rerank **off** by default.
- **Alternatives:** Qdrant (AGPL self-host / cloud) at >~50M vectors or filter-heavy workloads;
  Weaviate/Milvus/LanceDB; managed Pinecone (lock-in/cost — avoid). Rerank: Cohere rerank /
  bge-reranker (self-host). Embeddings: BGE/E5 self-host (TEI) for cost/DPDP, Cohere/Voyage.
- **Cost:** pgvector ≈ ₹0 new infra; pgvector(scale) beats standalone Qdrant under tens of millions
  of vectors; external engine adds a service only past that.
- **Why:** stay in Postgres until scale forces out; zero new infra, RLS multi-tenancy + DPDP-cascade
  delete come free.
- **Swap path:** `RetrievalPort` → Qdrant adapter; `EmbeddingPort`/`RerankPort` sub-seams.

### AI-ADR-04 — Agent memory & state
- **Default:** **Postgres** `MemoryPort` — `threads`/`messages` (+ `memory_facts` with pgvector for
  semantic recall), tenant-isolated by **RLS**, **DPDP TTL + audit + 48h-notice erasure**; pairs with
  `RetrievalPort` (semantic memory) and `WorkflowPort` (checkpoints).
- **Alternatives:** **Mem0** (OSS + managed; auto entity extraction), **Zep** (temporal knowledge
  graph, fact validity windows), **Letta/MemGPT** (single-org), LangGraph Store (embedded Postgres);
  Redis-vector (cache only, not durable).
- **Cost:** Postgres ≈ ₹1.4-28k/mo across scale; Mem0 +$19-249/mo, Zep +$125/mo — only if
  entity-extraction/temporal reasoning is a revenue lever.
- **Why:** 80% of memory needs are thread history + semantic recall — Postgres does both with no new
  infra and clean DPDP erasure; managed memory is a later, ROI-gated swap.
- **Swap path:** `MemoryPort` → Mem0/Zep adapter (tenant-scoped).

### AI-ADR-05 — GenAI observability & evals
- **Default:** extend the **existing `ObservabilityExport`/OTLP** seam to emit **OTel GenAI
  semantic-convention spans** (`gen_ai.usage.*` tokens, model, cost, tool spans) — emit once, route
  to any backend; plus a **DeepEval** (Apache-2, pytest-native) **eval harness + CI eval-gate**
  (accuracy/safety/cost thresholds, LLM-as-judge) wired into the `generate (capability)` gate.
- **Alternatives (tracing backend):** self-host **Langfuse** (MIT; richest, ClickHouse-heavy ~$/mo)
  or **Arize Phoenix** (Apache-2, Postgres-only, lean) behind OTLP; managed Langfuse Pro / LangSmith
  / Braintrust / Helicone. **Evals:** Promptfoo (MIT), Ragas (MIT, RAG-only).
- **Cost:** GenAI spans + DeepEval ≈ ₹0 (ride the existing OTLP stack); a tracing backend adds
  $0-200/mo small (Phoenix/managed-free-tier) or self-host Langfuse at scale.
- **Why:** "who called the LLM, at what cost, did quality regress" is the core AI debuggability +
  release-safety gap; OTLP-first keeps the backend swappable; DeepEval gates regressions pre-merge
  on the gate the repo already enforces.
- **Swap path:** OTLP endpoint (tracing backend); `include_evals` extra + the CI gate.

### AI-ADR-06 — Guardrails, prompts & MCP tool safety
- **Default:** **GuardrailPort** = `instructor` (present, schema-enforced output) + **LLM-Guard**
  (MIT, PII redaction + prompt-injection scan, ties to platform PII-encryption P15) + Guardrails AI
  validators; **PromptPort** = a **Postgres** prompt registry with versioning + A/B via the
  `FeatureFlagPort` (P18); **MCPToolPort** = FastMCP (present) with **per-tenant tool scoping**,
  **SSRF guard reused from P1**, and a **sandboxed-execution** seam (Modal/Cloudflare).
- **Alternatives:** NeMo Guardrails (Apache-2, Colang DSL); provider moderation (OpenAI/Anthropic);
  Langfuse prompt management; hosted MCP. Pin FastMCP and keep tool execution sandboxed (the MCP
  ecosystem had transport-RCE advisories — verify versions at build).
- **Cost:** ≈ ₹0 (libraries + Postgres); sandbox ≈ free-tier.
- **Why:** prompt-injection, PII leakage to providers, and tool-driven SSRF are the AI-specific
  attack surface; structured output + redaction + tool scoping close it cheaply; prompt versioning
  makes safe iteration possible.
- **Swap path:** each is a port; managed prompt/guardrail services slot behind them.

---

## 5. Gap table (AI layer) — build / seam / fine

| AI subsystem | Current | Researched best | Sev | Verdict |
|---|---|---|---|---|
| **LLM gateway + token metering** | litellm dep, no router/metering | LiteLLM SDK + caching + token→billing | 🔴 | **BUILD-NOW** (priority; needs P7) |
| **GenAI tracing + evals** | OTLP, no GenAI spans/evals | OTel GenAI spans + DeepEval CI-gate | 🔴 | **BUILD-NOW** |
| **Agent runtime seam** | example runner only | `AgentPort` + cost/usage-cap + durable via WorkflowPort | 🟠 | **SEAM-NOW** |
| **RAG / retrieval** | rag deps, no module | `RetrievalPort` pgvector-native | 🟠 | **SEAM-NOW** (BUILD the module) |
| **Agent memory** | none | `MemoryPort` Postgres-native | 🟠 | **SEAM-NOW** |
| **Guardrails + PII redaction** | instructor only | `GuardrailPort` (LLM-Guard + instructor) | 🟠 | **SEAM-NOW** |
| **MCP tool safety** | FastMCP open mount | per-tenant scoping + SSRF + sandbox | 🟠 | **SEAM-NOW** |
| **Prompt management** | in-code | `PromptPort` DB registry + A/B | 🟡 | **SEAM-NOW** |
| **Embedding/rerank** | n/a | `EmbeddingPort`/`RerankPort` | 🟡 | **SEAM-NOW** (with RAG) |
| **Durable agent execution** | none | platform `WorkflowPort` (P11) | 🟠 | **covered by P11** |
| **Model cascade defaults** | present, current Claude tiers | keep latest | 🟢 | **FINE-AS-IS** |
| **Framework-per-service** | conflicting toggles | correct pattern | 🟢 | **FINE-AS-IS** |

**Gold-plating rejected:** no dedicated vector DB at MVP (pgvector suffices), no managed memory/gateway
before scale, no self-host Langfuse cluster before a residency mandate, no multi-agent orchestration
framework before a multi-agent product — each is a seam, not a build.

---

## 6. DPDP / cost notes (AI-specific)
- **PII to providers:** redact at the `GuardrailPort` before prompts leave the trust boundary; prefer
  India-region or self-host embeddings for sensitive corpora; embeddings of PII fall under DPDP.
- **Erasure:** memory + RAG stores cascade-delete by subject/collection (crypto-shred the key per
  platform P15/P16); audit every deletion.
- **Cost discipline:** prompt + semantic caching first (biggest lever); model cascade (haiku→sonnet→
  opus) by task; per-tenant budget caps; meter everything. Self-host the *infra* (pgvector, LiteLLM
  SDK, Phoenix), pay only for *tokens* and the occasional managed backend.

The AI phases that implement all of this are **Wave 5 (P21-P26)** in [ROADMAP.md](ROADMAP.md).
