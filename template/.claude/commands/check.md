---
description: Run all gates — ruff, mypy, pytest.
argument-hint: (no arguments)
allowed-tools: Bash(uv:*), Bash(just:*), Read
model: claude-sonnet-4-6
---
Example: `/check` — runs every gate and reports one line of pass/fail per gate.

Run the full gate: `uv run ruff check .`, `uv run ruff format --check .`,
`uv run mypy src`, then `uv run pytest`. Report a one-line pass/fail per gate.
If anything fails, show the failing output and propose the minimal fix — but ask
before editing.
