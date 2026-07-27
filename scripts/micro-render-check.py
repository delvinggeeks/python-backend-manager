#!/usr/bin/env python3
"""Render staged `*.py.jinja` templates with every gated block OFF and format-check the result.

WHY THIS EXISTS — a failure class, not a style nit. A construct can be valid when a `{% if %}`
block renders and malformed when it does not, so the template looks fine and only *one particular
capability combination* breaks. Five instances in one session:

  1. a separator newline left outside `{% if %}` -> trailing blank line at EOF (test_route_auth)
  2. the same, in test_audit
  3. blank lines on both sides of a block -> four blank lines when the block is absent (logging)
  4. isort wants ONE blank line after imports before an assignment and TWO before a `def`, so the
     correct count DIFFERS between renders (logging) — no amount of care fixes this one
  5. `X: dict = {` + `}` across a gated body -> `{\\n}` when empty, where ruff wants `{}`

WHAT THIS IS — a **fast-feedback shortcut**, deliberately not a complete gate. It renders exactly
one combination: everything off. Instance 4 above is only caught in *some* combinations, and a
defect that needs two flags on and one off is invisible here. **The leg matrix remains the complete
gate for this class**; this hook exists to catch the common case in two seconds instead of twenty
minutes, not to replace it.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from jinja2 import ChainableUndefined, Environment
except ImportError:  # pragma: no cover - the hook env always provides it
    print("micro-render-check: jinja2 unavailable; skipping", file=sys.stderr)
    raise SystemExit(0) from None

# Mirrors copier.yml's _envops, so a render here matches what copier produces.
# keep_trailing_newline matters: jinja drops the final newline by default, which makes EVERY
# rendered file look unformatted. Mirrors copier.yml's _envops otherwise.
ENV = Environment(
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
    undefined=ChainableUndefined,
    autoescape=False,
)


def render_all_off(source: str) -> str | None:
    """Render with every variable undefined — falsy, so all gated blocks are absent."""
    try:
        return ENV.from_string(source).render()
    except Exception:
        # A template that cannot render standalone (macros, includes) is out of scope for a
        # shortcut check; the leg matrix covers it.
        return None


def main(paths: list[str]) -> int:
    # A file inside a gated DIRECTORY (e.g. "{% if include_audit %}audit{% endif %}/x.py.jinja")
    # is only ever rendered when that gate is true, so checking it with everything off tests a
    # combination copier can never produce. Skip them; the leg matrix covers those paths.
    targets = [
        Path(p) for p in paths if p.endswith(".py.jinja") and "{%" not in p
    ]
    if not targets:
        return 0

    failures: list[str] = []
    for path in targets:
        rendered = render_all_off(path.read_text())
        if rendered is None:
            continue
        with tempfile.TemporaryDirectory() as tmp:
            probe = Path(tmp) / "rendered.py"
            probe.write_text(rendered)
            # BOTH checks are required, and this was learned the hard way: recorded instance #4
            # (blank lines after the import block) is an isort I001 finding, NOT a formatter
            # finding — `ruff format` has no opinion on it. A hook running only the formatter
            # silently misses the very case that no amount of care can prevent.
            fmt = subprocess.run(
                ["ruff", "format", "--check", "--line-length", "100", str(probe)],
                capture_output=True,
                text=True,
            )
            lint = subprocess.run(
                [
                    "ruff",
                    "check",
                    "--select",
                    "I,E501,W291,W293",
                    "--line-length",
                    "100",
                    # The probe lives in a temp dir with no project config, so isort would treat
                    # `app` as third-party and report every file as un-sorted. Mirror the
                    # template's own [tool.ruff] src setting instead.
                    "--config",
                    'lint.isort.known-first-party = ["app"]',
                    str(probe),
                ],
                capture_output=True,
                text=True,
            )
            if fmt.returncode != 0 or lint.returncode != 0:
                detail = "".join(
                    f"      {line}\n"
                    for line in (fmt.stdout.splitlines()[:6] + lint.stdout.splitlines()[:6])
                    if line.strip()
                )
                failures.append(
                    f"{path}\n"
                    f"    with every gated block OFF, the render is not clean:\n{detail}"
                )

    if failures:
        print("\nMICRO-RENDER CHECK FAILED\n", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        print(
            "  A gated block that renders EMPTY changed the surrounding syntax. Move the blank-line\n"
            "  separators INSIDE the {% if %}, so both renders are well-formed.\n\n"
            "  This is a fast-feedback shortcut over the all-off combination only — the leg matrix\n"
            "  is the complete gate for this class.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
