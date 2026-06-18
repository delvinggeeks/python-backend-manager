# AGENTS.md — conventions for AI coding agents in this service

Generated from python_backend_manager. This file is the single source of truth for how
this service is built. When a convention isn't obvious, **read this file — don't guess.**

## Stack
- Python 3.13+, managed entirely by **uv**. Web: FastAPI + Pydantic v2, async-first.
- Layout: `src/app` (app factory in `app.main:app`), tests in `tests/`.

## Decision rules
- **Adding a dependency → `uv add`, never `pip`:** `uv add <pkg>` (core),
  `uv add --optional <extra> <pkg>`, or `uv add --dev <pkg>`. Commit the resulting
  `uv.lock`. A PreToolUse hook blocks raw `pip install`.
- **Exactly one agent framework per service** — `pydantic-ai`, `langgraph`, or
  `openai-agents`. They are declared as conflicting extras; never enable two.
- **Build a feature with `/feature`**, which implements to these conventions and then
  runs the `code-reviewer` and `build-judge` subagents.
- **Before declaring anything done, `/check` must pass** (ruff + mypy + pytest).
- **Settings come from `app.core.config.get_settings()`** — never read `os.environ`
  directly in app code.
- **Log via `structlog`** — `app.core.logging.get_logger(__name__)`; no bare
  `print` / `logging`.
- **Model tiers come from settings** (`model_fast` / `model_default` / `model_frontier`).
  Default to the cheapest tier that works; escalate explicitly.
- **Subagents are read-only** — the parent session owns all edits and commits.

## Commands convention
Every command in `.claude/commands/` must have: a one-line `description`, an
`argument-hint`, a first body line that is a concrete usage **example**, and a
verb-first, intent-obvious name. If the set grows beyond ~6, group by namespace folders —
`commands/db/migrate.md` → `/db:migrate`.

## Everyday commands
- Dev server: `just run`  ·  Tests: `just test`  ·  Lint+fix: `just fmt`  ·  Upgrade deps: `just upgrade`

## Template lifecycle
- This service was generated from a Copier template; `.copier-answers.yml` records the link.
- Pull upstream template improvements with `just template-update` (runs `copier update`).
- Do not hand-edit `.copier-answers.yml`; re-run copier to change generation answers.
