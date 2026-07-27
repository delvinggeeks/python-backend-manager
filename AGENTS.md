# AGENTS.md — canonical conventions for the python_backend_manager repo

How to operate this repo. *What* it is lives in [PLATFORM-INTEGRATION.md](docs/PLATFORM-INTEGRATION.md);
`template/` is the rendered body (`*.jinja` rendered, the rest copied verbatim), root is management.

## Decision rules
- **Adding a dependency → `uv add`, never `pip`.** The template's deps live in
  `template/pyproject.toml.jinja` (lower-bound pins so `uv lock --upgrade` pulls newest
  compatible); edit there. A PreToolUse hook blocks raw `pip install`.
- **Never build a service inside this repo.** Create one with `/scaffold`, which runs
  `copier copy` into a *sibling* directory; evolve the service there.
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
- **GC Friday — a repeated mistake becomes a gate, never a reminder.** A weekly session asks of each
  correction: *could this have been made impossible rather than discouraged?* Where yes, the output
  is a hook, a CI gate or a lint rule — **never a doc line**, because a doc line is the thing that
  already failed. `.github/workflows/gc-friday.yml` gathers the week's evidence: the trigger and the
  inventory are mechanical, the judgement is invoked.
- **Two automation layers — don't confuse them:** dependency freshness
  (`uv lock --upgrade` + Renovate, per service and for this repo) vs template propagation
  (`copier update`, which pulls template changes into already-generated services).

## Commands convention
Every command in `.claude/commands/` must have: a one-line `description`, an
`argument-hint`, a first body line that is a concrete usage **example**, and a
verb-first, intent-obvious name. If the command set grows beyond ~6, group by namespace
folders — `commands/db/migrate.md` → `/db:migrate`.

## Reading contract

**A session reads the smallest set that makes its task unambiguous.**

**Always read** — and nothing else by default: this file, and
[docs/PLATFORM-INTEGRATION.md](docs/PLATFORM-INTEGRATION.md) (what this repo is, the two modes, the
four standard endpoints). Both are line-budgeted in `.doc-budgets.toml` and gated in CI: growing one
means raising its budget in the same PR, so growth is a reviewed decision rather than a drift.

**Read just-in-time, by task type:**

| Doing this | Read |
|---|---|
| Selecting or sizing work | the relevant phase in [docs/ROADMAP.md](docs/ROADMAP.md) — the single ledger |
| Building or changing a gate, resolving a conflict, or any security work | [docs/SECURITY-BASELINE.md](docs/SECURITY-BASELINE.md) — §0 position doctrine, §13 gate conventions + what is already enforced |
| Building a module | that module's `docs/` entry + [docs/PRINCIPLES.md](docs/PRINCIPLES.md) |
| Choosing a library or provider | [docs/LIBRARY-DECISIONS.md](docs/LIBRARY-DECISIONS.md) — don't re-litigate; amend the ADR |
| Wiring a seam | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) port-adapter catalog |
| Asking "is this shipped?" | [docs/COVERAGE-MATRIX.md](docs/COVERAGE-MATRIX.md) — the single home for shipped inventory |
| Deploying / infra | [docs/INFRA-TOPOLOGY.md](docs/INFRA-TOPOLOGY.md) |
| The AI layer | [docs/AI-AGENTIC-STACK.md](docs/AI-AGENTIC-STACK.md) · monetization: [docs/MONETIZATION.md](docs/MONETIZATION.md) |
| How a phase is built / judged | [docs/BUILD-SYSTEM.md](docs/BUILD-SYSTEM.md) · [docs/SDLC.md](docs/SDLC.md) · [docs/CODE-QUALITY.md](docs/CODE-QUALITY.md) |

## Session protocol

**One ticket per session, fresh context, no exceptions.** Grouped sessions are how dumb-zone endings
happen: quality degrades with context depth, and the degradation is invisible from inside it.

- **Finishing early never pulls a second ticket.** Remaining context is safety margin, not budget.
- **A ticket proving oversized mid-session is stopped and split** — commit the coherent part, write
  the remainder as a new ticket with breadcrumbs, end the session.
- **Every session ends** by writing breadcrumbs and updating its ticket's status in the ledger.
- **The rule is never applied retroactively.** It bounds context *before* work, so re-splitting
  finished, verified work buys review granularity only — which commits inside one PR already give.

Sessions that stay in the smart zone don't hallucinate. Tickets sized to sessions guarantee that
structurally, rather than by anyone remembering to stop.

## Where to look
`copier.yml` (questions + computed extras) · `template/AGENTS.md` (ships INTO services) · `README.md`.
