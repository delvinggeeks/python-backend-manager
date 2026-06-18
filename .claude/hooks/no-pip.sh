#!/usr/bin/env bash
# PreToolUse(Bash) hook: block raw pip installs — this repo manages deps with uv.
# Reads the tool-call JSON from stdin and, when the command actually invokes pip to
# install, emits a deny decision so the call never runs. Invoked as `bash .../no-pip.sh`
# so a missing exec bit can't silently disable it. Never blocks anything else.
input=$(cat)
cmd=$(printf '%s' "$input" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))" 2>/dev/null)

# Match pip/pip3/`python -m pip`/`uv pip` + install, but only at COMMAND POSITION —
# start of the command or just after a separator (newline, ;, |, &, &&, ||), with an
# optional `sudo`. This blocks real invocations (`pip install x`, `cd y && pip install
# x`, `uv pip install x`) while NOT tripping on the phrase inside a quoted string (a
# commit -m / echo / doc), and leaves read-only `uv pip list` alone.
if printf '%s' "$cmd" | grep -Eq '(^|[;&|]|&&|\|\|)[[:space:]]*(sudo[[:space:]]+)?(uv[[:space:]]+pip|pip3?|python3?[[:space:]]+-m[[:space:]]+pip)[[:space:]]+install'; then
  cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Use `uv add` instead of pip — this repo manages dependencies with uv (a raw pip install does not update pyproject.toml / uv.lock). Try `uv add <pkg>`, `uv add --optional <extra> <pkg>`, or `uv add --dev <pkg>`."}}
JSON
  exit 0
fi
exit 0
