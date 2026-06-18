# CLAUDE.md — python_backend_manager

@AGENTS.md

The conventions and decision rules live in `AGENTS.md` (imported above). This file adds
only the Claude-Code-specific surface for operating this repo — which commands and
subagents exist. No rules are duplicated here; if something here ever disagrees with
`AGENTS.md`, `AGENTS.md` wins.

## Commands
- `/scaffold <service-name> [framework] [--no-db]` — generate a service into a sibling dir.
- `/validate` — run the full template CI gate locally across the matrix.
- `/audit-deps` — audit dependency freshness + risk (AI stack gets extra scrutiny).
- `/release <feat|fix|chore> "<summary>"` — validate, then prepare a Conventional-Commit release.

## Subagents (read-only analysts)
- `template-validator` — generate + lock + ruff + mypy + pytest a matrix entry; verdict.
- `build-judge` — PASS/FAIL a change against acceptance criteria; emits a next prompt.
- `dependency-auditor` — flag outdated / risky deps, extra scrutiny on the AI stack.
- `docs-researcher` — verify latest library versions / Claude Code conventions from the web.
