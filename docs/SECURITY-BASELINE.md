# SECURITY-BASELINE.md — defense in depth, and where each control must live

> This repo's security reference. Platform-neutral: it names standards and positions, never a
> consumer, a vendor, or a deployment. Inherits [PRINCIPLES.md](PRINCIPLES.md) — where a layer
> restates a principle, it cites it rather than re-arguing it. Companion to
> [ARCHITECTURE.md](ARCHITECTURE.md) (the seams) and [CICD-PIPELINE.md](CICD-PIPELINE.md) (the gates).

---

## 0. The doctrine: position, not existence

A control that exists in a document and nowhere else does not exist. What makes a guardrail real is
**where it is enforced**, and the positions are strictly ordered:

```
environment   >   policy / CI   >   middleware   >   prose
  strongest                                          not a control
```

| Position | Meaning | Failure mode it removes |
|---|---|---|
| **environment** | The unsafe state is unreachable — the network path doesn't exist, the credential was never minted, the container has no write access, the role cannot see the row. | Every failure mode. Nothing to remember, nothing to bypass. |
| **policy / CI** | The unsafe state is reachable at runtime but **cannot be merged or released**: a gate fails the build. | Regression. A human can still do it by hand in an emergency, and that is visible. |
| **middleware** | The unsafe request is rejected at run time by code on the request path. | The request. But new code paths that bypass the middleware are not covered. |
| **prose** | A document says to do it. | **Nothing.** |

**The rule this file enforces: prose is never the enforcement layer.** A guardrail whose only home is
a README, a docstring, or a review checklist is an *unenforced intention* and is reported as a finding
regardless of how well it is written. Documentation explains a control; it never *is* one.

Two corollaries:

- **Push each control down the stack as far as it will go.** If tenant isolation can be enforced by
  the database role rather than by remembering a `WHERE` clause, it belongs in the database. This is
  [P6](PRINCIPLES.md) — two independent layers, not one.
- **A control's position is part of its specification.** "We validate egress URLs" is not a
  requirement; "every user-influenced outbound URL passes the SSRF guard, enforced by an
  import-linter contract that fails the build" is.

Each layer below lists its guardrails and the **required position**. Task-2-style audits report the
*actual* position against this column; anything at `prose` or `absent` is a finding.

---

## 1. Infrastructure & host

| Guardrail | Required position |
|---|---|
| Hardened host baseline expressed **as code**, not as a runbook | environment (IaC) |
| Drift detection against that baseline, alerting on divergence | policy/CI |
| Immutable patch waves — hosts replaced, never patched in place | environment |
| Containers run **non-root**, read-only root filesystem, no capabilities beyond need | environment (image + runtime) |
| Agent/automation execution is **sandboxed**, with an **egress allow-list** | environment |
| Workload credentials are **short-lived and workload-scoped** (no long-lived static keys) | environment |

*Rationale:* an attacker who reaches a host should find a machine that can only talk to the things
its job requires. Egress allow-listing is the single highest-value host control for a service that
runs model calls and outbound webhooks, because it converts "arbitrary exfiltration" into "denied by
default".

## 2. Network

| Guardrail | Required position |
|---|---|
| TLS everywhere; **HSTS** on production responses | middleware (+ edge) |
| Segmentation: database, cache and internal services are **never internet-routable** | environment |
| **SSRF guard on every user-influenced outbound URL** — allow-list + private/link-local/loopback/metadata blocking, re-validated on redirect, DNS-rebinding-safe | middleware, **plus policy/CI proving no outbound path bypasses it** |
| Rate limits at the edge as well as in the app | environment (edge) + middleware |

*Cites [P6](PRINCIPLES.md): "egress is hostile."* The critical detail is the second position on the
SSRF row: a guard that exists but is applied by hand at each call site is one forgotten call away from
useless. The build must be able to prove no user-supplied URL reaches an HTTP client directly.

## 3. Database

| Guardrail | Required position |
|---|---|
| `FORCE ROW LEVEL SECURITY` (not merely `ENABLE`) on every tenant table | environment (DB) |
| Tenant context set **transaction-scoped**, so a pooled connection cannot leak it to the next transaction | environment (DB) |
| The application role **cannot bypass RLS**; a separate privileged role is used only for explicitly trusted flows | environment (DB) |
| Statement and lock timeouts bounded | environment (DB config) |
| Destructive migrations (drop/truncate/type-narrowing) gated by an explicit approval | policy/CI |
| **Cross-tenant isolation tests over the real tenant tables** run in CI | policy/CI |
| Backups immutable and held off-account; restores exercised | environment + policy/CI |

*Cites [P6](PRINCIPLES.md).* Isolation belongs in the database because that is the only position that
survives a missing `WHERE org_id=`. Transaction scoping is not a detail: with a transaction-mode
pooler, session-scoped context is **actively dangerous** — it hands one tenant's context to the next
tenant's transaction.

## 4. Application

| Guardrail | Required position |
|---|---|
| **Parse, don't validate** at every boundary — untrusted input becomes a typed object or is rejected | middleware (schema layer) |
| **Route-coverage test**: every route is behind auth **or** on an explicit public allow-list | policy/CI |
| Authorization is **roles → permissions**, never a scattering of boolean flags | middleware + policy/CI |
| Errors are **RFC 9457 Problem Details**; no stack traces, no internal identifiers | middleware |
| Secrets read only from the settings object (env / secret manager) — never `os.environ` in app code | policy/CI |
| **Idempotency on mutations** | middleware |
| **Vendor SDKs only at adapter edges** | policy/CI (import-linter) |

*Cites [P1](PRINCIPLES.md) (the app imports the port, never a vendor SDK), [P5](PRINCIPLES.md)
(idempotency), [P7](PRINCIPLES.md) (secrets).* The route-coverage test is the load-bearing one: it
converts "we always remember to add the auth dependency" from a habit into a build failure, and it is
the only guardrail that catches a *newly added* unauthenticated route.

## 5. API platform

| Guardrail | Required position |
|---|---|
| API keys: identifiable prefix, **hashed at rest**, per-key scopes, expiry, rotation, last-used | middleware + environment (storage) |
| Machine-to-machine auth via **OAuth2 client-credentials**, not shared static secrets | middleware |
| Per-key rate limits and quotas | middleware |
| Outbound webhooks **HMAC-signed**; inbound webhooks signature-verified **and replay-protected** | middleware |
| Contract lint + **breaking-change gate** on the published API | policy/CI |
| CORS strict by default (no wildcard with credentials) | middleware |

## 6. Served responses

| Guardrail | Required position |
|---|---|
| Content-Security-Policy, `frame-ancestors`, `X-Content-Type-Options`, `Referrer-Policy` | middleware |
| Cookies: `Secure`, `HttpOnly`, explicit `SameSite`; CSRF posture stated and enforced for any cookie-authenticated surface | middleware |
| **No secret in any client-served artifact**, proven by a scan | policy/CI |

*A bearer-token API has little CSRF surface — but any cookie-authenticated surface (an admin panel,
a docs portal) reintroduces it, and inherits this row in full.*

## 7. AI layer

| Guardrail | Required position |
|---|---|
| **Every model call goes through the port/gateway**, with a budget attached | policy/CI (import-linter) + middleware |
| **Prompt-injection defense is architectural**: untrusted content is structurally separated from instructions — never concatenated into them | middleware (call construction) |
| **Model output is untrusted input to deterministic code** — validated/parsed before it reaches anything executable | middleware |
| Tool scopes minimized per call; no ambient authority | middleware |
| Skills/prompts/tools are **pinned and reviewed**, never fetched-and-executed | policy/CI |

*The second and third rows are the ones teams get wrong.* Prompt injection is not solved by
instructing a model to ignore instructions; it is reduced by never placing untrusted text where
instructions are read, and by treating everything a model emits as hostile until parsed. A model that
can call a tool has exactly the authority of that tool — so the tool, not the prompt, is where the
limit belongs.

## 8. Build factory

| Guardrail | Required position |
|---|---|
| Pre-tool-use hooks blocking writes to protected paths, destructive operations, and secret reads | environment (agent harness) |
| Automation sessions sandboxed, with least-privilege tokens | environment |
| Branch protection with **enforced** required checks, admins included | policy (repo settings) |
| A gate job that fails — not skips — when any upstream job fails | policy/CI |

*The last row exists because a skipped required check is treated as passing by branch protection: a
naive summary job inverts into a rubber stamp exactly when the build is red.*

## 9. Supply chain

| Guardrail | Required position |
|---|---|
| GitHub Actions **SHA-pinned**; base images **digest-pinned** | policy/CI |
| SBOM generated and retained per release | policy/CI |
| Dependency and image vulnerability scanning | policy/CI |
| Build provenance **signed** (keyless/OIDC) and attested | policy/CI |
| **Secret scanning** on every commit and in CI | policy/CI |
| **Package-existence verification** before a dependency is added (defeats hallucinated/typosquatted names) | policy/CI |
| **Release-age cooldown** on new dependency versions, across *every* ecosystem in use | policy/CI |

## 10. Identity

| Guardrail | Required position |
|---|---|
| Platform mode: **OIDC/JWKS signature verification**; issuer, audience and claim names configured, never hard-coded | middleware |
| MFA-capable (TOTP at minimum) for interactive identities | middleware |
| Standalone mode: short access tokens + **rotating refresh with reuse detection** + revocation denylist | middleware |
| Token/version invalidation on credential change ("log out everywhere") | middleware |

## 11. Data governance

| Guardrail | Required position |
|---|---|
| **PII-scrubbing log processor** — redaction happens in the logging pipeline, not at call sites | middleware |
| Retention and deletion schedules expressed **as code** | policy/CI |
| Caches, rate-limit buckets and idempotency records **tenant-scoped by construction** | middleware |
| Data residency is a **deploy parameter**, not a code branch | environment |

*Cites [P7](PRINCIPLES.md).* Scrubbing belongs in the processor chain for the same reason isolation
belongs in the database: a call-site discipline fails the first time someone logs an object they
didn't write.

## 12. Process

| Guardrail | Required position |
|---|---|
| Each module ships a **threat section** — STRIDE against its ports and its data | policy/CI (artifact required to merge) |
| **Every incident finding lands as a mechanical guardrail**, not as a lesson-learned paragraph | policy/CI |
| Restore drills executed on a schedule, with the result recorded | policy/CI |
| A **vulnerability disclosure path** — `SECURITY.md` and `/.well-known/security.txt` | environment (served) + policy/CI |

> **Audit correction (layer 12).** An earlier audit pass reported this repo as having no disclosure
> path at all. That was too broad: `template/SECURITY.md` **does** ship into every generated service.
> The accurate, narrower finding is that **the template repository itself has no `SECURITY.md`**, and
> neither the template nor its generated services serve `/.well-known/security.txt`. Recorded as a
> visible edit rather than a silent rewrite — an audit that quietly corrects itself is not auditable.

*The second row is the one that compounds.* An incident that produces a document produces nothing; an
incident that produces a failing test, a lint rule, or a denied capability cannot recur silently. This
is the process-level statement of the doctrine in §0.

---

## 13. Enforcement status — guardrails proven in this repo

A guardrail moves onto this table only when it is enforced at its required position **and** a test or
gate demonstrates the failure it prevents. Evidence is a path, not a claim.

### Gate conventions

Three rules for building or changing a gate. Each was learned from a failure in this repo, cited
inline — they are not preferences.

- **Enumerate from the source of truth; never hand-maintain the list a gate checks.** A hand-kept
  list stops covering what it claims the moment someone adds a thing and forgets the list, and it
  fails *silently* — the gate still passes. *Evidence:* P4-a's coverage gate derives its table set
  from SQLAlchemy metadata, so a new tenant table is in scope the day the model exists.
- **A gate is trusted only after it has caught a failure nobody planted.** Until then it has
  confirmed its author's expectations and nothing else. *Evidence:* the route-coverage gate found an
  anonymously readable `GET /audit` on its first full-matrix run — outside the slice being worked on,
  in code that had already shipped and been reviewed (see the note below the table).
- **A conflict resolution is an edit, and earns the same verification as one.** Re-run the gates
  before pushing a resolved branch — *evidence:* #71 was blocked by its own budget gate after a
  rebase re-added a rule on top of the cuts meant to make room for it. And **keep-both is not a
  resolution**: each side must be re-read for whether it is still true, because text can be stale on
  arrival — *evidence:* this section carried `FU-1` twice, once closed and once as its original open
  text, until the duplicate was read rather than merged.

**Row order is deterministic: layer number, then guardrail name** (cross-cutting rows, layer `—`,
last). Insert a new row into its sorted position rather than appending — every guardrail PR adds a
row here, and appending makes each one collide with every other.

| Layer | Guardrail | Position reached | Evidence |
|---|---|---|---|
| 3 | A privileged role without `BYPASSRLS` **fails loudly** instead of returning empty results | **middleware** (fail-fast on first use) | `PrivilegedRoleMisconfigured` in `db/session.py.jinja` |
| 3 | Cross-tenant isolation suite **cannot silently skip** in CI | **policy/CI** | `REQUIRE_DB_TESTS=1` exported by `.github/workflows/ci.yml` for any leg that renders `tests/test_rls.py`; the fixture calls `pytest.fail` rather than `pytest.skip` |
| 3 | **Dev matches production for the privileged role** | **environment** (the role exists) | `template/scripts/init-db/01-privileged-role.sql`, mounted by `compose.yaml` into `/docker-entrypoint-initdb.d`; `tests/test_rls.py::test_compose_provisions_a_real_bypassrls_role` asserts the created role has `BYPASSRLS`, can log in, and that re-running the script is idempotent |
| 3 | **Every tenant table is RLS-protected, or exempt by name** | **policy/CI** | `tests/test_rls.py::test_every_tenant_table_is_rls_protected` — enumerates every `organization_id`-bearing table from SQLAlchemy metadata, applies the real migration chain to Postgres, and requires each table to have a policy AND `FORCE`, or an entry in `RLS_EXEMPT_TABLES` with a stated reason. Metadata is the source of truth, so a new model is covered the moment it exists. A companion test rejects stale exemptions, scoped to capabilities the render actually ships |
| 3 | Privileged sessions **clear** tenant context rather than inheriting it | **environment** | same hook, `rls_mode="bypass"` branch |
| 3 | Tenant context is **transaction-scoped** — cannot be inherited by the next transaction on a pooled connection | **environment** (Postgres discards it at commit) | `db/session.py.jinja` — `set_config(…, true)` issued from an `after_begin` hook, per transaction, for both the tenant and privileged paths |
| 4 | **Every route is authenticated, or explicitly public** | **policy/CI** | `tests/test_route_auth.py::test_every_route_is_authenticated_or_explicitly_public` — walks the service's own OpenAPI document; an operation with no security requirement must appear by exact `"METHOD /path"` name in the committed `PUBLIC_ROUTES` frozenset. Runs in every capability leg, since the route set varies by flag |
| 4 | **No anonymously-readable audit log** | **environment** (the route does not exist) | `src/app/audit/router.py` mounts the flat `GET /audit` only under an identity capability; `tests/test_audit.py::test_audit_read_endpoint_is_not_mounted_without_an_identity_capability` asserts 404 otherwise. `record()` is unaffected — the log still appends, it just has no HTTP reader until a reader can be authenticated |
| 4 | `POST /agent` is **authenticated**, not merely rate-limited | **middleware** | `src/app/api/routes/agent.py` — `get_principal` (JWT *or* API key) where `api_keys` ships, else `current_active_user`; proven at the request level by `tests/test_health.py::test_agent_requires_authentication` asserting **401** |
| 4, 7 | **Provider SDKs only at the adapter edge** | **policy/CI** (import-linter) | `.importlinter` contract *only the ai adapter layer may import a model-provider SDK*, with exactly one `ignore_imports` entry — `app.agents.example_agent -> anthropic`, marked TEMPORARY and deleted by W1. The rule lands before the module it governs, so W1 tightens the contract by **deletion** rather than by someone remembering to add it |
| 4 | The allow-list **cannot accumulate dead entries** | **policy/CI** | `tests/test_route_auth.py::test_the_allow_list_has_no_stale_entries` — an entry naming a route the service does not expose fails the build, so `PUBLIC_ROUTES` stays a live contract rather than an append-only pre-authorization cache |
| 6 | **Admin session cookie carries its flags** | **middleware** | `src/app/admin/setup.py` passes `https_only=settings.is_production`, `same_site="lax"` through sqladmin to Starlette's `SessionMiddleware`, whose `https_only` defaults to **False**; `tests/test_admin.py::test_admin_session_cookie_is_hardened` asserts `Secure`/`HttpOnly`/`SameSite` **with production settings active**, and a companion test asserts dev-over-http still signs in — hardening that breaks local login gets reverted rather than fixed |
| 9, 6 | **Secret scanning, in two positions** | **policy/CI** (+ a local convenience) | `.github/workflows/secret-scan.yml` — gitleaks on the **PR diff** (blocking) and a **weekly full-history sweep**; `.pre-commit-config.yaml` adds the same scanner as a hook. The two positions are not redundancy: the hook is **bypassable** with `git commit --no-verify`, so it is a fast local catch, and the CI job — which cannot be skipped — is the actual control. The history sweep exists because a secret committed before this gate existed is still a live credential that no diff scan will ever see. Allowlist in `.gitleaks.toml`, anchored so a placeholder must be the *whole* value |
| 11 | **PII redaction is a processor, not a call-site habit** | **middleware** | `src/app/core/logging.py::scrub_sensitive`, inserted ahead of **every** renderer so no formatting path bypasses it; recursive to any depth, container types preserved, key set from `settings.log_scrub_keys` (defaults: password, token, secret, authorization, api_key, email — matched case-insensitively as substrings, so `token` covers `access_token`). `tests/test_log_scrubbing.py` asserts on **rendered** output, including that non-sensitive fields survive verbatim |
| — | Local validation and CI **cannot drift** | **policy/CI** | `scripts/leg-check.sh` is the single definition of "a leg passed"; `.github/workflows/ci.yml` invokes that same script with the same arguments |
| — | Slice branches **cannot absorb unrelated changes** | **environment** (agent harness) | `.claude/hooks/staged-scope.sh`, a PreToolUse guard refusing a commit whose staged paths fall outside `.claude/slice-scope` |

**The failing test that justified the change** (`tests/test_rls.py::test_tenant_context_does_not_outlive_its_transaction`)
demonstrated a real cross-tenant read against the previous implementation:

```
CROSS-TENANT READ: a consumer that set no tenant context read ['a']
because the connection still carried app.current_tenant='b2e23a62-…'
```

> **Why this row is the one to point at.** The audit finding was not found by review, by threat
> modelling, or by the engineer who wrote the module. It was found by the route-coverage gate **on
> its first full-matrix run**, in a module **outside the slice being worked on**, in code that had
> already shipped and been read. The flat `GET /audit` attached its auth dependency only under
> `{% if include_users or include_admin %}`, so an audit-only service published its entire
> append-only log — actor, action, target, JSON metadata, paginated — to anonymous callers.
>
> That is the argument of this whole document in one incident. A control's **position** is what
> makes it real: the same defect had survived every prose-level protection available — a docstring
> that described the endpoint as authenticated, a code review, and a passing test suite — because
> none of them were *positioned* to notice a route that was never asked about. Nothing changed
> about the team's care. What changed was that a gate now enumerates every route and requires an
> answer for each one.

### Open follow-ups

*Findings that become scheduled work move to the ledger ([ROADMAP.md](ROADMAP.md)); this list holds
only what is open and unscheduled.*

**Open.**

- **`RLS-DEBT` · four tenant tables are exempted as debt, not design.** `usage_events`, `invoices`,
  `customer_wallets` and `outbox_events` carry `organization_id` with no policy — surfaced by the
  gate above on its first run, and listed in `RLS_EXEMPT_TABLES` so the omission is a visible
  decision rather than an invisible absence. Ledger ticket **P4-b** closes them and deletes the
  entries. `outbox_events` is low-risk (the relay already runs BYPASSRLS); `wallet_transactions`
  needs the denormalised `organization_id` column P4-b adds, having none today.
- **`FU-2` · `include_in_schema=False` bypasses the route-coverage gate.** The walker reads the
  OpenAPI document, so a route excluded from the schema is invisible to it — one keyword argument
  disables the check for that route. Direct route-table enumeration is not a viable alternative:
  FastAPI 0.137 wraps included routers in an internal `_IncludedRouter` that exposes no `.routes`,
  so the real routes cannot be reached from `app.routes`. Proposed mechanical fix: an AST gate over
  the template source asserting `include_in_schema=False` appears only at approved sites — policy/CI,
  and independent of framework internals. *Filed, not implemented.*

**Closed** — kept for the audit trail; each names the position that now holds it.

- ~~**`FU-1` · dev/prod parity for the privileged role.**~~ **CLOSED.** `database_url_privileged`
  fell back to `database_url`, so a default local environment ran the "privileged" session as the
  ordinary app role. The local compose stack now provisions a dedicated `BYPASSRLS` role, so the dev
  topology matches production — the *Dev matches production for the privileged role* row above.
- ~~**`FU-3` · `leg-check.sh` should refuse a dirty worktree.**~~ **CLOSED.** `copier --vcs-ref HEAD`
  renders uncommitted edits, so a leg-check on a dirty tree validated something the commit did not
  contain. `scripts/leg-check.sh` now fails fast when `git status --porcelain` is non-empty, with
  `LEG_CHECK_ALLOW_DIRTY=1` as the deliberate override.

---

## How to use this file

- **Building a module:** read the layers your module touches; implement each guardrail at its required
  position. A guardrail you implement one position weaker than required is a deliberate exception and
  needs to be recorded as one.
- **Auditing:** for each guardrail, establish the *actual* position with file/line or config evidence.
  `prose` and `absent` are findings. Severity follows blast radius — cross-tenant and
  credential-exposure findings outrank everything else.
- **Reviewing a fix:** the question is never "is it handled?" but "**at which position**, and can it be
  bypassed by code that doesn't know it exists?"
