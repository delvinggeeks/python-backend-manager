# CICD-PIPELINE.md — the CI/CD pipeline & DevSecOps gates

> The end-to-end pipeline that turns a phase PR into a signed, deployed, observed release — with
> security shifted left into every stage. Two layers: the **template's own CI** (proves the template
> still generates working, secure projects) and the **generated service's CI** (what ships into each
> backend). Implements the [SDLC.md](SDLC.md) gates and the [TRACEABILITY.md](TRACEABILITY.md)
> coverage check. Supply-chain hardening is ROADMAP **P2**; standards: NIST SSDF (SP 800-218), SLSA,
> OWASP ASVS, DORA. Inherits [PRINCIPLES.md](PRINCIPLES.md).

---

## 1. Pipeline stages & gates

```mermaid
flowchart LR
    commit[Commit/PR] --> g1[Stage 1: COMMIT\nsecret-scan · SAST · lint · type]
    g1 --> g2[Stage 2: TEST\nunit · integration · contract · security\n+ edge-matrix + RTM-coverage]
    g2 --> g3[Stage 3: DESIGN\ndiagram lint · ADR · threat→test]
    g3 --> g4[Stage 4: BUILD\nimage · SCA/scan · SBOM · SIGN/SLSA]
    g4 --> g5[Stage 5: MERGE\nblock on high findings · 2 approvals]
    g5 --> g6[Stage 6: DEPLOY\ntofu plan · canary · smoke · SLO check]
    g6 --> g7[Stage 7: OBSERVE\nSLO/error-budget · rollback-on-breach]
    classDef s fill:#1168bd,color:#fff,stroke:#0b4884; class g1,g2,g3,g4,g5,g6,g7 s;
```

| Stage | Gate (block-on) | Tools (OSS, ₹0) |
|---|---|---|
| **1 · Commit** | any secret; high/critical SAST; lint/type fail | gitleaks/trufflehog · semgrep + bandit · **ruff + mypy** (existing) |
| **2 · Test** | test fail; coverage < threshold; **edge-matrix fail**; **RTM-coverage broken link** | **pytest** (existing) · testcontainers · **Pact** (port contracts) · `check_rtm_coverage.py` |
| **3 · Design** | diagram won't render; missing ADR for new component; a threat with no test | mermaid-lint · ADR-coverage script · threat-coverage script |
| **4 · Build** | high CVE (no waiver); unsigned artifact | Trivy/Grype + `uv`/pip-audit · **CycloneDX SBOM** (Syft) · **cosign keyless** (Sigstore, GitHub OIDC) |
| **5 · Merge** | any unresolved high finding; < 2 approvals (1 security/arch) | branch protection + SARIF gate |
| **6 · Deploy** | `tofu plan` drift/policy fail; canary SLO breach; smoke fail | OpenTofu + policy-as-code · Flagger/ArgoCD canary · smoke tests |
| **7 · Observe** | SLO/error-budget breach → auto-rollback + page | OTel + Prometheus + AlertManager |

Stages 1-5 run on every PR; 6-7 on merge to `main`/release. The **existing template gate**
(`generate (capability)` + the 4 framework legs + render-gate) is Stage 2's core; this doc adds the
security/design/supply-chain gates around it.

---

## 2. Two CI layers (don't confuse them)

- **Template CI** (`.github/workflows/ci.yml`, repo root): generates real projects across the matrix and
  runs the full gate on each (lock/sync/ruff/format/mypy/pytest + alembic round-trip), **plus P2**:
  render-gates the generated workflow YAML, emits an SBOM + signed image for the template, and pins
  action SHAs. A capability/phase is covered by adding **one matrix row** — branch protection requires
  the aggregated `generate (capability)` check, so new rows are covered automatically.
- **Generated-service CI** (rendered into `template/.github/workflows/`): the same gate set tuned for a
  running service — secret-scan, SAST, SCA, **SBOM + cosign signing**, image scan, the test pyramid,
  `tofu plan`, and the deploy/canary/SLO stages. This is what each backend ships with from day one.

The render-gate ensures a Renovate bump to a CI action **cannot go green** unless it still renders into
valid workflow YAML — which is what makes auto-merging action majors safe.

---

## 3. Gate policy (block / warn / log)

- **Block the merge:** any secret; high/critical SAST or CVE without a documented waiver; coverage
  under threshold; a broken RTM trace link; an unmitigated threat; edge-matrix failure; unsigned
  release artifact; missing SBOM.
- **Warn (don't block):** medium SAST, low-risk CVE (tracked), diagram nits.
- **Log only:** informational lint, style.
- **Renovate:** auto-merge patch/dev after green; **majors require review** (never auto-merge a major).

---

## 4. Supply chain (SLSA) & provenance

Pinned deps (`uv lock` lower-bounds + Renovate) → **SBOM** (CycloneDX via Syft/`uv export`) → **keyless
signing** (cosign + Sigstore Fulcio/Rekor, GitHub OIDC — no long-lived keys) → **build provenance**
(GitHub attestations / SLSA L2→L3). Verified at deploy (`cosign verify` + `slsa-verifier`) so only
signed, provenanced artifacts reach production. Applies to both CI layers (P2).

---

## 5. Mapping to SDLC & traceability

Each pipeline gate corresponds to a [SDLC.md](SDLC.md) Definition-of-Done item, and each phase's
[TRACEABILITY.md](TRACEABILITY.md) rows name the **`ci_gate`** that proves the requirement — so the
pipeline is itself traced: requirement → test → *named gate* → deploy. The DORA 4-keys (deploy
frequency, lead time, change-fail rate, MTTR) are derived from this pipeline's run data once a team
exists. Nothing merges, ships, or is "done" outside these gates — that's the guarantee that no stage,
security check, or component is skipped, on any phase.
