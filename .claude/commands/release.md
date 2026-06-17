---
description: Validate, then prepare a Conventional-Commit release so CD tags + releases.
argument-hint: <feat|fix|chore> "<summary>"
allowed-tools: Bash(git:*), Bash(uvx:*), Bash(uv:*), Read, Glob, Grep
model: claude-sonnet-4-6
---
Prepare a release of the TEMPLATE. Arguments: $ARGUMENTS ($1 = type, rest = summary).

1. First run `/validate` (or the template-validator) and refuse to proceed if anything fails.
2. Then have the `build-judge` subagent review the staged changes against the acceptance
   criteria for this change and require a PASS.
3. Stage and commit with a Conventional Commit: `$1: <summary>` (use `$1!:` for breaking).
4. Show me `git log --oneline -5` and the diff stat, then STOP and ask before pushing.
   On push to main, `.github/workflows/ci.yml` runs CI then auto-tags + cuts the Release.
Never push without my explicit confirmation.
