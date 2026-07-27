# PLATFORM-INTEGRATION.md — the integration contract

> **Always-read.** This file holds only what is *durable*: what this repo is, and the exact
> standards a parent platform must speak. Anything **scheduled** lives in the ledger
> ([ROADMAP.md](ROADMAP.md)); anything **enforced** lives in
> [SECURITY-BASELINE.md](SECURITY-BASELINE.md) §13. Nothing here duplicates either.

---

## 1. Role — the anchor everything follows from

**The coupling rule, first, because it constrains every other decision:**

> This template is a general-purpose asset. A platform that adopts it is **one consumer of it**.
> The dependency direction is **one-way** — consumers depend on the template; **the template never
> references any consumer.** No consumer name appears in this repo's flags, code, settings, docs or
> tests. Ever.

That is not politeness. The moment a consumer's name enters a copier flag or a settings key, every
*other* adopter inherits a foreign vocabulary and the asset stops being general-purpose.

**`python_backend_manager` is a platform-neutral Python Service Chassis.** It generates Python
services that live inside any parent platform speaking standard protocols, and standalone Python
SaaS backends. A parent platform records "our Python services come from this chassis" **on its own
side**; this repo records only the standards it speaks. The repo keeps its own neutral identity.

---

## 2. The two modes

`integration_mode`, with exactly two values:

| Mode | Meaning |
|---|---|
| **`standalone`** *(default)* | A full self-contained SaaS backend: local identity and user tables, its own gateway, its own observability stack. |
| **`platform`** | The service runs inside a parent platform, wired **entirely through configurable standard endpoints — zero vendor coupling.** |

---

## 3. The four standard endpoints

**`platform` mode is defined by these four and nothing else.** No platform-specific code path, no
consumer-named adapter, no private protocol. A system providing these four works:

| Concern | Standard | Configuration surface |
|---|---|---|
| **Identity** | **OIDC** — the service is a *stateless verifier*, validating signatures against the issuer's **JWKS** endpoint | issuer URL, JWKS URL (or discovery), audience; **tenant and role claim names are configurable** — none is hard-coded |
| **Model calls** | **OpenAI-compatible HTTP API** | gateway base URL + key (+ optional budget/virtual-key header) |
| **Telemetry** | **OTLP** | exporter endpoint |
| **Entitlements** *(optional)* | plain HTTP API returning plan → features/limits | entitlements API base URL; **absent → falls back to local entitlements** |

**Why four endpoints and not an integration SDK:** an SDK is vendor coupling wearing a standards
costume. A base URL, an issuer URL, an OTLP endpoint and an optional HTTP API are all replaceable by
the adopter without touching generated code — the [P1](PRINCIPLES.md) *port vs toggle* discipline
applied at the platform boundary.

### 3.1 Type contract at the boundary

OIDC identifiers are strings; this repo's tenancy is UUID-typed with a hard `::uuid` cast in the RLS
policy. **The tenant claim must therefore be a UUID**, validated at token verification so a
non-conforming claim is a clean `403` at the edge rather than a `500` from Postgres. The subject
claim is a free-form string and is never used as a foreign key.

---

## 4. What `platform` mode removes

Local identity: the `user` and `refresh_tokens` tables, `memberships`, and the `/auth/*` and
`/users/*` routes. Tenant and roles come from verified claims; `organizations` rows are provisioned
just-in-time from the verified tenant claim, so the DDL is identical in both modes.

**The invariant that makes this safe:** RLS keys on the URL path while authorization keys on the
claim, so a claims-derived membership **must assert `path org_id == claim tenant` and 403 on
mismatch**. Without it, a token for tenant A reads tenant B.

---

## 5. Out of scope for this repo

Belongs to the parent platform, and must not be duplicated here: frontend and design system · the
platform's own identity product · enterprise SSO / SCIM · a module marketplace · any consumer's
non-Python concerns.

**The contract is the boundary.** A generated service consumes the parent platform's OpenAPI
contracts and emits its own; generated SDKs cross that line, nothing else does.

> **`standalone`'s ceiling, stated honestly:** enterprise SSO/SCIM stays platform-level. A
> standalone deployment needing it graduates to `platform` mode behind an OIDC issuer — it does not
> get SCIM from this repo.

---

## 6. Definition of done for the integration

An `integration_mode=platform` generation produces a service that validates parent-platform OIDC
tokens with zero local identity tables · routes every model call through the configured
OpenAI-compatible gateway with `gen_ai.*`-traced spans feeding `MeteringPort` · enforces tenant
isolation with `FORCE` RLS and transaction-scoped context · exposes its OpenAPI contract for SDK
generation · deploys via generated Stage-2 IaC — while `standalone` keeps today's behavior,
byte-for-byte unchanged where the new toggles are off ([P2](PRINCIPLES.md)).

**Scheduled work toward this lives in [ROADMAP.md](ROADMAP.md).** This file does not track it.
