# SDLC.md — the development lifecycle discipline (lean but rigorous)

> How every ROADMAP phase is built so **nothing is missed and everything is traced** — without
> waterfall over-specification. This is the *process* layer: the artifacts each phase must produce,
> the Definition-of-Ready / Definition-of-Done gates, and the per-team-size lean guidance. The
> *content* lives in [TRACEABILITY.md](TRACEABILITY.md) (the RTM), [SYSTEM-DESIGN.md](SYSTEM-DESIGN.md)
> (diagrams), [CICD-PIPELINE.md](CICD-PIPELINE.md) (gates), [INFRA-TOPOLOGY.md](INFRA-TOPOLOGY.md)
> (deploy). Inherits [PRINCIPLES.md](PRINCIPLES.md). Standards: C4, arc42, ISO/IEC/IEEE 12207 & 1016,
> OWASP ASVS/SAMM, NIST SSDF (SP 800-218), SLSA, DORA — applied at the *lean* end of the scale.

---

## 1. The core idea: completeness is a gate, not an upfront essay

You cannot correctly enumerate every component, diagram, and test for 30 phases before writing code —
that's waterfall, and most of it would be wrong. Instead, **each phase is one `feat:` PR that carries
a fixed artifact set**, and the **Definition-of-Done blocks the merge** until that set is complete and
traced. Completeness is therefore *structural*: the gate guarantees no requirement ships without a
design, a threat model, tests, a traceability row, a deploy note, and an SLO — every time, for every
phase. Lean teams keep each artifact small; the *set* is non-negotiable.

```mermaid
flowchart LR
    DoR[Definition of Ready] --> D[Design\nC4 + sequence + ER + ADR + STRIDE]
    D --> C[Code\nbehind a port, gated toggle]
    C --> T[Test\npyramid + contract + security]
    T --> G[CI/CD gates\nlint·type·SAST·SCA·secrets·SBOM·sign]
    G --> DoD[Definition of Done] --> M[squash-merge + tag]
    M --> Dep[Deploy\nIaC + canary + SLO + runbook]
    Dep --> O[Observe\nSLO/error-budget 7d]
    classDef s fill:#1168bd,color:#fff,stroke:#0b4884; class DoR,D,C,T,G,DoD,M,Dep,O s;
```

---

## 2. The per-phase artifact set (every phase produces all of these)

Each phase's deltas (not a restatement of [PRINCIPLES.md](PRINCIPLES.md)) are captured as:

| # | Artifact | Where it lives | Notation |
|---|---|---|---|
| 1 | **Requirements + acceptance criteria** | `docs/phases/PNN/` + RTM rows | Given/When/Then |
| 2 | **RTM rows** (req → component → test → CI gate → deploy → SLO) | [TRACEABILITY.md](TRACEABILITY.md) / `.meta/rtm/PNN.yml` | YAML, in-repo |
| 3 | **Design**: C4 component + primary sequence + ER delta | phase `.md` (Mermaid) | C4 / UML seq / ER |
| 4 | **ADR(s)** for any hard decision | `docs/adr/NNNN-*.md` | MADR (1 page) |
| 5 | **STRIDE threat model** (per component) + mitigations→tests | `.meta/threat/PNN.yml` | STRIDE (+ "A" for agents) |
| 6 | **Test plan**: unit/integration/contract/security per the pyramid | `tests/` + RTM | pytest / Pact |
| 7 | **CI capability row(s)** + DevSecOps gates green | `ci.yml` + [CICD-PIPELINE.md](CICD-PIPELINE.md) | — |
| 8 | **Deploy/IaC note**: topology delta (dep, network rule, secret, migration) | phase `.md` + `infra/` | [INFRA-TOPOLOGY.md](INFRA-TOPOLOGY.md) |
| 9 | **Runbook**: deploy steps + rollback + on-call | `docs/runbooks/PNN.md` | — |
| 10 | **Observability/SLO**: SLIs, targets, alerts, spans/metrics/logs | phase `.md` + dashboards | OTel + SLO |

The platform-level versions of 3/8/10 already exist (SYSTEM-DESIGN, INFRA-TOPOLOGY, observability
module); a phase ships the *granular delta* and links it from its RTM rows.

---

## 3. Definition of Ready (before code)

A phase may start when: the requirement is a 3-5 sentence story with Given/When/Then acceptance
criteria; dependencies/implies are mapped (which prior phases, which ports/toggles); a one-line STRIDE
stub names the applicable threat categories; a design spike sketches the C4 container + happy-path
sequence; an ADR stub exists *if* there's a hard decision; the RTM requirement IDs are created; and the
CI capability row is identified. (Lean: this is ~1-2 hours, in the PR description + the RTM file.)

## 4. Definition of Done (before merge) — the gate

A phase is done when **all** hold (enforced by review + CI):
- Code sits **behind its port + gated toggle**; the **edge-validation matrix passes** (byte-identity
  OFF, ALONE leg, `--vcs-ref HEAD` clean tree, no-infra tests) — the existing P3 discipline.
- **RTM 100%**: every requirement has ≥1 component, ≥1 test, a CI gate, a deploy note, an SLO (a CI
  script fails the build on a missing link).
- **Threat model**: every identified threat has a mitigation **and** a test.
- **Diagrams** (C4 component + sequence + ER delta) render in the PR; **ADR(s)** finalized.
- **Tests**: pyramid (unit-heavy) + **contract tests for any new port/adapter** (Pact) + security tests
  (the threat-model mitigations) green; coverage threshold met.
- **DevSecOps gates green**: ruff + mypy + pytest (existing) **plus** secret-scan, SAST, SCA, image
  scan, **SBOM generated + artifact signed (SLSA)** — see [CICD-PIPELINE.md](CICD-PIPELINE.md).
- **Runbook + SLO** present; **review** approvals obtained.
- **Squash-merge with the exact `feat:` title** (CD tags the version) — the existing release discipline.

---

## 5. Lean by team size (include vs skip — don't gold-plate the process)

The artifact *set* is fixed; its *depth* scales with the team. Process gold-plating is as wrong as
product gold-plating (P9).

| Artifact | Solo founder | Small team (2-4) | Growing (5+) |
|---|---|---|---|
| RTM | minimal (3-5 reqs/phase) | full | full + dashboards |
| C4 | context + container | + component | + arc42 (12 sections) |
| ADR | major decisions in design.md | one per hard decision | ADR review board |
| STRIDE threat model | top-3 risks | per-component | + DAST/pentest |
| Tests | unit ≥ target + key integration | + contract (Pact) | + E2E + property |
| DevSecOps gates | secret-scan + SAST + SCA + SBOM (all auto) | + sign/SLSA L2 | SLSA L3 + provenance |
| SLO | 1-2 SLIs | per-service | org-wide DORA |
| Runbook | template, 30 min | + on-call | SRE handbook |

**Always automate (cheap, high-value):** secret-scan, SAST, SCA, SBOM, RTM-coverage check, diagram
lint, the edge-validation matrix. **Defer for solo:** E2E, DAST, formal arc42. **Never skip:** the
port/toggle gating, the threat-model→test link, the SLO, the traceability row.

---

## 6. Cross-cutting discipline (inherited, restated as gates)

- **Security shift-left (DevSecOps):** STRIDE at design; SAST/secret-scan at commit; SCA/SBOM at build;
  sign at release; DAST/pentest at scale. OWASP ASVS as the requirement checklist for security-sensitive
  phases; NIST SSDF as the umbrella.
- **Supply chain (SLSA):** pinned deps (uv lock + Renovate, majors not auto-merged) + SBOM (CycloneDX) +
  keyless signing (Sigstore/cosign) + provenance — in the template CI and the generated CI (P2).
- **Flow (DORA):** trunk-based, short-lived branches, one phase = one PR, gated merge; track the 4 keys
  once there's a team.
- **Contract testing** the ports: every adapter is verified against its port's contract (Pact-style), so
  swapping a vendor can't silently break the app — the ports-and-adapters discipline made testable.

---

## 7. Where the artifacts live (repo layout)

```
docs/                 # this spec set (strategy + framework) — already present
  phases/PNN/         # per-phase: requirements, design (C4/seq/ER), deploy note
  adr/NNNN-*.md       # architecture decision records (MADR)
  runbooks/PNN.md     # deploy + rollback + on-call
.meta/                # machine-checked artifacts
  rtm/PNN.yml         # traceability rows (the living RTM)
  threat/PNN.yml      # STRIDE per component
scripts/check_rtm_coverage.py   # CI gate: fail on a broken trace link
```

A phase is not "done" until its `docs/phases/PNN/`, `.meta/rtm/PNN.yml`, `.meta/threat/PNN.yml`,
runbook, CI row, and code merge **together** — the traceability is the proof of completeness.
