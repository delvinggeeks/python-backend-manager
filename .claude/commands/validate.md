---
description: Run the full template CI gate locally (generate + lock + ruff + pytest across the matrix).
allowed-tools: Bash, Read, Glob, Grep
model: claude-sonnet-4-6
---
Delegate to the `template-validator` subagent to validate the current working tree
across the standard matrix: agent_framework ∈ {none, pydantic-ai, langgraph,
openai-agents}, with include_db=true for the first two and false for the rest —
mirroring `.github/workflows/ci.yml`.

Collect its verdicts and present the consolidated table. If anything FAILED, do NOT
fix silently: summarize the failures and ask me whether to fix, showing the likely
offending `.jinja` file for each.
