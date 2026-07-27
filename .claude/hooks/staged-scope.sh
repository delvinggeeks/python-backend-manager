#!/usr/bin/env bash
# PreToolUse guard: refuse a commit whose staged paths fall outside the declared slice scope.
#
# Why this exists: `git add -A` swept an unrelated doc into one PR and a deliberately-failing test
# into another, in a single session. The lesson could have been "be careful"; being careful is not
# a control. This is.
#
# Declare a slice's scope by writing path prefixes (one per line, '#' comments allowed) to
# .claude/slice-scope. With no such file the guard is inert, so it never blocks ordinary work.
set -euo pipefail

payload=$(cat)
command=$(printf '%s' "$payload" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("command",""))' 2>/dev/null || true)
case "$command" in
  *"git commit"*) ;;
  *) exit 0 ;;
esac

scope_file=".claude/slice-scope"
[ -f "$scope_file" ] || exit 0

mapfile -t prefixes < <(grep -vE '^\s*(#|$)' "$scope_file" || true)
[ "${#prefixes[@]}" -gt 0 ] || exit 0

staged=$(git diff --cached --name-only 2>/dev/null || true)
[ -n "$staged" ] || exit 0

outside=()
while IFS= read -r path; do
  [ -n "$path" ] || continue
  ok=0
  for prefix in "${prefixes[@]}"; do
    case "$path" in "$prefix"*) ok=1; break ;; esac
  done
  [ "$ok" -eq 1 ] || outside+=("$path")
done <<< "$staged"

if [ "${#outside[@]}" -gt 0 ]; then
  {
    echo "BLOCKED: staged paths fall outside the declared slice scope (.claude/slice-scope):"
    printf '  - %s\n' "${outside[@]}"
    echo
    echo "Declared scope:"
    printf '  - %s*\n' "${prefixes[@]}"
    echo
    echo "Stage explicit paths for THIS slice, or widen .claude/slice-scope deliberately."
  } >&2
  exit 2
fi
exit 0
