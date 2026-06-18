---
description: Generate a new backend service from this template into a sibling directory.
argument-hint: <service-name> [agent_framework] [--no-db]
allowed-tools: Bash(uvx copier:*), Bash(git:*), Bash(uv:*), Bash(just:*), Read, Glob
model: claude-sonnet-4-6
---
Example: `/scaffold billing-svc pydantic-ai`  ·  `/scaffold worker-svc none --no-db`

Scaffold a new service from this template. Arguments: $ARGUMENTS
- $1 = service name (kebab-case, required)
- $2 = agent framework: pydantic-ai | langgraph | openai-agents | none (default pydantic-ai)
- include `--no-db` to skip Postgres/pgvector.

Steps:
1. Refuse if $1 is empty; ask for a name.
2. Target dir = `../$1` relative to this repo (a SIBLING, never inside template/).
3. Run:
   `uvx copier copy --defaults --data project_name="$1" --data agent_framework="${2:-pydantic-ai}" --data include_db=<true unless --no-db> . ../$1`
4. `cd ../$1 && git init -q && git add -A && git commit -qm "chore: scaffold from python_backend_manager"`
5. `uv lock` then `uv sync` with the chosen extras (read the generated Justfile's `setup` recipe to get the exact extras).
6. Run `just check` (or `uv run ruff check . && uv run pytest`) and report green/red.
7. Print the path and the next command to start the dev server.
Do not push or create a GitHub repo unless I ask.
