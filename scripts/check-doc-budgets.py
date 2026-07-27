#!/usr/bin/env python3
"""Fail when an always-read document exceeds its committed line budget.

The always-read set is a tax on every session's context window. Left ungoverned it only grows,
because every individual addition looks small. This gate makes growth explicit: exceed the budget
and CI fails; the fix is either to cut the file or to raise the number in `.doc-budgets.toml` in the
same pull request, where a reviewer sees the raise as the decision it is.
"""

from __future__ import annotations

import sys
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".doc-budgets.toml"


def main() -> int:
    budgets = tomllib.loads(CONFIG.read_text())["budgets"]
    failures: list[str] = []
    for name, budget in sorted(budgets.items()):
        path = ROOT / name
        if not path.exists():
            failures.append(f"{name}: budgeted but missing")
            continue
        actual = len(path.read_text().splitlines())
        headroom = budget - actual
        status = "OK  " if headroom >= 0 else "OVER"
        print(f"  {status} {name:36} {actual:>4} / {budget:<4} ({headroom:+d})")
        if headroom < 0:
            failures.append(f"{name}: {actual} lines exceeds its budget of {budget} by {-headroom}")

    if failures:
        print("\nDOC BUDGET EXCEEDED:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        print(
            "\nEvery session reads these files in full. Either cut the file, or raise its budget\n"
            "in .doc-budgets.toml in this same PR so the growth is reviewed rather than absorbed.",
            file=sys.stderr,
        )
        return 1
    print("\nall always-read documents are within budget")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
