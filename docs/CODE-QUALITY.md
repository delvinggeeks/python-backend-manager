# CODE-QUALITY.md — quality, security, coverage & deterministic-code gates

> How the platform guarantees **best-in-class, deterministic, high-assurance code** — the gate set
> that makes "the goal is achieved" *verifiable*, not asserted. Extends the security gates in
> [CICD-PIPELINE.md](CICD-PIPELINE.md) and the per-phase Definition-of-Done in [SDLC.md](SDLC.md);
> it's the quality half of ROADMAP **P2** (applied template-wide so every phase inherits it).
> Researched 2025-2026, cited; decision recorded as [LIBRARY-DECISIONS.md](LIBRARY-DECISIONS.md) ADR-36.

---

## 1. The baseline (already enforced today)

The template is **~80% there** before any addition: **`ruff`** (lint + format, 800+ rules), **`mypy
--strict`**, **`pytest` + `coverage.py`** (`--cov-fail-under`), pre-commit, the **`generate
(capability)` CI gate** across the framework × db × capability matrix, **byte-identity deterministic
rendering**, and **`uv.lock`** pinned deps. This doc closes the remaining 20% — the parts that make
quality *measured and gated*, and code *deterministic*.

---

## 2. Decision: the Python-native quality stack beats SonarQube (for this scope)

SonarQube **Community lacks PR/branch analysis** (main-branch only), its Python SAST is weaker than
ruff+bandit, and the **Developer Edition is $15-25k/yr** — ops + cost overhead a bootstrapped team
shouldn't carry, and it sends code to a server (DPDP friction). The **native stack covers every
SonarQube-Community capability and more** (dead-code, architecture boundaries, docstrings) at ₹0,
self-hosted, with sub-1% false positives. **SonarQube is a documented seam at ~50+ devs / regulated
audit.** (ADR-36, no founder fork needed — the default is clear.)

---

## 3. The quality stack (BUILD-NOW — additive dev-deps + CI gate steps)

| Tool | Gate | Why |
|---|---|---|
| **ruff** (have) — incl. **`S`** (bandit security) + **`I`** (imports) rule groups | lint + format + Python SAST | one fast tool; `S` rules = hardcoded secrets / SQLi / unsafe-deserialize |
| **mypy --strict** (have) | type safety enforced | production-grade types; the strongest correctness lever |
| **vulture** | **dead-code** (≥80% confidence) | no orphaned code rots in |
| **radon / xenon** | **cyclomatic + cognitive complexity** + maintainability index | block over-complex functions (e.g., fail on grade > C) |
| **import-linter** | **architecture boundaries** | *enforces the ports-and-adapters discipline in CI* — adapters can't import the domain; the agent framework can't leak; this is the standout add |
| **interrogate** | **docstring coverage** (≥80%) | public API stays documented |
| **coverage.py** (have) + **`coverage combine`** / **Codecov** free-tier | **total + per-PR diff/patch coverage**, **branch coverage** | new code must be tested, not just the total |

**Concrete quality gate (blocks the PR):** coverage ≥ threshold (total + **patch coverage on the
diff**), branch coverage on, complexity ≤ grade C, dead-code = 0, **import-linter contracts pass**,
docstring ≥ 80%, ruff (incl. `S`) + mypy-strict clean. These slot into the existing
`generate (capability)` gate as steps — **no new required check, no restructuring**.

---

## 4. Test effectiveness (beyond coverage %) — measuring whether tests *work*

Coverage proves lines *ran*, not that they're *checked*. Add:

- **Property-based testing — `Hypothesis`** (BUILD-NOW): assert **invariants** on critical modules —
  money/`Decimal` round-trips, **idempotency** (`f(f(x)) == f(x)`), serialization symmetry, RLS
  isolation. ~3 invariant tests/critical module; runs inside existing pytest, ~0 CI overhead.
- **API fuzzing — `Schemathesis`** (BUILD-NOW): generate positive/negative/malformed cases **from the
  service's own `/openapi.json`** (finds 5xx, injection, path-traversal); one full-schema pass per
  release / on API changes (~2-3 min).
- **Mutation testing — `mutmut`** (SEAM-NOW): the real test-quality metric — does the suite *kill*
  injected bugs? Full-suite is too slow for the matrix, so gate it **on changed files + 2-3 critical
  modules only** (payments/auth/core ports), risk-based thresholds (payments ≥95%), **informational
  (non-blocking) on PR**, ~10-15 min when triggered.
- **Fuzzing — `atheris`** (SEAM-NOW): coverage-guided fuzz on parsers (webhook signature verify,
  Pydantic deserialization, upload blobs).

---

## 5. Deterministic & reproducible code (the "deterministic goal" made real)

Determinism here is twofold — *deterministic tests* and *reproducible builds*:

- **Test-order determinism — `pytest-randomly`** (BUILD-NOW): shuffles order every run with a captured
  seed → surfaces order-dependence / shared-state leaks. Main path runs a fixed seed (deterministic);
  a **nightly** job runs a full shuffle to flush latent flakes.
- **Time/uuid/randomness frozen — `freezegun` + `pytest-freezegun` / `time-machine`** (BUILD-NOW):
  every datetime-dependent path (token expiry, subscriptions, webhook backoff, idempotency windows) is
  tested against frozen time — no wall-clock nondeterminism. (Mirrors the template's existing ban on
  `Date.now()`/`random()` in workflow scripts.)
- **Flaky-test quarantine** (SEAM-NOW): track attempt-level reruns (`pytest-rerunfailures`/Mergify);
  **quarantine, never hide** — keep the signal visible.
- **Reproducible/hermetic builds** (BUILD-NOW, minimal): `uv.lock` (have) + **`SOURCE_DATE_EPOCH`**
  (from the commit timestamp) + **Docker base pinned by digest** (not tag) + BuildKit → byte-stable
  images. Pairs with the **byte-identity render** (already a determinism proof of the *template*) and
  the **SBOM + Sigstore signing** (P2) → **SLSA-2** provenance now, SLSA-4 reproducibility later.

**Why this yields "deterministic code that achieves the spec":** order-independent + time-frozen +
invariant-checked + mutation-killed + reproducibly-built means a green pipeline is a *reliable* signal
that the code does what the spec says — every run, every machine, every rebuild. Determinism ≠
correctness, but it removes the nondeterminism that hides incorrectness.

---

## 6. Fit with the existing CI — no restructuring

- **New dev-deps** (template `pyproject.toml.jinja`): `vulture`, `radon`/`xenon`, `import-linter`,
  `interrogate`, `hypothesis`, `schemathesis`, `pytest-randomly`, `freezegun`+`pytest-freezegun`,
  `time-machine` (Hypothesis/randomly/freezegun run *inside* the existing pytest — zero new jobs).
- **New gate steps** in the matrix legs: vulture / radon / import-linter / interrogate / coverage
  patch-gate — added to `generate (capability)`; the aggregated gate already covers them.
- **Optional informational jobs**: a `mutmut` (critical modules, on PR) job and a nightly
  `pytest-randomly --seed=0` flaky-sweep — non-blocking, don't touch branch protection.
- **Generated services inherit all of it** — these gates render into each service's CI, so every
  backend built from the template ships the same quality+determinism floor.

---

## 7. BUILD-NOW vs SEAM-NOW

| Item | Verdict | Cost |
|---|---|---|
| ruff `S`/`I` + mypy-strict + coverage (have) | ✅ shipped | ₹0 |
| vulture · radon/xenon · **import-linter** · interrogate + patch-coverage gate | **BUILD-NOW** | ₹0, ~0 CI time |
| Hypothesis invariants · Schemathesis (OpenAPI fuzz) | **BUILD-NOW** | ₹0, ~min |
| pytest-randomly · freezegun/time-machine | **BUILD-NOW** | ₹0 |
| SOURCE_DATE_EPOCH + digest-pinned image (reproducible build) | **BUILD-NOW** | ₹0 |
| mutmut mutation gate (critical modules) · atheris fuzz | **SEAM-NOW** | ~10-15 min on PR |
| Codecov / Coveralls PR decoration | **SEAM-NOW** | free tier → $/multi-repo |
| **SonarQube** (Community→Developer) | **deferred** (≥50 devs / audit) | $15-25k/yr |
| SLSA-2 SBOM+Sigstore (in P2) · SLSA-4 reproducibility | ✅ P2 / **SEAM** | ₹0 / effort |

---

## 8. Where it lives in the roadmap & gates

This is the **quality+determinism half of P2** (the security half — SBOM/scan/sign/SHA-pin/ingress —
is already in P2). It's *template-wide*, not a single capability: the gates apply to every phase via
the CI matrix, and each phase's [SDLC.md](SDLC.md) Definition-of-Done already requires "tests +
coverage + security gates green" — this doc makes that concrete (patch-coverage, complexity,
architecture-boundary, invariant, determinism). Traced in [TRACEABILITY.md](TRACEABILITY.md) as the
`ci_gate` named on every phase row; recorded as ADR-36; audited under
[COMPLETENESS-AUDIT.md](COMPLETENESS-AUDIT.md) §K.
