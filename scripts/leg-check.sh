#!/usr/bin/env bash
# The single definition of "a capability leg passed".
#
# CI invokes this script; so does local validation. That is the whole point: when the two are
# separate lists of commands they drift, and the drift is only discovered when CI rejects a change
# that passed locally. Adding a gate here adds it to both at once.
#
# Usage:  scripts/leg-check.sh <generated-project-dir> [uv sync extras...]
#   e.g.  scripts/leg-check.sh /tmp/generated --extra db --extra users
set -euo pipefail

project="${1:?usage: leg-check.sh <generated-project-dir> [extras...]}"
shift || true

# --- refuse a dirty worktree -----------------------------------------------------------------
# `copier --vcs-ref HEAD` renders UNCOMMITTED edits, so a leg-check on a dirty tree validates
# something the commit does not contain — the exact "passed locally, failed CI" class this script
# exists to eliminate. Set LEG_CHECK_ALLOW_DIRTY=1 to override deliberately.
if [ -z "${LEG_CHECK_ALLOW_DIRTY:-}" ] && git -C "$(dirname "$0")/.." rev-parse --git-dir >/dev/null 2>&1; then
  dirty=$(git -C "$(dirname "$0")/.." status --porcelain --untracked-files=no)
  if [ -n "$dirty" ]; then
    echo "REFUSING: the template worktree is dirty, so --vcs-ref HEAD would render uncommitted" >&2
    echo "edits that the commit does not contain. Commit first, or set LEG_CHECK_ALLOW_DIRTY=1." >&2
    printf '%s\n' "$dirty" >&2
    exit 2
  fi
fi

# --- per-run isolation -------------------------------------------------------------------------
# The generated conftest keys its sqlite file off the project SLUG, which is identical across
# renders, and run_fuzz.sh binds a fixed default port. CI never contends for either (one leg per
# runner), but any local harness running legs concurrently does. Derive both from the project
# directory so no caller has to remember.
project_id=$(printf '%s' "$project" | cksum | cut -d' ' -f1)
export TMPDIR="${TMPDIR_OVERRIDE:-${project}/.leg-tmp}"
mkdir -p "$TMPDIR"
export FUZZ_PORT="${FUZZ_PORT:-$(( 20000 + project_id % 20000 ))}"

cd "$project"

step() { printf '\n\033[1m── %s ──\033[0m\n' "$1"; }

step "git init (copier needs a committed tree; uv needs a project root)"
if [ ! -d .git ]; then
  git init -q
  git add -A
  git -c user.email=ci@local -c user.name=ci commit -qm "ci: generated"
fi

step "lock + sync${*:+ ($*)}"
uv lock
uv sync "$@"

step "ruff check";        uv run ruff check .
step "ruff format";       uv run ruff format --check .
step "mypy";              uv run mypy src
step "vulture";           uv run vulture src
step "xenon";             uv run xenon --max-absolute C --max-modules C --max-average B src
step "import-linter";     uv run lint-imports
step "interrogate";       uv run interrogate src

step "pytest"
# Any leg that RENDERS the cross-tenant isolation suite must RUN it: REQUIRE_DB_TESTS turns an
# unavailable container into a failure instead of a silent skip. Keyed off the rendered file, so a
# new rls-bearing capability row is covered automatically.
if [ -f tests/test_rls.py ]; then export REQUIRE_DB_TESTS=1; fi
uv run pytest

step "OpenAPI fuzz gate"
bash scripts/run_fuzz.sh

step "alembic round-trip"
# Only db-backed services render alembic.ini; a db-less capability has no migrations to round-trip.
if [ -f alembic.ini ]; then
  export DATABASE_URL="sqlite+aiosqlite:///$PWD/alembic_ci.sqlite3"
  uv run alembic upgrade head
  uv run alembic downgrade base
else
  echo "no alembic.ini (db-less capability) — skipping migration round-trip"
fi

printf '\n\033[1;32mLEG PASSED\033[0m: %s\n' "$project"
