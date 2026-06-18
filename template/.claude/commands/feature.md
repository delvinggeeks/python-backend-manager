---
description: Implement a feature end-to-end following project conventions, then self-review.
argument-hint: "<what to build>"
allowed-tools: Read, Glob, Grep, Edit, Write, Bash(uv:*), Bash(just:*)
model: claude-sonnet-4-6
---
Example: `/feature "add a GET /healthz/db endpoint that pings Postgres"`

Implement: $ARGUMENTS

1. Plan briefly: which files under `src/app/` change, and the new test under `tests/`.
2. Implement following CLAUDE.md/AGENTS.md conventions (get_settings, structlog,
   async, model tiers from settings, one agent framework).
3. Add or update a test that covers the change.
4. Run `/check`.
5. Delegate to the `build-judge` subagent for a PASS/FAIL verdict; address any fixes.
6. Stop before committing and show me the diff stat.
