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
- **Validating a capability leg → `scripts/leg-check.sh`, never a hand-typed command list.** It is
  the single definition of "a leg passed" — `.github/workflows/ci.yml` invokes exactly the same
  script with the same arguments. Two separate lists drift, and the drift only ever surfaces as
  "it passed locally and CI disagrees". Adding a gate means adding it there, once.
  Corollary: **commit before you validate.** `copier --vcs-ref HEAD` renders a *dirty worktree*, so
  a leg-check on uncommitted edits silently validates something the commit does not contain.
- **Scope every command to what the task needs — wildcards default to more.** On a branch carrying
  one slice, stage by explicit path, never `git add -A` (enforced by `.claude/hooks/staged-scope.sh`
  against `.claude/slice-scope`). The same discipline covers the other over-reaching defaults:
  `rm -rf` outside the generated/scratch tree, and `pkill -f`, which matches far more than the
  process you meant and will happily kill the session running it. Prefer a named target: a specific
  path, a recorded PID. `rm -rf` is already denied by `.claude/settings.json`; the rest is this rule.
- **A PR opens only after the evidence it will be judged on exists.** Open it when the matrix,
  gate or benchmark it claims has actually been run — not before, so the first thing a reviewer
  sees is the result rather than a promise of one.
- **Subagents are read-only.** `template-validator`, `build-judge`, `dependency-auditor`,
  and `docs-researcher` only read and report; the **parent session owns all edits,
  commits, and pushes.**
- **GC Friday — a repeated mistake becomes a gate, never a reminder.** A standing weekly session
  walks the week's corrections and asks one question of each: *could this have been made impossible
  rather than merely discouraged?* Where the answer is yes, the output is a hook, a CI gate, a lint
  rule or a script — **never a doc line**, because a doc line is the thing that already failed. This
  is [PRINCIPLES.md](docs/PRINCIPLES.md)'s discipline and
  [SECURITY-BASELINE.md](docs/SECURITY-BASELINE.md) §0's position doctrine applied to process rather
  than to code. Already harvested this way: `.claude/hooks/staged-scope.sh`, `scripts/leg-check.sh`,
  and the `ci-ok` gate. **Caveat, stated so it isn't mistaken for coverage:** the cadence itself is a
  convention, and conventions are exactly what this repo distrusts — it recurs only as long as
  someone runs it.
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
- `docs/MONETIZATION.md` — the monetization **decision** layer above the billing plumbing: the
  revenue-model & packaging engine (`PricingPort`, pricing-as-versioned-data, multi-stream) + **AI pricing
  intelligence** (`PricingIntelligencePort`, recommend/dynamic/experiment, human-gated). ROADMAP Wave 9
  (P39/P40); founder gates D19/D20.
- `docs/GAP-ANALYSIS.md` — what's BUILD-NOW vs SEAM-NOW vs FINE-AS-IS, and why (incl. gold-plating
  explicitly rejected — don't build the deferred items without a real trigger).
- `docs/COVERAGE-MATRIX.md` — the 360° subsystem checklist (shipped / spec'd / adding / gap / out-of-scope).
- `docs/COMPLETENESS-AUDIT.md` — the adversarial *no-gaps proof*: every backend subsystem (A-K) specced,
  or (L) consciously out-of-scope with reasoning. A living audit — a new subsystem becomes a phase.
- `docs/CURRENT-STATE.md` — the inventory as of the spec.

**Engineering-discipline layer (HOW each phase is built — full SDLC, every phase obeys these):**
- `docs/BUILD-SYSTEM.md` — the **agentic build & assurance system**: the 7-gate per-phase pipeline
  (Ready→Build→Quality→Test/edge→**skeptical adversarial review**→DoD/trace→Merge), the parent-builds /
  subagents-review split, the real-use-case + edge-matrix + property/fuzz/mutation testing, and a
  reference Workflow that fans out a diverse-lens adversarial panel + `build-judge`. Rigor scaled to risk.
- `docs/SDLC.md` — the lifecycle discipline: the **per-phase artifact set** + Definition-of-Ready /
  Definition-of-Done gates. A phase is NOT done until its design + threat model + tests + traceability
  rows + runbook + SLO merge with the code. Lean-by-team-size; never skip the gates.
- `docs/TRACEABILITY.md` — the living **requirements-traceability matrix** (requirement → component →
  test → CI gate → deploy → SLO), machine-checked in CI. The master phase→trace table lives here.
- `docs/SYSTEM-DESIGN.md` — platform **C4 + sequence + ER diagrams** (Mermaid, diagrams-as-code); each
  phase ships its own component/sequence/ER-delta diagrams in the same notation.
- `docs/CICD-PIPELINE.md` — the CI/CD stages + **DevSecOps gates** (secret-scan/SAST/SCA/SBOM/sign/SLSA)
  wrapping the existing capability gate.
- `docs/CODE-QUALITY.md` — the **code-quality + coverage + deterministic-code** gates (ruff/mypy-strict +
  import-linter architecture enforcement + complexity/dead-code/docstring + patch-coverage; Hypothesis/
  Schemathesis/mutmut; pytest-randomly + freezegun + reproducible builds). Python-native stack > SonarQube
  for this scope (ADR-36). It's the quality half of P2; every phase inherits it.
- `docs/INFRA-TOPOLOGY.md` — cloud / hybrid / self-host **deployment routes + networking + IaC**, staged
  by growth; India-residency (DPDP) constraints.
- `docs/MCP-SERVERS.md` — building **custom MCP servers** (FastMCP, Streamable HTTP, OAuth2.1, per-tenant);
  safety ties to P29/P26.
- `docs/DECISIONS-NEEDED.md` — founder-input calls; proceed on the recommended defaults unless told
  otherwise.

## Where to look
- `copier.yml` — the questions + computed extras.
- `template/AGENTS.md` — the conventions that ship INTO each generated service.
- `README.md` — full pipeline + GitHub setup.
- `docs/` — the platform spec set (above): principles, architecture, library ADRs, roadmap.
