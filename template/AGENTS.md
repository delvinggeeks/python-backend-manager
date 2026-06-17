# AGENTS.md — conventions for AI coding agents in this repo

## Stack
- Python 3.13, managed entirely by **uv**. Never call `pip` directly; use `uv add`, `uv sync`, `uv run`.
- Web: FastAPI + Pydantic v2. Async-first. JSON via `ORJSONResponse`.
- Layout: `src/app` (app factory in `app.main:app`), tests in `tests/`.

## Rules
- Add a dependency: `uv add <pkg>` (core) or `uv add --optional <extra> <pkg>`; dev tools via `uv add --dev <pkg>`. Commit the resulting `uv.lock`.
- Pick **one** agent framework per service: `pydantic-ai`, `langgraph`, or `openai-agents`. They are declared as conflicting extras — do not enable two.
- Run every gate before declaring done: `just check` (ruff + mypy + pytest).
- Settings come from `app.core.config.get_settings()` — never read `os.environ` directly in app code.
- Use `structlog` via `app.core.logging.get_logger(__name__)`; no bare `print`/`logging`.
- Model tiers come from settings (`model_fast` / `model_default` / `model_frontier`). Default to the cheapest tier that works; escalate explicitly.

## Commands
- Dev server: `just run`  ·  Tests: `just test`  ·  Lint+fix: `just fmt`
- Upgrade deps: `just upgrade` (writes a new `uv.lock`).

## Template lifecycle
- This project was generated from a Copier template; `.copier-answers.yml` records the link.
- To pull upstream template improvements: `just template-update` (runs `copier update`).
- Do not hand-edit `.copier-answers.yml`. Re-run copier to change generation answers.
