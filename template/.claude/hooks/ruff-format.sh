#!/usr/bin/env bash
# PostToolUse hook: format an edited Python file with ruff. Never blocks.
input=$(cat)
file=$(printf '%s' "$input" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null)
case "$file" in
  *.py)
    if [ -f "$file" ]; then
      uv run ruff format "$file" >/dev/null 2>&1 || ruff format "$file" >/dev/null 2>&1 || true
    fi
    ;;
esac
exit 0
