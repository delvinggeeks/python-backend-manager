# Changelog

All notable template changes are documented here. Projects pull these via
`copier update`. Versions are git tags (PEP 440), cut automatically on merge to main.

## Unreleased
Dependency-automation fixes on the template's **management surface** (root `renovate.json`
+ root CI). Nothing under `template/` changed, so no tag is cut and there is nothing for a
downstream `copier update` to pull — but every future Python bump now reaches the template.

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
