#!/usr/bin/env bash
# PostToolUse hook: format an edited Python file with ruff. Never blocks.
#
# Matches *.py* (not just *.py) so it also formats the template's *templated* Python, which
# is what services would otherwise hand-flatten after every build:
#   - gated filenames, e.g. tests/{% if include_billing %}test_billing.py{% endif %}
#     (the body is valid Python; the jinja lives only in the filename)
#   - *.py.jinja and {% ... %}NAME.py{% endif %}.jinja module/migration files whose body is
#     valid Python (jinja only inside string literals)
# ruff parses each file: bodies that are valid Python get formatted at the repo's
# line-length=100 (root ruff.toml); files with *structural* inline jinja (e.g.
# core/config.py.jinja, where bare {% if %} lines aren't valid Python) fail to parse, so ruff
# exits non-zero and the `|| true` leaves them untouched. The hook never blocks an edit.
# (.claude/ is outside template/, so this script is never itself rendered by copier.)
input=$(cat)
file=$(printf '%s' "$input" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null)
case "$file" in
  *.py*)
    if [ -f "$file" ]; then
      uv run ruff format "$file" >/dev/null 2>&1 || ruff format "$file" >/dev/null 2>&1 || true
    fi
    ;;
esac
exit 0
