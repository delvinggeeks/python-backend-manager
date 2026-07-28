#!/usr/bin/env bash
# PostToolUse hook: format an edited Python file with ruff. Never blocks.
#
# THE VERSION IS THE POINT, so it comes first. This hook EDITS files that a capability leg's
# `ruff format --check` then JUDGES, so a hook running a different ruff manufactures the exact
# "passed locally, CI disagrees" class scripts/leg-check.sh exists to eliminate — and it does so in
# regions the session never touched, which puts changes nobody chose into the diff a reviewer reads.
# Measured (FMT-1): `uv run ruff format` and a bare `ruff format` BOTH resolved 0.4.10 here — the
# manager repo has no Python project, so the first arm fell through to the same PATH binary — while
# generated projects run 0.16.0. Driving this hook at tests/test_rls.py rewrote an assert ~75 lines
# from any edit into 0.4.10's pre-parenthesized-message style, and the rendered tenancy leg then
# failed `ruff format --check` on precisely that assert.
#
# So: exactly ONE place records the ruff version — `.ruff-version` at the repo root — and both this
# hook and ci.yml's `repo-lint` job read it. Resolving whatever ruff is on PATH is ruled out. When
# the pinned ruff cannot be fetched the file is left ALONE and the session is told, because an
# unformatted file is a loud CI failure while a wrongly-formatted one is a silent bad diff.
#
# Matches *.py* (not just *.py) so it also formats the template's *templated* Python, which is what
# services would otherwise hand-flatten after every build:
#   - gated filenames, e.g. tests/{% if include_billing %}test_billing.py{% endif %}
#     (the body is valid Python; the jinja lives only in the filename)
#   - *.py.jinja and {% ... %}NAME.py{% endif %}.jinja module/migration files whose body is
#     valid Python (jinja only inside string literals)
# ruff parses each file: bodies that are valid Python get formatted at the repo's line-length=100
# (root ruff.toml); files with *structural* inline jinja (e.g. core/config.py.jinja, where bare
# {% if %} lines aren't valid Python) fail to parse, so ruff exits non-zero and the file is left
# untouched. The hook never blocks an edit.
# (.claude/ is outside template/, so this script is never itself rendered by copier.)
set -uo pipefail

input=$(cat)
file=$(printf '%s' "$input" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null)
case "$file" in
  *.py*) ;;
  *) exit 0 ;;
esac
[ -f "$file" ] || exit 0

# Resolved from this script's own location rather than the cwd, so the pin is found whatever
# directory the session is working in.
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
pin_file="$repo_root/.ruff-version"
# Guarded rather than redirect-and-suppress: a `<"$pin_file"` on a missing file is reported by the
# SHELL, not by tr, so a `2>/dev/null` on the command does not silence it and the session gets a
# raw "No such file or directory" ahead of the hook's own message.
ruff_version=""
[ -r "$pin_file" ] && ruff_version=$(tr -d '[:space:]' <"$pin_file")

if [ -z "$ruff_version" ]; then
  echo "ruff-format hook: no ruff version recorded in $pin_file — '$file' left unformatted." >&2
  exit 0
fi

if ! uvx "ruff@${ruff_version}" format "$file" >/dev/null 2>&1; then
  # ruff exits non-zero on a file it cannot PARSE — the structurally-jinja templates above — and
  # that is the designed no-op. It exits non-zero just the same when uvx cannot fetch ruff at all,
  # and THAT case must not pass silently, since the file is then left unformatted for CI to reject.
  # The probe runs only on the failure path, and uvx caches, so the common case pays nothing.
  if ! uvx "ruff@${ruff_version}" --version >/dev/null 2>&1; then
    echo "ruff-format hook: cannot run ruff ${ruff_version} (uvx offline or unavailable)" >&2
    echo "  '$file' was left unformatted rather than formatted by some other ruff." >&2
  fi
fi
exit 0
