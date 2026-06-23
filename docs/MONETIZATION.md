# MONETIZATION.md — revenue-model orchestration + AI pricing intelligence

> The monetization **decision** layer, above the billing **plumbing**. The platform already specs how
> to *charge* (subscriptions via `PaymentsPort`; usage→rating→invoice via `MeteringPort`/`BillingPort`,
> P7; entitlements + quotas, P8; API products + dev portal, P35). What it did **not** capture is the
> layer that decides *what* to charge, *how* to package it, and *which* of several revenue streams to
> compose — and the **AI systems** that turn usage + cohort data into pricing/packaging recommendations.
> This doc specs that as two dependency-sequenced phases, the same disciplined way Wave 5 (AI) is specced
> in [AI-AGENTIC-STACK.md](AI-AGENTIC-STACK.md). Canonical companions: [ROADMAP.md](ROADMAP.md) (P39/P40),
> [ARCHITECTURE.md](ARCHITECTURE.md) (the new ports), [LIBRARY-DECISIONS.md](LIBRARY-DECISIONS.md)
> (ADR-37/38), [COMPLETENESS-AUDIT.md](COMPLETENESS-AUDIT.md) (§B), [DECISIONS-NEEDED.md](DECISIONS-NEEDED.md)
> (D19/D20).

---

## 1. The gap (why this is a real subsystem, not gold-plating)

A modern AI-SaaS rarely earns from one stream. It blends: a base **subscription** (flat or per-seat),
**usage/overage** (the AI cost = billable unit — P7/P21), **prepaid credits** with burn-down, **one-time
charges / add-ons**, **API-product** pricing (per-key/per-call tiers for the developer surface — P35),
and **marketplace rev-share** (when third parties sell on the platform — P35). Today each of those is a
*mechanism* with no unifying **revenue model** and no engine that **resolves the effective price + entitlement**
for a `(tenant, plan, usage)` tuple — and no way to change packaging without a code deploy.

Above that sits the harder, higher-value gap: **deciding** the numbers. Plan **recommendation**, **dynamic /
personalized** pricing, **upsell/expansion** timing, **churn-risk** discounting, **price-elasticity** and
**usage-forecast** modeling, **packaging simulation** ("what if feature X moves to Pro?"), and **price
experimentation** (A/B → measure → re-price). This is `decision-support`, increasingly **AI-driven**, and it
is genuinely absent from the spec. Per [COMPLETENESS-AUDIT.md](COMPLETENESS-AUDIT.md)'s own rule — *a new
subsystem becomes a phase* — it earns two.

**Split rationale (two phases, not one):** the **engine** (P39) is deterministic plumbing — pricing as data,
entitlement/price resolution, proration, multi-stream invoicing. The **intelligence** (P40) is an
AI/analytics layer that *reads* usage + cohorts and *proposes* changes the engine then applies. They ship
independently (P40 needs P39 + metering data to exist first), match the platform's one-`feat:`-PR-per-phase
discipline, and keep the risky AI/pricing-fairness concerns isolated behind a human gate.

---

## 2. Two planes

```
            ┌─────────────────────────── P40 · AI PRICING INTELLIGENCE ───────────────────────────┐
 inputs →   │  metering(P7) · analytics(P34: MRR/ARR/churn/expansion/cohorts) · catalog(P39)        │
            │     │                                                                                  │
            │     ▼   PricingIntelligencePort.recommend(...)  →  Recommendation{change, rationale,    │
            │  rules+forecast baseline  |  LLM/agent adapter (P21, token-metered)   confidence, bounds}│
            │     │                                   │ guardrails (P26: floors/ceilings/fairness)     │
            │     ▼  human-in-the-loop APPROVAL (D-gate) ─────────────► apply via P39 PackagingPort     │
            │     ▼  price experiments: A/B via flags (P18) → measure lift → recommend                  │
            └───────────────────────────────────────┬───────────────────────────────────────────────┘
                                                     │ applies / reads
            ┌────────────────────────────────────────▼──────────────── P39 · REVENUE-MODEL ENGINE ────┐
            │  PricingCatalog (products·plans·features·prices·streams) — versioned DATA, not code       │
            │  PricingPort.resolve(tenant, plan, usage) → {entitlements, line_items}                    │
            │  PackagingPort.publish(catalog_version) (audited, reversible)                             │
            │  streams: subscription · per-seat · usage/overage(P7) · credits/burn-down · one-time/     │
            │           add-on · API-product(P35) · marketplace rev-share(P35)                          │
            └───────────────┬───────────────────────────────────────────────┬──────────────────────────┘
                            │ entitlements                                   │ rate→invoice→charge
                            ▼ (P8 require_feature / quotas)                  ▼ (P7 MeteringPort/BillingPort → PaymentsPort)
```

The engine never decides numbers; the intelligence never charges. The engine is the **system of record**
for packaging; the intelligence is a **recommender** whose output a human approves before it touches money.

---

## 3. P39 — Revenue-model & packaging engine

**Goal:** packaging is **data**, edited without a deploy; one engine resolves the effective entitlement +
price for any `(tenant, plan, usage)` and composes every active stream into one P7 invoice.

### 3.1 Data model (`app/pricing`, Postgres-native default)
- **`Product`** → **`Plan`** (tier) → **`PlanFeature`** (entitlement keys + limits, feeds P8) and
  **`Price`** (per stream, per currency, per interval; effective-dated). **`AddOn`** (one-time / recurring).
- **`PricingCatalog` version** — an immutable, published snapshot (`draft → published → archived`); a
  change publishes a *new version*, so pricing history is auditable + rollback is "re-publish vN".
- **`Subscription`** (extends the shipped billing model) references a catalog version + plan + add-ons +
  seat count; **`CustomerWallet`/`WalletTransaction`** (prepaid credits, extends P7) for burn-down.
- **Revenue-stream taxonomy** (a stream is `kind + price + meter?`): `subscription_flat`, `per_seat`,
  `usage_overage` (→ P7 meter), `prepaid_credit` (→ wallet), `one_time`, `api_call` (→ P35 key/usage),
  `marketplace_revshare` (→ P35 take-rate). New streams are new `kind`s, not new code paths.

### 3.2 Ports (the seams — see [ARCHITECTURE.md](ARCHITECTURE.md) §3)
- **`PricingPort.resolve(tenant, plan, usage) -> ResolvedPricing{entitlements, line_items, currency}`** —
  pure, deterministic; the rest of the app reads only this. Default adapter is the Postgres catalog;
  managed adapters (**Stripe Billing**, **Lago**, **Metronome**, **Orb**) implement the same contract.
- **`PackagingPort.publish(version) / rollback(version)`** — mutates the catalog (audited via P10).
- **Proration** on up/down-grade is a `PricingPort` concern (default: time-prorated against the active
  interval; matches Stripe semantics).

### 3.3 Backend workflow
1. Request hits an org-scoped route → P8 `require_feature(key)` calls `PricingPort.resolve(...)` for the
   tenant's plan → entitlements gate the route; quotas (P8) read the resolved limits.
2. Billing cycle / usage close → P7 aggregates `UsageEvent`s, **rates against the resolved `line_items`**
   (base + included quota + overage + seats + add-ons + credit burn-down), emits one **`Invoice`**, charges
   via `PaymentsPort`. Multi-stream composition happens here — the engine supplies the line items, P7 totals.
3. A packaging change = `PackagingPort.publish(new_version)`; existing subscriptions migrate on renewal (or
   immediately with proration), every change audited + reversible.

### 3.4 Toggle / deps / DoD / CI
- **Toggle/Port:** `include_pricing` (implies billing + metering); `PricingPort`, `PackagingPort`,
  `pricing_provider`.
- **Implies/Deps:** **P7 metering** (rate→invoice), **P8 entitlements/quotas**, billing.
- **DoD:** a plan/price/packaging change is **data-only** (no deploy); `resolve(...)` is deterministic +
  pure; proration on up/downgrade is correct; ≥2 streams compose into one invoice via P7; every catalog
  change is versioned, audited (P10), and reversible; works on sqlite/no-infra with the default adapter.
- **CI:** `pricing` (ALONE: pricing + metering + billing minimal) + `pricing_full` (+ API-product + add-ons
  + proration) rows; alembic round-trip of the new tables.

---

## 4. P40 — AI pricing intelligence (revenue optimization)

**Goal:** turn usage + cohort data into **pricing/packaging recommendations** with rationale + guardrails,
which a human approves before they apply via P39. The decision model is a **pluggable adapter**.

### 4.1 Port + adapters
- **`PricingIntelligencePort.recommend(scope) -> list[Recommendation]`** where `Recommendation =
  {target (plan/feature/tenant-segment), change (price/packaging/discount), rationale, confidence, bounds,
  expected_lift}`. Also `simulate(change) -> ProjectedImpact` (packaging what-ifs) and
  `evaluate(experiment) -> Lift`.
- **Default adapter — `rules+forecast`:** deterministic, no-LLM. Usage-percentile plan-fit + a simple
  forecast (e.g. EWMA/Holt on usage) + heuristics (high-overage tenant → upgrade rec; idle paid seat →
  downgrade/churn-risk; near-quota → upsell). Always available, no external dep.
- **AI adapter — `llm`:** an LLM/agent over the AI stack (**P21 LLM gateway, token-metered**) that reads the
  catalog + analytics + a usage summary and proposes changes **with a written rationale + confidence**,
  structured-output-validated (instructor). Degrades to `rules+forecast` when the LLM is unconfigured.

### 4.2 Capabilities (each a `recommend` mode)
plan **recommendation** + right-sizing · **expansion/upsell** timing · **dynamic / personalized** pricing
(within guardrails) · **churn-risk** retention discounting · **price-elasticity** estimation ·
**usage-forecast** → revenue projection · **packaging simulation** (move feature across tiers) ·
**price experimentation** (launch an A/B price via **P18 flags**, measure lift, recommend the winner).

### 4.3 Guardrails + governance (non-negotiable)
- **Guardrails (ties P26):** hard price **floors/ceilings**, **max discount**, **no personalized price for a
  protected attribute** (fairness/anti-discrimination), per-region legal bounds — enforced *before* a
  recommendation is surfaced; a recommendation that violates a guardrail is dropped + logged.
- **Human-in-the-loop:** nothing auto-applies. `recommend → review → approve → PackagingPort.publish`. Every
  applied change is audited (P10) + reversible (P39 rollback).
- **Founder D-gate:** enabling **dynamic/personalized pricing** is a legal/fairness/regional decision
  (D20) — off by default; the platform ships the engine + the rules baseline, not a live dynamic-pricing
  policy.

### 4.4 Backend workflow
metering(P7) + analytics(P34) + catalog(P39) → `recommend()` (rules or LLM) → guardrail filter (P26) →
review queue → human approve → `PackagingPort.publish()` (P39) → audit (P10); experiments fan out via P18,
measured by P34. AI adapter cost is itself metered through P7 (the platform dogfoods its own unit economics).

### 4.5 Toggle / deps / DoD / CI
- **Toggle/Port:** `include_pricing_ai` (implies pricing P39 + analytics P34); `PricingIntelligencePort`,
  `pricing_ai_provider` (default `rules`; `llm` via P21).
- **Implies/Deps:** **P39** packaging engine, **P7** metering, **P34** analytics, **P18** flags (experiments),
  **P21** LLM gateway (AI adapter, optional), **P26** guardrails (price-fairness), **P10** audit.
- **DoD:** a recommendation is produced from real usage/cohort data with rationale + confidence +
  guardrail-checked bounds; **nothing auto-applies** (human gate); an A/B price experiment launches (P18) and
  its lift is measured (P34); the `llm` adapter **degrades to `rules`** when unconfigured; every applied
  change is audited + reversible; guardrail violations are rejected. Works on sqlite/no-infra with a fake LLM.
- **CI:** `pricing_ai` row (ALONE: pricing_ai + pricing + analytics, fake LLM) — recommend→approve→apply→audit
  happy path + a guardrail-rejection test + the llm→rules degradation test.

---

## 5. Library decisions (summary — ADR-37/38 in [LIBRARY-DECISIONS.md](LIBRARY-DECISIONS.md))

| Subsystem | Default (cost-effective / self-host) | Managed swap | Why |
|---|---|---|---|
| **Revenue-model engine** (P39) | **Postgres-native** pricing catalog (pricing as versioned data) behind `PricingPort` | Stripe Billing · **Lago** (self-host, MIT) · Metronome · Orb | Pricing is core IP + needs durable, auditable, deploy-free changes; managed billing engines are 1–2% rev-share, justified only at volume — the port keeps the swap a config change |
| **AI pricing intelligence** (P40) | **`rules+forecast`** baseline (deterministic, no external dep) | **`llm` adapter** via P21 gateway (token-metered); offline elasticity via a notebook/DW seam | Ship value with zero AI cost; the LLM adapter is opt-in + degrades; the *model* is a port so a future trained elasticity model drops in without touching callers |

Out of scope (consciously): a full **BI/data-warehouse** (P34 `AnalyticsPort` covers in-app metrics; a DW is
an external decision), bespoke **ML model training/serving infra** (the port consumes a model; training is a
notebook/MLOps concern), and **tax computation** (P33 owns tax/e-invoicing; the engine emits pre-tax line items).

---

## 6. Phasing, sequencing, founder gates

- **P39** slots in **Wave 3/4**, immediately after **P7 (metering)** + **P8 (entitlements)** — it needs the
  usage→rating spine and the entitlement levers to exist. One `feat:` PR, gated by a `pricing` capability row.
- **P40** slots in **Wave 5 (AI)** alongside the AI stack — it needs **P39** + **P34 analytics** + (for the
  `llm` adapter) **P21**. One `feat:` PR, gated by a `pricing_ai` row. Rides the same `MeteringPort` seam
  (its own AI cost is billable).
- **Founder decisions** ([DECISIONS-NEEDED.md](DECISIONS-NEEDED.md)): **D19** — which revenue streams + the
  pricing philosophy (seat vs usage vs hybrid; credit model); **D20** ⚠️ — whether to enable
  **dynamic/personalized pricing** at all (legal/fairness/India-DPDP + EU implications) — default **off**,
  rules-baseline + human approval only until explicitly enabled.

This keeps the platform's invariant: every monetization capability is a port with a cost-effective
self-hostable default, gated behind a toggle, byte-identity-safe when off, CI-gated, and sequenced after its
real dependencies — and the genuinely consequential calls (pricing strategy, dynamic pricing) are escalated
to the founder rather than guessed.
