---
description: Audit dependency freshness + risk (AI stack gets extra scrutiny).
argument-hint: (no arguments)
allowed-tools: Bash, Read, Glob, Grep, WebFetch, WebSearch
model: claude-sonnet-4-6
---
Example: `/audit-deps` — audits the template's pins + a fresh lockfile, AI stack first.

Delegate to the `dependency-auditor` subagent. Have it inspect the template's pins
and a freshly generated lockfile, then report SAFE-TO-BUMP vs REVIEW-REQUIRED.

After it reports, summarize for me in two lines and ask whether to (a) bump safe
pins in the relevant `.jinja`/config files, or (b) leave it to Renovate.
