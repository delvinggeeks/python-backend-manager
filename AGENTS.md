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

## Where to look
- `copier.yml` — the questions + computed extras.
- `template/AGENTS.md` — the conventions that ship INTO each generated service.
- `README.md` — full pipeline + GitHub setup.
