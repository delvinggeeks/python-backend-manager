# Changelog

All notable template changes are documented here. Projects pull these via
`copier update`. Versions are git tags (PEP 440), cut automatically on merge to main.

## 0.1.0
- Initial template: uv-managed FastAPI backend, conflicting agent-framework
  extras (pydantic-ai / langgraph / openai-agents), async SQLAlchemy + pgvector,
  structlog, model cascade.
- Layer 1 automation: weekly `uv lock --upgrade` PR + full-stack Renovate.
- Layer 2 automation: Copier template with `copier update` + monthly auto-update PR.
- Template repo CI/CD: matrix generate+test gate, gated auto-tag + GitHub Release, Renovate self-maintenance.
- Claude agent architecture: manager + service .claude/ (subagents, slash commands, settings, ruff hook) and CLAUDE.md operating manuals.
