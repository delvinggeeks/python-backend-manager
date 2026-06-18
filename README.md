# witaura-backend-template

A **Copier** template for self-maintaining Python backends: uv-managed, FastAPI,
AI-agent ready. Generated projects stay current on two independent layers —
their **dependencies** and the **template itself**.

## Generate a new project

```bash
# uvx ships with uv; no global install needed
uvx copier copy gh:witaura/witaura-backend-template ./myservice
cd myservice
git init && git add -A && git commit -m "chore: scaffold"
uv lock && uv sync
```

You'll be asked for: project name, Python version, agent framework
(pydantic-ai / langgraph / openai-agents / none), the core capability extras
(db, cache, worker, auth, observability), an optional FastMCP server, and any
SaaS + agentic extras (`saas_extras` multiselect: users, payments, email,
storage, admin, ratelimit, scheduler, api, rag, mcp) to enable. Whatever you
pick is declared in `pyproject.toml` so Renovate / `uv lock` keep it latest and
Python-compatible.

## Update an existing project to the latest template

```bash
cd myservice            # must be a clean git repo
uvx copier update       # pulls the latest template tag, merges changes
```

Generated projects also ship a `template-update.yml` workflow that does this
monthly via PR, and an `update-deps.yml` workflow that upgrades libraries weekly.

## How the two layers work

| Layer | What it tracks | Mechanism | Cadence |
|---|---|---|---|
| Dependencies | PyPI libs, GitHub Actions, Docker base, pre-commit, uv, Python | `uv lock --upgrade` + Renovate | weekly |
| Template | CI, configs, structure, defaults | Copier `update` | monthly / on demand |

Both open **CI-gated PRs**. Auto-merge (if enabled) covers only patch/dev/CI
updates; the AI stack and majors are always reviewed.

## CI/CD for this template repo

`.github/workflows/ci.yml` runs on every push and PR:

- **CI** generates real projects from the *current commit* across a matrix
  (agent framework × db on/off) and runs `uv lock` + `ruff check` +
  `ruff format --check` + `pytest` on each. A broken `.jinja`, a bad dependency
  combination, or unformatted generated code fails the build — so the template
  can never ship a project that doesn't work.
- **CD** runs only on `main`, only after CI passes: it computes the next version
  from Conventional Commits, tags it, and cuts a GitHub Release. That tag is what
  downstream projects pull via `copier update`.

## Maintainer workflow

1. Edit files under `template/`.
2. Open a PR — CI generates + tests every matrix combination.
3. Merge to `main` with a Conventional Commit (`feat:` → minor, `fix:`/`chore:`
   → patch, `feat!:`/`BREAKING CHANGE` → major).
4. CD tags + releases automatically; downstream projects pick it up on their next
   `copier update`.

## Automatic maintenance of this repo

`renovate.json` keeps the template's *own* pins current: GitHub Actions versions
(across both this repo's workflows and the ones in `template/`), pre-commit hook
revs in `template/.pre-commit-config.yaml`, and the pinned `uv` version. Actions
and pre-commit bumps auto-merge after CI passes; majors are held for review.
(The Python version default in `copier.yml` is intentionally manual — moving to a
new minor is a compatibility decision, not routine maintenance.)

Downstream projects carry their own freshness pipeline (rendered `renovate.json`
+ `update-deps.yml` + `template-update.yml`); this repo's Renovate only maintains
the template itself.

## One-time GitHub setup

1. **Workflow permissions** — Settings → Actions → General → Workflow permissions:
   *Read and write* (lets CD tag + release and lets Renovate auto-merge).
2. **Branch protection** on `main` — require the `generate-and-test` checks to
   pass before merge. This makes auto-merge wait for green CI.
3. **Renovate** — install the Renovate GitHub App on the repo (or run the
   self-hosted `renovatebot/github-action`). Dependabot is a zero-install
   fallback for Actions only, but can't manage pre-commit or the uv pin.

## Claude agent architecture

This repo is operated by Claude Code at two levels:

- **Manager** (repo root): `AGENTS.md` (canonical conventions) + a thin `CLAUDE.md`
  that imports it, plus `.claude/` with subagents (`template-validator`, `build-judge`,
  `dependency-auditor`, `docs-researcher`), slash commands (`/scaffold`, `/validate`,
  `/audit-deps`, `/release`), permission rules, and two hooks (no-pip + ruff-format).
  Subagents are read-only analysts; the parent owns edits.
- **Service body** (`template/.claude/` + `template/AGENTS.md` + `template/CLAUDE.md.jinja`):
  renders into every generated service so it's born agent-ready — its own `AGENTS.md`
  SoT, `code-reviewer` + `build-judge` subagents, `/check` + `/feature` commands,
  settings, and the same two hooks.

## Working with Claude

`AGENTS.md` is the single source of truth for conventions and decision rules;
`CLAUDE.md` just `@AGENTS.md`-imports it and lists the Claude-Code surface (which
commands and subagents exist). Drive the repo through its verb-first slash commands:

- `/scaffold <name> [framework] [--no-db]` — generate a service into a sibling dir.
- `/validate` — run the full CI gate locally across the matrix before pushing.
- `/audit-deps` — audit dependency freshness + risk (AI stack first).
- `/release <feat|fix|chore> "<summary>"` — validate, then prepare a release.

Two guardrails run automatically: a PreToolUse hook **blocks `pip install`** (use
`uv add`), and a PostToolUse hook ruff-formats Python on save. Subagents are
read-only analysts; the parent session owns all edits, commits, and pushes.

## Repo structure

```
AGENTS.md                  # canonical conventions + decision rules (SoT)
CLAUDE.md                  # thin @AGENTS.md import + Claude-Code command/subagent map
.claude/                   # manager subagents, commands, settings, hooks
copier.yml                 # questions + computed extras + update settings
renovate.json              # auto-maintenance of THIS repo
template/                  # the project body (.jinja rendered; .claude ships into services)
.github/workflows/ci.yml   # CI (matrix generate+test) + CD (tag+release)
CHANGELOG.md
```
