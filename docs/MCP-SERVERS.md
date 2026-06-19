# MCP-SERVERS.md — building custom MCP servers in a generated service

> The template *mounts* FastMCP at `/mcp` today (the `include_mcp` toggle). This doc specs the
> discipline for a generated service to **define and expose its own production MCP server** — curated
> tools/resources/prompts over the SaaS's domain, consumable by Claude / IDEs / agents — securely and
> multi-tenant. Inherits [PRINCIPLES.md](PRINCIPLES.md); the safety controls are
> [ROADMAP.md](ROADMAP.md) **P29** (agent system-safety) + **P26** (MCP tool safety); design notation
> per [SYSTEM-DESIGN.md](SYSTEM-DESIGN.md). Researched 2025-2026, cited; treat exact SDK versions as
> *verify-at-build*.

---

## 1. Decision summary

| Axis | Choice | Why |
|---|---|---|
| **SDK** | **FastMCP** (on the MCP Python SDK) | least boilerplate, auto schema/validation, OAuth middleware, OTel hooks; dominant in 2025-2026 |
| **Transport** | **Streamable HTTP** (stateless), mounted at `/mcp`; `stdio` dev toggle | the only multi-tenant-web-grade transport (HTTP+SSE deprecated); stateless → any replica serves any request, no sticky sessions |
| **Auth** | **OAuth 2.1 + PKCE** + **RFC 9728 Protected Resource Metadata** (`/.well-known/…`), reusing `AuthnPort` | the Nov-2025 MCP spec mandates it for remote servers; the SaaS IdP is the auth server, the MCP server is a resource server |
| **Multi-tenancy** | extract `tenant_id` from the token; **filter tools/resources/prompts at discovery** | a client only ever *sees* its tenant's capabilities (the Asana-2025 cross-tenant leak is the cautionary tale) |
| **Verdict** | **SEAM-NOW** the "define-your-own-server" surface; the **safety controls are BUILD-NOW with P29** | exposing tools that act on the system is exactly the P29 threat surface — never ship the server capability ahead of the guardrails |

---

## 2. The seam: how a service defines its MCP server

Gated on `include_mcp`, a generated service gets an `app/mcp/` package that is a **thin MCP facade
over the existing ports** — MCP tools call `app.billing`/`app.audit`/… through their ports; they never
re-implement domain logic (DRY, and they inherit RLS + audit + idempotency for free).

```
app/mcp/
  server.py      # FastMCP server factory; mounted at /mcp (Streamable HTTP)
  auth.py        # OAuth2.1 token validate + tenant extraction (reuses AuthnPort);
                 # serves RFC 9728 resource metadata
  policy.py      # per-tenant capability filter for tools/list + resources/list (P29 AgentPolicy)
  tools/         # one module per domain; each tool wraps an existing port/service
  resources/     # read-only context (org settings, catalogs) — tenant-scoped URIs
  prompts/       # multi-step task templates that chain tools (with elicitation points)
```

**Primitives** (use the right one):
- **Tools** = actions the agent *invokes* (`create_invoice`, `query_audit`) — go through ports, are
  audited, are role-gated.
- **Resources** = context the agent *reads* (`org/{id}/settings`) — `read_only`, tenant-scoped URI,
  cacheable.
- **Prompts** = reusable workflows that orchestrate tools, with **elicitation** (human-in-the-loop
  input) at ambiguous steps — distinct from LLM *sampling*.

---

## 3. Security — the non-negotiables (BUILD-NOW with P29)

Exposing tools that act on the system *is* the P29 threat surface. Every MCP server in a generated
service must satisfy, enforced in CI:

1. **Per-tenant isolation at discovery AND execution** — `tools/list`/`resources/list` filtered by the
   token's `tenant_id`; every tool's data access goes through the RLS-scoped session. (The cross-tenant
   MCP-leak class is the #1 incident pattern.)
2. **OAuth 2.1 + Resource Indicators (RFC 8707)** — tokens are audience-bound to this server; a bare
   401 advertises the RFC 9728 metadata URL.
3. **`Origin` validation on POST** (DNS-rebinding defense for Streamable HTTP); tokens/`MCP-Session-Id`
   never logged in plaintext.
4. **Tool = capability-gated** via `AgentPolicy` (P29): allow/deny lists per tenant, role-gating
   (`require_role(owner)` for destructive tools), **HITL approval** for destructive/irreversible tools.
5. **Strict arg-schema validation** (Pydantic) + **SSRF egress guard** (reuse P1) for any URL-fetching
   tool + **sandboxed execution** for untrusted tool code.
6. **Immutable audit** of every tool invocation (actor, tenant, tool, redacted args, outcome, cost,
   trace-id) via `app.audit` — append-only, 90-day+ retention (DPDP).
7. **Tool over-privilege review** — a tool that can delete an org is owner-gated + HITL; the design
   checklist (below) is a CI/PR gate.

---

## 4. Tool / resource / prompt design checklist (a PR gate)

**Every tool:** tenant-scoped input or context-extracted `tenant_id`; data access via the
RLS-scoped session/port; Pydantic-validated inputs + declared output schema; reuses an existing
service (no logic fork); audited; role-gated if sensitive; HITL if destructive; SSRF-guarded if it
fetches URLs; tested in MCP Inspector + a CI conformance check.
**Every resource:** tenant-scoped URI; `read_only`; schema + pagination hints; tenant-keyed cache;
retrieval audited.
**Every prompt:** documents the workflow + the tools/resources it uses; declares elicitation points;
version-tagged for deprecation; example usage.

---

## 5. Testing & deployment

- **Testing:** the **MCP Inspector** (`just mcp:inspect`) for interactive schema/tool validation in dev;
  a **CI conformance step** validates the rendered server's schemas + a sample tool call against the
  spec (extends the `generate (capability)` gate — an `mcp` capability row), with mocked auth.
- **Deployment:** stateless Streamable HTTP → the MCP endpoint scales with the API replicas behind the
  same ingress (no session store; cache hot tool schemas in Redis if needed). Auto-instrumented by the
  existing OTel/observability seam (spans per tool call). Discovery: ship the internal `/mcp` URL;
  list on a public registry (mcp.so / Anthropic registry) only when deliberately ready.
- **Cost/ops:** ≈ ₹0 incremental — same FastAPI process/replicas; ~negligible CPU for dispatch + token
  validation; audit growth ~100 B/call.

---

## 6. Roadmap placement

This elevates the existing `include_mcp` mount into a **"define + expose your own MCP server" capability**:
- The **server seam + per-tenant auth/filtering** is a phase that lands **alongside or after P26**
  (guardrails/MCP-tool-safety) and **depends on P29** (AgentPolicy + HITL + sandbox + audit) — *the
  safety layer ships first or together; never the exposure ahead of the guardrails*.
- It reuses **AuthnPort** (OAuth), **AuthorizationPort** (capability/role gating), **AuditPort**, the
  **SSRF guard** (P1), and the **observability** seam — so it's a facade, not new infrastructure.

Add an `mcp_server` capability row to the `generate (capability)` matrix (Inspector schema-validation +
per-tenant filter test + a destructive-tool HITL/role-gate test), per the SDLC per-phase template
([SDLC.md](SDLC.md)) and traced in [TRACEABILITY.md](TRACEABILITY.md).
