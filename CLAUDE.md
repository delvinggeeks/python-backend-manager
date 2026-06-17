# CLAUDE.md — operating manual for the python_backend_manager repo

This repo is a **Copier template** that produces self-maintaining FastAPI backends.
You (Claude Code) operate it through the agents, commands, and settings in `.claude/`.

## What this repo is — and is NOT
- `template/` is the **body** that gets rendered into each generated service. Files
  ending in `.jinja` are rendered; everything else is copied verbatim.
- The repo **root** is the template's own management surface (CI/CD, Renovate, docs).
- **Never build a service inside this repo.** Services are generated into sibling
  directories (e.g. `~/Desktop/<service>`) via Copier, then evolved there.

## Golden rules
1. To create a service: use `/scaffold` (it runs `copier copy` into a sibling dir).
   Never hand-copy files.
2. One agent framework per service: `pydantic-ai` | `langgraph` | `openai-agents`.
   They cannot co-resolve — never enable two.
3. Before pushing template changes, run `/validate` — it generates projects across
   the matrix and runs lock + ruff + pytest, exactly like CI does.
4. Commit with Conventional Commits (`feat:` / `fix:` / `chore:`; `feat!:` = major).
   CD tags + releases automatically on merge to `main`.
5. Keep `template/src/**/*.py` ruff-clean and formatted (a PostToolUse hook does this).
6. Two automation layers exist; don't confuse them:
   - Dependency freshness: `uv lock --upgrade` + Renovate (per service + this repo).
   - Template propagation: `copier update` (pulls template changes into services).

## Delegate to subagents (read-only analysts)
- `template-validator` — generate + lock + ruff + pytest a matrix entry; verdict.
- `build-judge` — PASS/FAIL a change against acceptance criteria; emits a ready-to-paste next prompt.
- `dependency-auditor` — flag outdated / risky deps, with extra scrutiny on the AI stack.
- `docs-researcher` — verify latest library versions or Claude Code conventions from the web.

The parent session owns all edits, commits, and pushes; subagents only read + report.

## Where to look
- `copier.yml` — the questions and computed extras.
- `template/AGENTS.md` — conventions that ship INTO each generated service.
- `README.md` — full pipeline + GitHub setup.
