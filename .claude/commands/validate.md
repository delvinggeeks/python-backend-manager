---
description: Run the full template CI gate locally (generate + lock + ruff + mypy + pytest across the matrix).
argument-hint: (no arguments)
allowed-tools: Bash, Read, Glob, Grep
model: claude-sonnet-4-6
---
Example: `/validate` — generates the full matrix and runs the CI gate on each.

Delegate to the `template-validator` subagent to validate the current working tree
across the standard matrix: agent_framework ∈ {none, pydantic-ai, langgraph,
openai-agents}, with include_db=true for the first two and false for the rest —
mirroring `.github/workflows/ci.yml`. The gate includes `uv run mypy src` (now
blocking, like CI) alongside lock + ruff + pytest.

Collect its verdicts and present the consolidated table. If anything FAILED, do NOT
fix silently: summarize the failures and ask me whether to fix, showing the likely
offending `.jinja` file for each.
