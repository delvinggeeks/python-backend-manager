# AGENTS.md — canonical conventions for the python_backend_manager repo

This repo is a **Copier template** that generates self-maintaining FastAPI backends.
`template/` is the body rendered into each service (`*.jinja` is rendered, everything
else is copied verbatim); the repo **root** is the template's own management surface
(CI/CD, Renovate, docs). This file is the single source of truth for how to operate it.
When a convention isn't obvious, **read this file — don't guess.**

## Decision rules
- **Adding a dependency → `uv add`, never `pip`.** The template's deps live in
  `template/pyproject.toml.jinja` (lower-bound pins so `uv lock --upgrade` pulls newest
  compatible); edit there. A PreToolUse hook blocks raw `pip install`.
- **Never build a service inside this repo.** Create one with `/scaffold`, which runs
  `copier copy` into a *sibling* directory; evolve the service there.
- **Exactly one agent framework per service** — `pydantic-ai` | `langgraph` |
  `openai-agents`. They are declared as conflicting extras in `[tool.uv]`; never enable two.
- **Changing the template → run `/validate` before you push.** It generates the matrix
  (none / pydantic-ai / langgraph / openai-agents, × db) and runs lock + ruff +
  ruff-format + mypy + pytest, exactly like CI. Before declaring any template change
  done, `/validate` must pass.
- **Releasing → `/release`.** Commit with Conventional Commits (`feat:` / `fix:` /
  `chore:`; `feat!:` = major). On merge to `main`, CD auto-tags and cuts the GitHub
  Release — only `feat:` / `fix:` / breaking commits bump a version. Downstream services
  pick the tag up on their next `copier update`.
- **Subagents are read-only.** `template-validator`, `build-judge`, `dependency-auditor`,
  and `docs-researcher` only read and report; the **parent session owns all edits,
  commits, and pushes.**
- **Two automation layers — don't confuse them:** dependency freshness
  (`uv lock --upgrade` + Renovate, per service and for this repo) vs template propagation
  (`copier update`, which pulls template changes into already-generated services).

## Commands convention
Every command in `.claude/commands/` must have: a one-line `description`, an
`argument-hint`, a first body line that is a concrete usage **example**, and a
verb-first, intent-obvious name. If the command set grows beyond ~6, group by namespace
folders — `commands/db/migrate.md` → `/db:migrate`.

## Platform spec — the build-out source of truth (`docs/`)
The platform is being hardened into a full SaaS backend via a researched, phased plan. Before
building any new subsystem, **read `docs/` — it is canonical and overrides ad-hoc choices:**
- `docs/PRINCIPLES.md` — cross-cutting laws **every phase inherits** (ports-vs-toggles, gated
  byte-identity, the P3 edge-validation matrix, best-effort/no-op, idempotency, defense-in-depth,
  cost-effective self-hostable defaults). A phase spec lists only its deltas; it inherits these.
- `docs/ROADMAP.md` — the ordered, dependency-sequenced phases. **Build in order; one `feat:` PR per
  phase**, each gated by the existing `generate (capability)` matrix (add the phase's CI row(s)).
- `docs/LIBRARY-DECISIONS.md` — the chosen default lib/provider per subsystem + the swap path (port).
  Don't re-litigate a decision; if you must, update the ADR.
- `docs/ARCHITECTURE.md` — target architecture + the port-adapter catalog (the seam contracts).
- `docs/AI-AGENTIC-STACK.md` — the AI-native application layer (LLM gateway + token metering, agent
  runtime, RAG, memory, evals/tracing, guardrails/MCP-safety); the AI counterpart to LIBRARY-DECISIONS,
  sequenced as ROADMAP Wave 5. Its defining seam: token-usage → `MeteringPort` (AI cost = billable unit).
- `docs/GAP-ANALYSIS.md` — what's BUILD-NOW vs SEAM-NOW vs FINE-AS-IS, and why (incl. gold-plating
  explicitly rejected — don't build the deferred items without a real trigger).
- `docs/COVERAGE-MATRIX.md` — the 360° subsystem checklist (shipped / spec'd / adding / gap / out-of-scope).
- `docs/CURRENT-STATE.md` — the inventory as of the spec.
- `docs/DECISIONS-NEEDED.md` — founder-input calls; proceed on the recommended defaults unless told
  otherwise.

## Where to look
- `copier.yml` — the questions + computed extras.
- `template/AGENTS.md` — the conventions that ship INTO each generated service.
- `README.md` — full pipeline + GitHub setup.
- `docs/` — the platform spec set (above): principles, architecture, library ADRs, roadmap.
