# Changelog

All notable template changes are documented here. Projects pull these via
`copier update`. Versions are git tags (PEP 440), cut automatically on merge to main.

## Unreleased
### P8 — per-tenant rate limiting & auth-abuse protection (`include_ratelimit`)
An `app/ratelimit` package behind a `RateLimitPort`, off by default; a service without the toggle
renders byte-for-byte unchanged.

- **Atomic Redis token bucket.** One Lua script per decision (`EVALSHA`), so it is correct under
  concurrency across every app instance, has no fixed-window boundary burst (the `2 × limit` a
  fixed window leaks), and no `INCR`/`EXPIRE` race that can strand a key with no TTL. Timed by the
  **Redis server clock** so hosts can't disagree under skew; idle buckets expire, bounding keys.
  This replaces `fastapi-limiter` — ADR-11 records why, and the `ratelimit` extra is now just
  `redis[hiredis]`.
- **Per-tenant, plan-tiered.** `rate_limit()` keys on the organization for org-scoped routes and the
  client IP otherwise, against the route TEMPLATE (bounded key cardinality, not one key per URL).
  With billing on, the budget is the org's plan tier, resolved from its active subscription and
  cached in-process so the hot path stays off Postgres. Over budget → `429` + `Retry-After`.
- **Auth-abuse protection.** Login / refresh carry a tighter per-client throttle, and consecutive
  failed logins lock the identity out — checked *before* the password is verified, so a locked
  identity costs no argon2 hash. Identities are hashed before they reach Redis (no emails in keys).
  The docstring states the targeted-lockout DoS trade-off explicitly rather than hiding it.
- **Fails OPEN everywhere.** No `REDIS_URL`, an unreachable Redis, or any error allows the request;
  a limiter outage must never become a service outage. 250 ms socket timeouts keep a slow Redis off
  the hot path. `RATELIMIT_ENABLED=false` is a full kill switch.
- Enforced by an import-linter contract: app code cannot import the concrete limiter, only the port.
- CI: `ratelimit` (ALONE, no db, no reachable Redis — the degradation path) and `ratelimit_full`
  (+ billing/tenancy/users — plan lookup and the auth wiring).

### Dependency automation
Fixes on the template's **management surface** (root `renovate.json` + root CI), plus the one-line
template fix that was red-lighting the whole capability matrix.

- **`ruff format` on the generated README.** ruff 0.16 — which the template's `ruff>=0.15`
  floor now resolves to — formats Python code blocks inside Markdown. The arq snippet in the
  `include_jobs` README section had three spaces before its trailing comment where ruff wants
  two, so `ruff format --check .` failed on `generate (jobs)`, `generate (jobs_email)` and
  `generate (observability_full)`. That red-lit the required `generate (capability)` check,
  which is why every Renovate PR has been stuck since June. Inside the `include_jobs` gate, so
  services without jobs are byte-identical.
- **Renovate can finally see the template's Python dependencies.** `template/pyproject.toml.jinja`
  is a jinja file, so no built-in manager (pep621 / pip_requirements) ever parsed it — all 75
  lower-bound pins were invisible, and the Dependency Dashboard's "Detected Dependencies" listed
  no pypi manager at all. Added a `customType: regex` custom manager over that one file
  (`datasource: pypi`, `versioning: pep440`) that reads PEP 508 requirement strings: optional
  extras are non-capturing (`uvicorn[standard]` → depName `uvicorn`), dotted/hyphenated names are
  supported, and PEP 440 pre-release floors (`>=0.50b0`) and bare majors (`>=7`) are captured.
- **Python bump policy.** New package rules for `pypi`: a 3-day `minimumReleaseAge` supply-chain
  cooldown (same posture as SHA-pinning the actions — the template's floors propagate into every
  generated service's next `uv lock --upgrade`), auto-merge for minor + patch, and majors held for
  a human via `dependencyDashboardApproval` (they are breaking-change reviews that reach every
  downstream service).
- **One stable required check: `ci-ok`.** Added a summary job to `.github/workflows/ci.yml` that
  aggregates `generate-and-test`, `generate-capability` and `generate (capability)`. It runs with
  `if: always()` and fails unless every gating job reported `success` — a naive `needs:` + `echo`
  job would be *skipped* on failure, and GitHub counts a skipped required check as passing.
  Requiring only `ci-ok` means the matrix can grow without ever editing branch protection, and
  Renovate's `platformAutomerge` has a single deterministic context to wait on.

## 0.1.0
- Initial template: uv-managed FastAPI backend, conflicting agent-framework
  extras (pydantic-ai / langgraph / openai-agents), async SQLAlchemy + pgvector,
  structlog, model cascade.
- Layer 1 automation: weekly `uv lock --upgrade` PR + full-stack Renovate.
- Layer 2 automation: Copier template with `copier update` + monthly auto-update PR.
- Template repo CI/CD: matrix generate+test gate, gated auto-tag + GitHub Release, Renovate self-maintenance.
- Claude agent architecture: manager + service .claude/ (subagents, slash commands, settings, ruff hook) and CLAUDE.md operating manuals.
