# BUILD-SYSTEM.md — the agentic build & assurance system

> *How* the spec gets built into the platform with maximum rigor — the multi-gate, adversarially-
> reviewed, agent-orchestrated execution system, using Claude Code's actual architecture (parent
> session + read-only analyst subagents + the Workflow orchestrator + skills + the CI gate). This is
> the *executor* of [SDLC.md](SDLC.md) (the process), [CODE-QUALITY.md](CODE-QUALITY.md) (the gates),
> [TRACEABILITY.md](TRACEABILITY.md) (the trace), and [ROADMAP.md](ROADMAP.md) (the work). Inherits
> [PRINCIPLES.md](PRINCIPLES.md). Nothing is built until the founder approves the spec (D1-D18).

---

## 0. Honest framing — what "100% quality" means

Literal 100% (every input, zero defects, proven correct) is unachievable and claiming it is the
opposite of rigor. What this system delivers is **100% gate-pass under defense-in-depth**: every phase
clears *every* gate, and the gates are layered so a defect must survive types **and** architecture
**and** invariants **and** mutation **and** the edge matrix **and** an adversarial review panel to
reach `main`. That makes shipping a defect *expensive and unlikely*, and makes a green pipeline a
**reliable** signal that the phase achieves its spec. **Rigor is scaled to risk** (P9): a money/security
phase (P7 metering, P29 agent-safety, P15 PII, P30 crypto) gets the full adversarial panel; a small
doc/convention phase gets the light path. Over-reviewing a trivial phase is as wrong as under-reviewing
a critical one.

---

## 1. The two roles (Claude architecture, non-negotiable)

- **Parent session = the Builder.** It is the *only* thing that edits/commits (the repo's standing rule:
  *subagents are read-only; the parent owns all edits, commits, pushes*). It plans, writes the code
  behind the toggle, runs `/validate`, fixes findings, commits, opens the PR, arms auto-merge, reports.
- **Subagents / Workflow = the Assurance system** — *read-only* analysts that **plan, validate, review,
  and judge**, returning findings/verdicts the parent acts on. They never edit. This separation is what
  makes the review *independent* (a reviewer that can also fix has an incentive to wave its own work
  through).

---

## 2. The phase-build pipeline — 7 gates, one `feat:` PR

```mermaid
flowchart LR
    G0[G0 READY\nplan from spec\n→ design+RTM+threat+tests] --> G1[G1 BUILD\nparent edits\nbehind toggle]
    G1 --> G2[G2 QUALITY\nruff·mypy-strict·import-linter\ncomplexity·dead-code·patch-cov]
    G2 --> G3[G3 TEST+EDGE\nunit/integration/contract\n+Hypothesis+Schemathesis\n+EDGE MATRIX +/verify]
    G3 --> G4[G4 SKEPTICAL REVIEW\nN adversarial reviewers\n(diverse lenses) + build-judge]
    G4 -->|findings| G1
    G4 --> G5[G5 DoD+TRACE\nRTM 100% · diagrams\n· runbook · SLO]
    G5 --> G6[G6 MERGE\nsquash exact title\n→ CD tags → report]
    classDef g fill:#1168bd,color:#fff,stroke:#0b4884; class G0,G1,G2,G3,G4,G5,G6 g;
```

Each gate **blocks**; a failure at G2-G5 loops back to G1 (fix) and re-runs. The loop continues until
every gate is green — *that* is "completely achieved."

---

## 3. The gates — who runs them, what passes

| Gate | Run by | Passes when |
|---|---|---|
| **G0 · Ready** | **Plan agent** + **`docs-researcher`** (reads `docs/` spec) → parent | Phase requirements + acceptance criteria (Given/When/Then), C4/sequence/ER design, STRIDE threat model, RTM rows, and a **use-case + edge-case test plan** exist (the SDLC DoR). Risk tier chosen. |
| **G1 · Build** | **Parent session** | Code behind its toggle; **byte-identity OFF**; follows the spec's port/adapter shape; no spec-drift. |
| **G2 · Quality** | **`/validate`** + **`template-validator`** (read-only, parallel matrix) | The full local CI gate + the [CODE-QUALITY.md](CODE-QUALITY.md) stack green: ruff(+`S`/`I`), mypy-strict, **import-linter** (architecture), radon/xenon (complexity), vulture (dead code), interrogate (docstrings), **per-PR patch coverage**. |
| **G3 · Test + edge** | parent + **`template-validator`** + **`/verify`** | The **edge-validation matrix** (byte-identity, ALONE/minimal-deps leg, `--vcs-ref HEAD` clean tree, **no-infra** tests) + unit/integration/**contract (Pact)** + **Hypothesis** invariants + **Schemathesis** OpenAPI fuzz + **real use-case scenarios** + (critical modules) **mutmut**; `/verify` runs the rendered app to confirm real behavior. |
| **G4 · Skeptical review** | **adversarial Workflow** (N reviewers, diverse lenses) + **`build-judge`** + **`/code-review`** + **`/security-review`** (security phases) | A diverse panel finds **no real defect** (consensus), AND `build-judge` returns **PASS** against the acceptance criteria. See §5. |
| **G5 · DoD + trace** | **`build-judge`** + parent | RTM 100% (every requirement → component → test → gate → deploy → SLO), threat→test links, diagrams + ADR merged, runbook + SLO present ([SDLC.md](SDLC.md) DoD). |
| **G6 · Merge** | parent (**`/release`**) | Squash-merge with the **exact `feat:` title**; CD auto-tags the version; report (validation table, base-unaffected, matrix rows, proofs, tag). |

---

## 4. The agent & tool roster (using all of Claude's surface)

| Capability | Used for |
|---|---|
| **Parent session** | the Builder — all edits, `/validate`, `/release`, commits, PR, the report. |
| **`template-validator`** (read-only) | generate + lock + ruff + mypy + pytest + alembic over a matrix combo → PASS/FAIL per leg (parallelize the matrix). |
| **`build-judge`** (read-only) | PASS/FAIL a change against acceptance criteria + emit a ready-to-paste next prompt — the G4/G5 adjudicator. |
| **`docs-researcher`** (read-only) | verify any current fact (lib version, API, spec change) before relying on it (G0). |
| **`dependency-auditor`** (read-only) | dep freshness/risk (AI stack extra scrutiny) — run per phase touching deps + before `/release`. |
| **`/validate`** | the canonical local gate (full CI matrix) — G2/G3. |
| **`/code-review`** (low→ultra) | correctness + reuse/simplification review of the diff — G4; `ultra` for high-risk phases. |
| **`/security-review`** | security review of the branch diff — G4 for P1/P15/P29/P30/secrets/auth. |
| **`/verify`** / **`/run`** | launch the rendered app and observe real behavior — G3 (proves it works, not just compiles). |
| **`/simplify`** | post-green altitude/efficiency cleanup (quality, not bug-hunt). |
| **`/audit-deps`**, **`/release`** | dependency audit; Conventional-Commit release + CD tag — G6. |
| **The Workflow orchestrator** | deterministic fan-out of the skeptical-review panel + parallel validators + judge (the assurance harness, §6). |

---

## 5. Skeptical / adversarial review (the assurance core)

The single most important gate. Patterns (from Claude's multi-agent toolbox), **composed**, scaled to
the phase's risk tier:

- **Adversarial verify (refute-by-default):** spawn **N independent reviewers**, each instructed to
  *find a reason to REJECT* and to *default to "reject" when uncertain*. A finding stands only if it
  survives; the phase passes only if the panel can't kill it.
- **Perspective-diverse lenses:** the reviewers are *not* clones — each gets a distinct lens so they
  catch different failure modes: **correctness/spec-fidelity · security (the lethal-trifecta/STRIDE
  view) · edge-cases & determinism · simplicity/over-engineering · cross-combo/byte-identity
  regression**. Redundant reviewers miss what diverse ones catch.
- **Consensus rule:** a "real defect" from *any* lens blocks (G4 → G1). For "is this good enough"
  judgments, majority of the panel + **`build-judge` PASS** is required.
- **Loop-until-dry:** for discovery-heavy phases, keep spawning finders until **K consecutive rounds
  surface nothing new** — the tail of bugs hides past the first pass.
- **Completeness critic:** a final agent asks *"what's missing — an untested edge, an unverified
  claim, a spec requirement with no code, a port with no contract test?"* Its output becomes the next
  fix round.

The parent does **not** mark a phase done on its own say-so; the independent panel + `build-judge`
do. This is the structural answer to "skeptical reviews."

---

## 6. The orchestration — a reference `phase-build-assurance` Workflow

The parent builds, runs `/validate`, then invokes this **assurance Workflow** (read-only fan-out) to
adversarially review the diff/render and adjudicate. Run when building begins (explicit opt-in); the
parent fixes findings and re-runs until it returns clean + build-judge PASS.

```js
export const meta = {
  name: 'phase-build-assurance',
  description: 'Adversarial multi-gate assurance for one roadmap phase (read-only review + judge)',
  phases: [{ title: 'Validate' }, { title: 'Review' }, { title: 'Verify' }, { title: 'Judge' }],
}
// args = { phase: 'P7', riskTier: 'critical', acceptance: '...', diffRef: 'feat/...' }
const LENSES = args.riskTier === 'critical'
  ? ['spec-fidelity','security','edge+determinism','byte-identity/combo','simplicity']
  : ['spec-fidelity','edge+determinism','simplicity']

phase('Validate')                                  // parallel matrix validation (template-validator)
const legs = await parallel(MATRIX_LEGS.map(leg => () =>
  agent(`Validate the ${leg} leg of ${args.phase}: generate + lock + ruff + mypy + pytest + edge matrix. PASS/FAIL.`,
        { agentType: 'template-validator', label: `validate:${leg}`, schema: VERDICT })))

phase('Review')                                    // diverse-lens adversarial reviewers, each refutes
const reviews = await parallel(LENSES.map(lens => () =>
  agent(`Review the ${args.phase} diff through the ${lens} lens. Try to REJECT it: find a real defect,
         a spec-drift, an untested edge, a determinism/byte-identity break. Default to "reject" if unsure.`,
        { label: `review:${lens}`, schema: FINDINGS })))
const findings = reviews.filter(Boolean).flatMap(r => r.findings)

phase('Verify')                                    // each finding independently re-verified (kill false positives)
const confirmed = (await parallel(findings.map(f => () =>
  agent(`Independently verify this claimed defect in ${args.phase}: ${f.title}. Is it REAL and reproducible?`,
        { label: `verify:${f.id}`, schema: VERDICT }).then(v => ({ ...f, real: v.isReal })))))
  .filter(Boolean).filter(f => f.real)

phase('Judge')                                     // build-judge: PASS/FAIL vs acceptance + next prompt
const verdict = await agent(
  `Judge ${args.phase} against acceptance criteria: ${args.acceptance}. Confirmed defects: ${JSON.stringify(confirmed)}.
   Matrix: ${JSON.stringify(legs)}. Return PASS only if zero confirmed defects and all legs pass; else FAIL + a
   ready-to-paste next prompt listing exactly what to fix.`,
  { agentType: 'build-judge', schema: JUDGEMENT })

return { verdict, confirmed, legs }   // parent loops on FAIL; proceeds to G5/G6 on PASS
```

For *generating* candidate designs (G0) or hard trade-offs, add a **judge panel**: N independent design
attempts → scored → synthesize the winner (the Workflow "judge panel" pattern).

---

## 7. Real use-cases + edge-cases (how G3 gets to "no edge missed")

Five layers, so edges aren't left to luck:
1. **Use-case scenarios** — the phase's Given/When/Then acceptance criteria, run end-to-end (incl.
   `/verify` against the rendered app).
2. **The edge matrix (regression checklist)** — the hard-won edge bugs are encoded as a standing
   checklist every phase re-checks: **byte-identity OFF == prior tag**, the **ALONE/minimal-deps leg**,
   **db-less/db-present leg parity**, **`--vcs-ref HEAD` clean-tree render**, **no-infra tests**
   (unreachable Redis / sqlite), **trim_blocks newline** traps, **RLS cross-tenant leak**,
   **import-sort/RUF012** on the maximal combo. (These come from the project's accumulated memory —
   each was a real CI failure once.)
3. **Property-based generation** — **Hypothesis** auto-generates edge inputs for invariants
   (money/`Decimal`, idempotency, serialization, RLS) — the machine finds edges humans miss.
4. **API fuzzing** — **Schemathesis** drives the service's own OpenAPI with malformed/negative cases.
5. **Mutation** (critical phases) — **mutmut** confirms the tests actually *catch* injected bugs, so
   "covered" means "checked."

---

## 8. Failure handling & the loop

A red gate is *normal* and is the system working. The loop: **gate fails → build-judge emits the exact
next prompt → parent fixes → re-run from G1.** Auto-fixable classes (lint/format/import-sort/RUF012,
known trim_blocks/byte-identity traps) are fixed and re-validated without ceremony; design-level or
security findings escalate to a human checkpoint. **Determinism makes the loop trustworthy** —
reproducible builds + frozen time + pytest-randomly mean a green re-run isn't luck. Track DORA
(change-fail-rate, MTTR) once a team exists.

---

## 9. Human-in-the-loop (you stay in control)

- **Before any building:** approve the spec; answer the consequential decisions (**D1-D3, D9, D14, D17,
  D18**). The rest proceed on cost-effective defaults.
- **Per wave:** review the merged phases' reports (each phase reports its validation table, byte-/base-
  unaffected proof, matrix rows, the specific proofs, and the tag).
- **Escalation:** the system pauses for you on design-level review findings, irreversible/destructive
  actions, and the security-sensitive phases' `/security-review` verdicts.
- **Cadence control:** waves are dependency-ordered; you can reprioritize, pause, or stop at any wave.

---

## 10. Putting it together — the per-phase command flow

```
parent: read docs/ (spec for Pn) ───────────────► G0 design + RTM + threat + test plan (build-judge checks DoR)
parent: implement Pn behind its toggle ─────────► G1
parent: /validate  (+ template-validator matrix)─► G2 quality + G3 edge matrix / Hypothesis / Schemathesis / /verify
parent: run phase-build-assurance Workflow ─────► G4 adversarial panel + build-judge  → (FAIL: fix, loop to G1)
parent: confirm RTM/diagrams/runbook/SLO ───────► G5  ·  /code-review · /security-review (risk phases)
parent: /release (squash exact title) ──────────► G6  → CD tags version → report
```

This is the system that builds the spec "completely": every phase, the same seven gates, an independent
adversarial panel, the edge matrix + property/fuzz/mutation testing, determinism, and a human at the
decision and review checkpoints — **100% gate-pass, honestly defined, on every phase.**
