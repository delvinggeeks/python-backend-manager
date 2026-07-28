# ROADMAP.md — the ledger

> **The single ledger of OPEN work.** One numbering, one home. There is no separate overlay and no
> mapping document: a mapping between two sources *is* two sources. Read a phase when you are about
> to select or size work — this file is JIT, never always-read.

## How the ledger works

**Landed work exits.** A shipped phase is deleted from here, not annotated. Its record lives in
[CHANGELOG.md](../CHANGELOG.md) (what changed) and, for anything enforced,
[SECURITY-BASELINE.md](SECURITY-BASELINE.md) §13 (where the guardrail lives, with an evidence path).
A ledger that keeps its completed items becomes an archive, and an archive is read by nobody.
**P1–P8 shipped through v0.35.0 and have left this file.** What is shipped is listed once, in
[COVERAGE-MATRIX.md](COVERAGE-MATRIX.md).

**Exits are decided per phase, on shipped evidence — never by deleting a grouping.** Wave headings
group by *theme*; ship status accrues per *phase*. The two do not align, and assuming they do loses
work or keeps it. P8 shipped as v0.35.0 but sits under the Wave 4 heading, so removing Waves 0–3
left it behind; it was caught by checking phases against the changelog, not by reading the outline.
Before removing anything, confirm that phase's evidence in [CHANGELOG.md](../CHANGELOG.md) or
[SECURITY-BASELINE.md](SECURITY-BASELINE.md) §13 individually.

**Two levels, deliberately.**

- **Phases are COARSE** — outcome, hard outer lines, blocks/blocked-by. No task detail. A phase is a
  destination, not a plan.
- **Only next-up phases carry tickets.** Every other phase carries `decompose on pull`, and that
  decomposition is itself one planning-session ticket when the phase becomes next-up. Decomposing
  early produces tickets written against a codebase that no longer exists by the time they are pulled.

**Ticket format** (mandatory fields): one-sentence deliverable · done-contract sketch (grows to full
criteria at build) · failing-test-first entry point · file-set touched · blocks/blocked-by ·
**AFK**/**HITL** tag · sized-for-one-session assertion. Where two tickets share an interface, the
interface lands as its own tiny ticket first, so the dependents are genuinely independent sessions.

**One ticket per session** — see AGENTS.md's session protocol. The sizing assertion is what makes
that rule enforceable rather than aspirational.

---

## NEXT UP — decomposed

The active queue, **in priority order: FMT-2 → ENV-2 → RESET-1 → MIG-SPLIT-1.** Ticket order in
this section is the queue; a session pulls the top one. Everything below the tickets is coarse and
carries `decompose on pull`.

*FMT-2 leads for the reason FMT-1 did, one layer down: FMT-1's headline finding was a `# renovate:`
marker that matched nothing — **a config with no gate behind it is prose**, the same doctrine §0
applies to controls, applied to the automation that maintains them. FMT-2 is the other half of that
finding, and it is small.*

*Shipped tickets have exited per the landed-work convention — T1 (#72), T2 (#73), T3 (#74) and P4-a
(#75); their evidence is in [CHANGELOG.md](../CHANGELOG.md) and
[SECURITY-BASELINE.md](SECURITY-BASELINE.md) §13. Each exit was confirmed against that ticket's own
merged PR, never inferred from the batch — T2 was held back at first pass, when #73 was still open,
and exited only once it merged.*

*`GC-1` exits with the PR that fixes it, rather than in a later pass: the evidence and the exit are
the same commit, so the ledger cannot claim a fix that did not land. Its scope was corrected against
measurement — the ticket named four SIGPIPE sites and **two** actually fire (`:70`, `:72`); `:105` is
structurally safe because `sort` buffers its whole input, and `:109` is a race that did not trigger
at 14 matching files. Both latent sites were converted anyway. Verified by dispatch, not by reading:
[run 30287201659](https://github.com/delvinggeeks/python-backend-manager/actions/runs/30287201659)
completed and opened issue #77 — the first harvest that has ever existed.*

*`DEV-1` exits the same way. Its rule was rebuilt against **measured** matcher behaviour, not against
the documented syntax: allow cannot override deny, `!` negation is ignored, and a `[!e]` character
class **fails open** — the probe that used one silently stopped denying `.env.local`. The shipped
form is layered instead: `Read(.env)` (bare, so any depth) plus `Read(/.env.*)` (root-anchored, so
any suffix at the repo root, enumerated or not) plus bare rules for the conventional suffixes. Two
findings the old rule had been concealing are filed above as **ENV-1** and **GIT-1**.*

*`ENV-1` exits with its own PR. It was larger than filed: the consumer name was in the **settings
default** too (`Settings.app_name`), so a service that never set `APP_NAME` still got it, and
`.env.example`'s database credentials **disagreed with the compose stack they describe** — copying
the file produced an authentication failure, a functional defect rather than a cosmetic one. The
model-cascade duplication was resolved by deletion, not by picking values: the single home is
`Settings.model_fast`/`model_default`/`model_frontier`, and the example now points at it. The
renamed `.jinja` path had to be un-ignored in `template/.gitignore`, whose `.env.*` rule governs
`template/` in this repo as well as shipping into services. **ENV-2** files what the render still
carries: `SECURITY.md` is verbatim, so every service sends vulnerability reports to one company.*

*`P4-b` exits with its own PR. `RLS_EXEMPT_TABLES` now holds only `memberships`. Two findings the
plan did not contain: SQLite implements neither `ALTER COLUMN ... SET NOT NULL` nor an in-place
foreign key, so the contract step needs `op.batch_alter_table` — a dialect guard would have left the
column nullable and unconstrained in exactly the database the unit suites run on; and the five-table
list rendered to 105 columns in the all-capabilities combination, the gated-block class again. The
column route held up: nothing surfaced against it, so the pre-made decision stands as made. **GATE-1**
files a fail-open found in P4-a's own enumeration while using it.*

*`LINT-1` exits with its own PR. Its scope was **narrowed by measurement**: the plan implied linting
this repo's Python wherever it lives, and an unscoped `ruff check .` reports 26 findings — 22 of them
in `template/`, under rules that template's own `[tool.ruff]` deliberately configures away (14x
`B008`, which it lists in `ignore`). Those files are already checked by the capability legs with the
config that governs them, so the gate is scoped to `scripts/`; two gates disagreeing about one file
is worse than one gate. Three of the four real findings were deliberate patterns made explicit
(`check=False`, a reasoned `noqa`) rather than silenced, and the ruff version is pinned.*

*`GIT-1` exits with its own PR. Verified in both directions rather than by reading the pattern: the
two probe files are ignored and `git add .env` is refused, AND `template/.env.example.jinja` is still
tracked — a deeper `.gitignore` takes precedence, so the root's new `.env.*` does not defeat the
negation ENV-1 added one directory down. That regression was the only real risk in a three-line
change, so it is the thing that got checked.*

*`HANDOFF-1` was filed and built in one session, and exits with its own PR — filing and building were
its single deliverable. Three findings. **AGENTS.md had no headroom**: it was at 90/90, not the 88/90
the ticket assumed, the slice-scope note having taken the rest; the budget was raised to 92 rather
than room manufactured by cutting prose that is still true, since the cut would have been the
unreviewed change. **The verification order was inverted on purpose** — the refusal was demonstrated
against this session's own unfinished state rather than a simulated one, and the emit was
demonstrated only after this note existed, which is the first moment `/handoff` can legitimately
pass its own gate. **The JIT reads are resolved by reading AGENTS.md's Reading-contract table**, not
by a copy inside the command: a second copy of that table would drift from the one sessions follow,
and a handoff naming the wrong reads is exactly the defect the command exists to prevent. One thing
it deliberately does not do: a dirty worktree is printed as a loud warning, not a refusal, because a
ticket may legitimately end with its PR open — but it is what a window-close destroys, so it is
never silent.*

*`GATE-1` exits with its own PR, and its own evidence was off in a way worth recording. **The
observed symptom was wrong, and the real defect is worse than filed:** a users-less metering sync
returns the **empty set**, not `{items}` — `items` carries no `organization_id` in any render — so
the total-wipe case was always caught by `assert tenant_tables`. The partial case the ticket
predicted but had not measured was reproduced by making one model module's dependency genuinely
missing: the enumeration returned `{memberships}`, **1 of 5** tenant tables, and the gate **passed**,
leaving `usage_events`, `invoices`, `customer_wallets` and `wallet_transactions` — the four money
tables §13 has a row for — unverified and reported green. **The shipped rule is tighter than the
sketch.** The sketch would skip any `ImportError` naming a module inside `app.`; shipped, the skip
requires the missing module to be the target itself or a package on its path, so a *different* `app.`
module going missing raises rather than shrinking the scope one level in. That was verified safe
before it was chosen: every model module's only `app.` import is `app.db.models`, which the
enumeration imports before the loop, so no render this template produces can reach the stricter
branch. **FMT-1** files what validating it surfaced.*

*`FMT-1` exits with its own PR. The defect reproduced exactly as filed — both hook arms resolved
**0.4.10**, and driving the hook at `test_rls.py` rewrote the assert at
`test_rls_exemptions_are_not_stale` with no edit anywhere in the file, which the rendered `tenancy`
leg's own ruff **0.16.0** then rejected. Three things the ticket did not contain. **The pin was
tracked by nothing:** the `# renovate: datasource=pypi depName=ruff` marker over `RUFF_VERSION=0.16.0`
matched no manager — the workflow customManager requires a `version: "…"` key and no built-in manager
parses a shell assignment inside a `run:` block — so "Renovate-tracked" was decorative, verified by
running the config's own regex over `ci.yml` (4 matches, all `astral-sh/uv`). Moving the pin to
`.ruff-version` with a customManager is what makes the claim true. **There was a *third* floating
ruff:** `.pre-commit-config.yaml`'s `--with ruff` fed `scripts/micro-render-check.py`'s bare `ruff`,
so a gate that format-checks a render ran whatever released last; it reads the pin now, which is what
"exactly one place records the version" has to mean. **And the gate that actually rejected the file
floats by design** — a capability leg resolves ruff from a fresh `uv lock` against the template's
`ruff>=0.15` floor, so the pin can only ever be *behind* it. That is real residual exposure, not a
detail, and closing it is a trade-off the ticket had not pre-decided; it is filed as **FMT-2** rather
than improvised here.*

### FMT-2 · Bound the ruff-pin lag with a cooldown, instead of gating on it

- **Deliverable:** `.ruff-version` chases the floating floor within about a day, and the residual lag
  is *accepted on the record* rather than policed by a gate.
- **Evidence:** FMT-1 gave this repo one recorded ruff version (`.ruff-version`, read by the hook,
  `repo-lint` and `micro-render-check.py`) — but the gate that *rejected* the file in FMT-1's own
  reproduction was none of those. It was the capability leg, and a leg resolves ruff from a fresh
  `uv lock` against the template's `ruff>=0.15` **floor**, so it takes whatever is newest at run
  time. Today both are 0.16.0. On the next formatter-affecting release they are not, and FMT-1's
  defect returns — one minor apart instead of twelve.
- **The legs must keep floating — do not "fix" this by pinning them.** A leg floating to the newest
  ruff is how this repo learns that a new ruff broke the template; that is the signal that caught
  0.16's markdown formatting. Any solution that pins the leg's ruff destroys the gate to protect the
  hook.
- **Decision — pre-made, which is what makes this AFK.** **Accept the lag, and shorten it.** No
  pin-equals-resolved CI check: on a stale pin it would red *every* PR for close to a week (weekly
  Renovate schedule × 3-day pypi cooldown), and **noise that trains people to ignore red costs more
  than a bounded lag that announces itself**. The §13 row already states the residual, so the honest
  record exists. What lands instead is a **ruff-specific `packageRule`** — short cooldown (~24h),
  automerge on **patch/minor only** — so the pin chases the floor within a day. That constraint is
  not the builder's to revisit; the *shape* of the rule is.
- **Verify the rule MATCHES; do not assume it does.** This is the ticket that found a `# renovate:`
  marker matching nothing, so the same standard applies to its own fix: extract the dep from
  `.ruff-version` with the customManager's own regex, then confirm the new rule selects
  `{depName: ruff, datasource: pypi}` and wins. Dry-run already done, with two results worth having
  before you start:
  - **Append it — prepending is a silent no-op.** Rules merge in order, later wins. Simulated:
    appended → `minimumReleaseAge: 1 day`; prepended → the generic pypi cooldown rule overrides it
    straight back to **3 days**, i.e. the change appears to be made and does nothing. Same class as
    §13's "insert into sorted position rather than append", pointing the other way.
  - **`matchUpdateTypes: ["minor","patch"]` leaves the major path intact** — simulated, a major still
    lands on `automerge: false` + `dependencyDashboardApproval`. Confirm Renovate classifies a
    **0.16 → 0.17** bump as `minor` under `pep440`, since that is the exact case this exists for.
- **Watch for:** `minimumReleaseAge` bounds when a release becomes *eligible*, not when Renovate
  *runs*. The repo extends `schedule:weekly` at top level, so a 24h cooldown alone still waits for
  the weekly window — the rule almost certainly needs `schedule: ["at any time"]` too. Confirm what
  `schedule:weekly` expands to rather than trusting this line.
- **Failing-test-first:** set `.ruff-version` to a version *older* than the floor resolves (e.g.
  `0.15.0`), render a leg, and show the hook and the leg formatting the same file differently —
  then show the rule that would have closed that gap within a day.
- **File set:** `renovate.json`, `docs/SECURITY-BASELINE.md` (the §13 row's residual clause becomes
  *bounded* rather than open).
- **Blocked-by:** none — FMT-1 shipped the single pin this builds on. **Blocks:** none. **AFK** —
  the noise/earliness trade is pre-made above. **Sized:** yes.

### ENV-2 · `template/SECURITY.md` sends every service's vulnerability reports to one company

- **Deliverable:** a generated service's disclosure address is the *service owner's*, not the
  template author's.
- **Evidence:** `template/SECURITY.md` has no `.jinja` suffix, so it is copied byte-for-byte, and
  line 3 reads `Report vulnerabilities to security@witaura.in`. Every service this template has
  generated instructs finders to email that address, and there is **no copier question** to override
  it — unlike `author_name` / `author_email`, which are prompted and therefore not defects.
  Confirmed on a service rendered as `acme-widgets-api` after ENV-1 landed.
- **Why this outranks a naming nit:** a disclosure path that reaches the wrong organisation is worse
  than none. The finder believes they have reported it; the operator never hears. §12 requires a
  vulnerability disclosure path at `environment` position, and one pointing elsewhere does not meet
  it.
- **Also in scope, minor:** `template/README.md.jinja:5` names the template
  `witaura-backend-template`, which is not this repository. Stale provenance, cosmetic.
- **Design decision required (do not pre-empt):** a new copier question (`security_contact`?) versus
  deriving from `author_email` versus shipping a `TODO` placeholder that a service must fill. Each
  trades safety against friction differently — decide before building.
- **Failing-test-first:** render a service and assert `SECURITY.md` contains no address the answers
  file did not supply.
- **File set:** `template/SECURITY.md` → `.jinja` (via `git mv`), `copier.yml`,
  `template/README.md.jinja`.
- **Blocked-by:** none. **Blocks:** none. **HITL** — the question design is a judgement call.
  **Sized:** yes.
- *Re-filed: the ENV-1 exit deleted this block along with ENV-1's, which sat immediately above it.*

### RESET-1 · Pool-boundary GUC reset, as a declared backstop

- **Deliverable:** a connection returned to the pool carries no `app.*` GUC, whatever set it — and
  §13 gains a row *type* that says so without claiming a failure it has not caught.
- **Evidence — and its limit, stated up front:** there is **no recorded failure**. F1 (#64) made the
  tenant GUC transaction-local (`set_config(..., true)`), and §3 already documents why: under a
  transaction-mode pooler a session-scoped value is *actively dangerous*, because the connection
  carries it to the next tenant's transaction. The shipped design cannot produce that value — the
  only writer is the `after_begin` listener, and it always writes locally. This ticket guards the
  class anyway, at the boundary where the leak would occur: the analog of PgBouncer's
  `server_reset_query`, one layer below the code that is currently correct.
- **Why it is filed despite no failure:** the hazard is a *future* session-scoped `SET`, added by
  app code or a library, which the current design has no mechanism to prevent — only a convention
  against. A backstop at the pool boundary makes the convention unnecessary for safety.
- **The row type is the real deliverable.** §13's opening sentence currently admits a guardrail only
  when "a test or gate demonstrates the failure it prevents". This row cannot meet that and must not
  pretend to. Add to the **Gate conventions** preamble a fourth bullet defining two row kinds:
  *demonstrated-failure* rows (evidence is a path to the failure caught) and *declared-backstop*
  rows (guards a class the current code cannot produce; no demonstrated failure; **upgrades** to
  evidence-carrying the first time it fires). **The second must never masquerade as the first** —
  that is the whole point of naming them, since an undifferentiated table lets a rationale row
  inherit the credibility of an evidence row.
- **Failing-test-first:** the synthetic test *is* the entry point, and it is synthetic by
  construction — deliberately issue a session-scoped `set_config('app.current_tenant', ..., false)`,
  return the connection, and assert the next checkout sees it still set. That assertion passes today;
  it is the failure the backstop then removes.
- **Sketch:** a `checkin` pool-event listener issuing `RESET` for the `app.*` GUCs; the synthetic
  test above; the §13 row under the new type; the preamble bullet; and **one line in §3**, beside the
  existing transaction-scoping paragraph — *transaction-scope is the design; checkin-reset is the
  backstop. The reset does not license session-scoped sets: the factory structure test still enforces
  the source.* Without that line the backstop reads as permission.
- **File set:** `template/src/app/…db/session.py.jinja`, `template/tests/{% if include_rls %}test_rls.py{% endif %}`,
  `docs/SECURITY-BASELINE.md` (§3 line, §13 preamble bullet + row).
- **Blocked-by:** none. **Blocks:** none. **AFK.** **Sized:** yes.

### MIG-SPLIT-1 · `0012_wallet_org` is one revision doing three deployable steps

- **Deliverable:** future renders get expand, backfill and contract as three independently
  deployable and reversible revisions instead of one.
- **Evidence:** `0012_wallet_org.py.jinja` performs all three inside a single `upgrade()` —
  comment-delimited at lines 44 / 49 / 58, but one revision and one transaction. An operator
  therefore cannot verify the backfill in production *before* the column becomes `NOT NULL`, which
  is the entire operational reason the expand→contract shape exists. The migration's own docstring
  already explains the three steps, so the intent is present and only the packaging is wrong.
- **Scope boundary — read before starting:** already-generated services **keep the merged
  revision**; there is no rewrite of applied history and no data migration. This is forward-looking
  template hygiene for services rendered after it lands, and a service that already ran `0012` is
  correct as it stands.
- **Failing-test-first:** render a metering service and show `alembic history` listing one revision
  between `0011_metering` and `0013_rls_backfill`, then assert what does not yet exist — that
  stopping after the expand step leaves a schema the application can still run against.
- **Sketch:** three revisions chained `0011_metering → expand → backfill → contract →
  0013_rls_backfill`, each with a working `downgrade()`; `0013`'s `down_revision` follows the new
  tail. Each docstring gains the operator sentence: *this chain may be applied across separate
  production releases (expand → backfill → contract-after-verification)*. Round-trip both directions
  under the RLS legs.
- **File set:** `template/…/versions/{% if include_metering %}0012_wallet_org.py{% endif %}.jinja`
  (split), the two new revision files, `template/…/versions/{% if include_rls %}0013_rls_backfill.py{% endif %}.jinja`
  (`down_revision`).
- **Blocked-by:** none. **Blocks:** none. **AFK.** **Sized:** yes.
- *Lowest priority in NEXT UP: nothing is unsafe today, and no shipped service is affected.*

## Wave 4 — platform seams (value-ordered; mostly independent)

### P9 · Notifications (multi-channel)  🟠
- **Scope:** `NotificationPort` generalizing `EmailPort` (email becomes one adapter); **in-app feed
  (Postgres)** + email defaults; SMS (MSG91), WhatsApp (Gupshup), push (FCM) adapters; per-user
  preferences + quiet hours; Novu orchestrator as a seam. Retrofit of `email`.
- **Toggle/Port:** `include_notifications` (generalizes email); `NotificationPort`,
  `notification_provider` per channel.
- **Implies/Deps:** email; db (in-app feed + prefs). DLT registration is an ops doc.
- **DoD:** email + in-app send via the port; SMS/WhatsApp/push adapters no-op-when-unconfigured;
  preference/opt-out honored; quiet hours respected.
- **CI:** `notifications` (ALONE: email+db) + `notifications_full` (+users) rows; no live providers.
- *decompose on pull*

### P10 · Authorization port (ReBAC seam)  🟡
- **Scope:** thin `AuthorizationPort` (`check(subject, action, resource)`) wrapping the current role
  hierarchy as the default adapter; a Cerbos adapter **stub**. Retrofit of `rbac`.
- **Toggle/Port:** `authz_engine` setting (default `rbac`); `AuthorizationPort`.
- **Implies/Deps:** rbac.
- **DoD:** existing role checks route through the port unchanged; stub raises NotImplemented; no
  behavior change (byte-identity of role decisions).
- **CI:** `authz` row (ALONE) — role checks via the port.
- *decompose on pull*

### P11 · Durable workflows  🟠
- **Scope:** `WorkflowPort` for long multi-step flows; arq adapter (simple) + **DBOS Transact**
  adapter (Postgres-native durable). Keep `enqueue()` as the simple `TaskQueuePort`.
- **Toggle/Port:** `include_workflows` (implies jobs + db); `WorkflowPort`, `workflow_engine` setting.
- **Implies/Deps:** jobs (worker) + db.
- **DoD:** a multi-step workflow survives a mid-run crash (durable adapter); arq adapter covers the
  simple case; no-infra test uses the in-Postgres durable path on sqlite or a fake.
- **CI:** `workflows` row.
- *decompose on pull*

### P12 · Datasource bridge (tenant→DB)  🟠
- **Scope:** `DatasourcePort` (`get_session_factory(tenant_id)`) with a pooled-shared default and a
  silo adapter (per-tenant engine registry). Pairs with P4 RLS. Retrofit of `tenancy`/`db.session`.
- **Toggle/Port:** `DatasourcePort` (pooled default); silo via config registry.
- **Implies/Deps:** tenancy. Silo adapter unit-tested with a mock (no second DB in CI).
- **DoD:** all queries go through the port; pooled default unchanged; silo routing covered by a
  mock-engine test; no query-site changes.
- **CI:** `tenancy` rows (pooled) + a datasource-port unit test.
- *decompose on pull*

### P13 · Enterprise identity (SSO/MFA)  🟠
- **Overlay merged (was W3):** a narrower, EARLIER slice lands first — an OIDC/JWKS *verifier* for `platform` mode (stateless; no local user tables). Full SSO/MFA remains this phase's scope.
- **Scope:** `AuthnPort` + an OIDC adapter (authlib); SAML/SCIM stubs; self-host Authentik seam doc;
  **TOTP MFA** (`pyotp`) behind a toggle; passkeys later. Builds on P3.
- **Toggle/Port:** `include_sso` (OIDC), `include_mfa` (TOTP); `AuthnPort`, `authn_provider` setting.
- **Implies/Deps:** users (+ P3).
- **DoD:** OIDC login flow works against a mock IdP; TOTP enroll+verify; default jwt path unchanged;
  no-infra tests use a fake OIDC discovery doc.
- **CI:** `sso` + `mfa` rows (ALONE, users) — no live IdP.
- *decompose on pull*

### P14 · Secrets provider seam  🟠
- **Overlay merged (was W12 day-0):** this phase IS the day-0 secrets story; W12/P45 adopts it rather than restating it.
- **Scope:** `SecretsPort` with the env/`.env` default adapter + an Infisical adapter stub.
- **Toggle/Port:** `secrets_provider` setting (default `env`); `SecretsPort`.
- **Implies/Deps:** none.
- **DoD:** `get_settings()` sources through the port; env adapter byte-identical to today; stub
  documented.
- **CI:** `secrets` row (ALONE) — env adapter.
- *decompose on pull*

### P15 · PII field-level encryption  🟠
- **Scope:** `EncryptionPort` + SQLAlchemy `EncryptedType`; envelope encryption with a local DEK
  default + a KMS adapter seam; apply to sensitive columns when on.
- **Toggle/Port:** `include_pii_encryption`; `EncryptionPort`/`KMSPort`.
- **Implies/Deps:** db. India-region hosting documented.
- **DoD:** encrypt/decrypt round-trips transparently via the ORM; off = plaintext byte-identical;
  KMS adapter stubbed; latency noted.
- **CI:** `pii_encryption` row — round-trip on sqlite.
- *decompose on pull*

### P16 · Data-subject rights (export + erasure)  🟠
- **Scope:** export (async arq job → signed URL) + **crypto-shredding** erasure (drop the P15 key) +
  soft-delete + weekly purge; per-subject data map; audit-logged.
- **Toggle/Port:** `include_data_rights`.
- **Implies/Deps:** db; **P15 (encryption) + P5 (outbox)**.
- **DoD:** export produces a complete per-subject bundle; erasure renders PII unreadable without
  mutating the append-only audit log; actions audited first.
- **CI:** `data_rights` row.
- *decompose on pull*

### P17 · API versioning & pagination conventions  🟠
- **Overlay merged (was W9, part):** the pagination convention is a *gate input*, not a doc convention — the contract lint asserts exactly one convention across collection endpoints.
- **Scope:** URL `/v1` versioning, cursor/keyset pagination helper (`fastapi-pagination`),
  RFC-8594/9745 Deprecation/Sunset middleware.
- **Toggle/Port:** `include_api_conventions` (or fold into the `api` extra).
- **Implies/Deps:** none.
- **DoD:** versioned mount + cursor params + deprecation headers on an example route; docs.
- **CI:** `api` row.
- *decompose on pull*

### P18 · Feature flags  🟡
- **Scope:** `FeatureFlagPort` with a Postgres flag-table default adapter (OpenFeature-shaped); Unleash
  adapter seam.
- **Toggle/Port:** `include_feature_flags`; `FeatureFlagPort`, `flags_provider` setting.
- **Implies/Deps:** db.
- **DoD:** flag eval via the port (cached); DB adapter default; Unleash stub.
- **CI:** `feature_flags` row.
- *decompose on pull*

### P19 · Search port  🟡
- **Scope:** thin `SearchPort` over Postgres-native full-text (`tsvector`/GIN) + `pgvector`; external
  engine (Meilisearch/Qdrant) as a documented seam, **not built**.
- **Toggle/Port:** `include_search`; `SearchPort`, `search_backend` setting.
- **Implies/Deps:** db.
- **DoD:** full-text + vector query via the port on Postgres; external adapter stubbed.
- **CI:** `search` row.
- *decompose on pull*

### P20 · Cost & ops defaults  🟡 (mostly docs + light code)
- **Scope:** document **Cloudflare R2 (zero-egress)** as the recommended storage default endpoint;
  document the managed-observability free-tier seam (Axiom/SigNoz); add the **SLO/error-budget** doc +
  extended `/readyz` timeout-bounded checks + graceful-degradation/circuit-breaker on flaky externals.
- **Toggle/Port:** none new (uses existing storage/observability seams).
- **Implies/Deps:** none.
- **DoD:** README/`.env.example` recommend R2; `/readyz` checks are timeout-bounded; SLO doc shipped;
  a **backup/DR + data-retention posture** doc (PITR/snapshot guidance + per-data-class retention
  windows tied to DPDP) — *skeptic-review addition: durability/retention was implied but unstated*.
- **CI:** existing rows; readyz test asserts timeout behavior.
- *decompose on pull*

---

## Wave 5 — AI-native application layer (the usage-priced AI product surface)

Specs in [AI-AGENTIC-STACK.md](AI-AGENTIC-STACK.md). Inherits the P3 matrix; **no-infra tests mock
LLM calls** (no live provider keys). The throughline: the gateway/engines are seams, the **token
cost-metering is the core** (ties to P7).

### P21 · LLM gateway + per-tenant token metering  🔴 ⭐
- **Overlay merged (was W1):** the `ai` module — `LLMPort` (pure, no DB), an `ai/service.py` facade as the sole caller (metering + `gen_ai.*` spans unskippable by import-linter), ONE OpenAI-compatible HTTP adapter (no provider SDKs in the tree), prompt registry, evals seam. `ai_layer: none|port`, default `port`.
- **Scope:** `LLMPort` (LiteLLM **SDK in-process** default) with provider routing + fallback,
  **prompt caching** + **semantic caching** (Redis), and a **token-usage → `MeteringPort`** bridge
  with per-tenant **budget caps (429 on exceed)**. Charge via the existing `PaymentsPort`.
- **Toggle/Port:** `include_llm_gateway` (implies `llm`); `LLMPort`, `llm_gateway` setting.
- **Implies/Deps:** llm; **P7 metering** (for billing tie-in — degrades to log-only when metering
  absent); cache (Redis) for caching.
- **DoD:** per-call usage parsed (input/output/cache tokens → cost) and metered per tenant; a tenant
  over budget gets 429; caching demonstrably reduces tokens; works against a **mocked provider** (no
  live key).
- **CI:** `llm_gateway` row (ALONE: llm+cache) + `llm_gateway_full` (+billing metering) under a fake
  provider + unreachable Redis (caching degrades open).
- *decompose on pull*

### P22 · Agent runtime seam + GenAI tracing  🟠
- **Overlay merged (was W2):** collapse `agent_framework` (4 values) to `ai_layer: none|port`; drop langgraph/openai-agents extras; copier `_migrations` rewrites stored answers; `feat!:` major.
- **Scope:** a thin **`AgentRuntime`/`AgentPort`** wrapping the framework toggles (pydantic-ai default;
  retrofit `example_agent.py`); emit **OTel GenAI spans** (tokens/cost/model/tool calls) via the
  existing observability seam; per-call cost + usage-cap; long runs wrap **`WorkflowPort` (P11)**.
- **Toggle/Port:** uses `agent_framework` + `include_observability`; `AgentPort`.
- **Implies/Deps:** an agent framework extra; observability (for GenAI spans, gated).
- **DoD:** the `/agent` route runs via the port for each framework; GenAI spans emitted when
  observability on; no behavior change when off (byte-identity); durable variant checkpoints via P11.
- **CI:** framework matrix rows assert the runner + (when observability) span attributes, mocked LLM.
- *decompose on pull*

### P23 · RAG / RetrievalPort  🟠
- **Scope:** build the `rag` module — `RetrievalPort` with a **pgvector-native** hybrid search
  (tsvector + vector, RRF) + ingestion (`pypdf` + `semantic-text-splitter`) + `EmbeddingPort`
  (`text-embedding-3-small` default) + optional `RerankPort`; Qdrant adapter seam.
- **Toggle/Port:** `include_rag` (implies db + pgvector); `RetrievalPort`/`EmbeddingPort`/`RerankPort`.
- **Implies/Deps:** db (pgvector). DPDP-cascade delete by collection.
- **DoD:** ingest→chunk→embed→store→hybrid-retrieve works on sqlite/pgvector test path with a mocked
  embedder; rerank optional; tenant-scoped + erasable.
- **CI:** `rag` row (db) with a fake embedding function.
- *decompose on pull*

### P24 · Agent memory / MemoryPort  🟠
- **Scope:** `MemoryPort` — Postgres `threads`/`messages`/`memory_facts` (+ pgvector long-term),
  RLS-isolated, **DPDP TTL + audit + erasure**; composes with `RetrievalPort` (P23) + `WorkflowPort`
  (P11); Mem0/Zep adapter seams.
- **Toggle/Port:** `include_memory` (implies db); `MemoryPort`, `memory_provider` setting.
- **Implies/Deps:** db; pairs with P23/P11; erasure ties to P16.
- **DoD:** add/fetch thread + semantic fact retrieval via the port; tenant-isolated; TTL/erase works;
  mocked embedder for no-infra.
- **CI:** `memory` row (db).
- *decompose on pull*

### P25 · LLM evals + eval-gate + tracing backend  🔴
- **Scope:** a **DeepEval** harness (`evals/`) + a CI **eval-gate** (accuracy/safety/cost-delta
  thresholds, LLM-as-judge) wired into the `generate (capability)` gate; a Langfuse/Phoenix
  tracing-backend adapter behind the OTLP seam (off by default).
- **Toggle/Port:** `include_evals` extra; tracing backend via `OTEL_*` endpoint.
- **Implies/Deps:** an agent framework (evals target model calls). Uses a **mocked/cheap judge** in CI.
- **DoD:** `just evals` runs locally; the CI gate blocks a regression beyond threshold; baselines
  stored in-repo; no live provider needed (recorded fixtures / mock judge).
- **CI:** an `evals` leg on framework rows (skips `none`); thresholds gate merge.
- *decompose on pull*

### P26 · Guardrails + prompts + MCP tool safety  🟠
- **Scope:** `GuardrailPort` (`instructor` + LLM-Guard PII/injection + Guardrails AI; PII redaction
  ties to P15); `PromptPort` (Postgres prompt registry + versioning + A/B via `FeatureFlagPort` P18);
  `MCPToolPort` (per-tenant tool scoping + **SSRF guard reused from P1** + sandboxed-execution seam).
- **Toggle/Port:** `include_guardrails`, `include_prompts`; extends `include_mcp`.
- **Implies/Deps:** llm; P1 (SSRF), P15 (PII), P18 (flags) where present.
- **DoD:** injection/PII scan on the prompt boundary; schema-enforced output; prompt fetch-by-label;
  MCP tools scoped per tenant + URL-fetch tools SSRF-guarded; all no-op-safe when unconfigured.
- **CI:** `guardrails` + `mcp` rows (mocked LLM; SSRF unit test).
- *decompose on pull*

---

## Wave 6 — client surface, agent-safety & alternative payments

The 360°-coverage additions ([COVERAGE-MATRIX.md](COVERAGE-MATRIX.md)). Each inherits the P3 matrix;
cross-wave deps noted. **P29 is security-critical and gates production agents.**

### P27 · Real-time updates  🟠
- **Scope:** `RealtimePort` + a **FastAPI WebSocket/SSE** default adapter over a **Redis pub/sub
  backplane** (channels `tenant:{id}:{channel}`); presence (Redis-TTL); **missed-message backfill
  from the transactional outbox (P5)**; per-tenant channel **authorization via `AuthorizationPort`
  (P10)**; connection/message rate-limit via `RateLimitPort` (P8); graceful degrade when Redis down.
- **Toggle/Port:** `include_realtime` (implies cache); `RealtimePort`, `realtime_provider` setting.
- **Implies/Deps:** cache (Redis backplane); db + **P5 outbox** (reliable backfill).
- **Alternatives/seam:** self-host **Centrifugo** (BSD) / Soketi; managed **Ably/Pusher** (6-10× cost).
- **DoD:** WS connect/subscribe/publish/presence/backfill; JWT auth + per-channel authz; backfill from
  outbox; rate-limit present; **mocked Redis** in the no-infra test (degrades to single-worker).
- **CI:** `realtime` row (ALONE: cache) with a fake WS client + mocked pub/sub.
- *decompose on pull*

### P28 · Mobile / BFF backend support  🟠
- **Scope (BUILD-NOW backend caps):** a **version-gate `/config`** endpoint (force-upgrade /
  min-version), an **APNs** adapter alongside FCM (extends `NotificationPort`, P9), **app-attestation
  verify** (Play Integrity / Apple App Attest — block tampered clients), OAuth2 **PKCE** for native +
  **deep/universal-link** resolution. **SEAM-NOW:** an offline-first **`SyncPort`** (delta sync +
  change-tokens). **Out-of-scope:** the app itself.
- **Toggle/Port:** `include_mobile` (+ `mobile_capabilities`); `MobileConfigPort`, `AttestationPort`,
  `SyncPort` (stub).
- **Implies/Deps:** users (auth) + notifications (push). Attestation uses free Google/Apple APIs.
- **Alternatives (sync seam):** **PowerSync** (OSS self-host) / **ElectricSQL** (Postgres-native) /
  Replicache — built only when a mobile service needs offline.
- **DoD:** `/config` returns version policy; attestation token verified (fail-open + logged on first
  pass); APNs adapter no-ops unconfigured; PKCE flow; `SyncPort` stub documented. Mocked attestation
  in CI.
- **CI:** `mobile` row (users) — version-gate + attestation verify (mocked), no live Apple/Google.
- *decompose on pull*

### P29 · AI agent **system-safety** (jailbreak / least-privilege)  🔴 ⭐ (gates production agents)
- **Scope:** defense-in-depth against a jailbroken / prompt-injected agent **acting on the system**
  (the "lethal trifecta": private-data access + untrusted content + exfiltration), layered onto the
  existing ports — **no new infra**. Six BUILD-NOW controls:
  1. **`AgentPolicy` (least-privilege):** agent identity distinct from the user; per-tenant scoped
     **capability tokens** (allow/deny tool lists, short TTL); **no raw DB/secret access**;
     kill-switch. (seam: AuthnPort + AuthorizationPort/P10)
  2. **MCP tool hardening:** per-tenant tool scoping, **tool-description signature** (anti-poisoning),
     **strict arg-schema validation**, output PII redaction, **SSRF egress reuse (P1)**. (seam: MCPToolPort/P26)
  3. **Human-in-the-loop approval** for destructive/irreversible/high-value actions (plan-then-execute,
     2FA on HIGH/CRITICAL, logged). (seam: AuthorizationPort + AuditPort + NotificationPort)
  4. **Memory admission control** (anti-MINJA): trust-scored ingestion, consistency check, TTL,
     causal attribution. (seam: MemoryPort/P24)
  5. **Per-agent spend caps + runaway-loop detection** (hard 429 at budget; anomaly pause at ≥3×
     baseline). (seam: MeteringPort/P21 + RateLimitPort/P8)
  6. **Immutable agent-action audit** (every tool call + cost + risk + injection-score; OTel GenAI
     span). (seam: AuditPort)
  Mapped to **OWASP Agentic Top-10 (2025)** + **MITRE ATLAS**.
- **Toggle/Port:** ships with the agent capability; `AgentPolicy` + the control hooks on existing ports.
- **Implies/Deps:** an agent framework; P10 (authz), P26 (MCP/guardrails), P1 (SSRF), P21 (spend),
  audit. **Must land before any production agent with tools/memory** (P22+).
- **DoD:** an agent cannot call a tool outside its capability list; a destructive action requires
  approval; a poisoned tool signature is rejected; a budget-exceeded agent gets 429 + pause; every
  action is audited; threat-sim tests (injection, memory-poison, runaway) pass — all against a
  **mocked LLM**, ₹0 infra.
- **CI:** `agent_safety` row — capability-deny, arg-injection-reject, spend-cap, approval-gate tests.
- *decompose on pull*

### P30 · Crypto / blockchain payments  🟠 (+ ⚠ India compliance gate)
- **Scope:** a **`CryptoPaymentAdapter` behind the existing `PaymentsPort`** (Option A — crypto is
  just another method). Default **self-host BTCPay Server** (non-custodial, **0% fee**, MIT) for
  BTC/Lightning + **Beldex (BDX)** via its AEON-Pay/BTCPayServer integration; **NOWPayments** +
  **stablecoins (USDC/USDT on Polygon/Solana)** as the practical low-fee path; **idempotent
  on-confirmation webhook reuses `ProcessedEvent`** (`(provider,invoice_id,status)` dedupe on N
  confirmations).
- **Toggle/Port:** `include_crypto_payments`; `PaymentsPort` crypto adapter, `crypto_provider` setting.
- **Implies/Deps:** billing/payments. Web3.py for EVM stablecoins; httpx for BTCPay Greenfield / Beldex RPC.
- **⚠ COMPLIANCE GATE (DECISIONS-NEEDED D14):** India VDA law — **30% tax + 1% TDS**, **mandatory
  FIU-IND registration** for VDA service providers (PMLA), **FEMA** does *not* recognize crypto as
  forex (an Indian exporter accepting crypto loses FIRC → GST export benefit), and **privacy coins
  (Beldex) draw AML scrutiny**. Ship the adapter **off by default** with the compliance caveats
  documented; enabling it for Indian flows needs counsel.
- **DoD:** checkout → on-confirmation idempotent webhook → `Subscription`/invoice sync via PaymentsPort;
  BTCPay + a stablecoin adapter; signature-verified, replay-safe; no-op-when-unconfigured; the
  compliance caveat surfaced in README + DECISIONS-NEEDED. Mocked chain/webhook in CI.
- **CI:** `crypto_payments` row (billing) — signature verify + idempotent confirmation, mocked.
- *decompose on pull*

---

## Wave 7 — growth & distribution (custom domains, backend SEO)

The acquisition/distribution surface (vs the production pipeline, which is covered). Scope discipline:
the backend owns infrastructure + data + seams; **the frontend/marketing site owns rendering, content,
on-page meta, and Core-Web-Vitals-frontend** (out of scope — separate repo).

### P31 · Custom domains + automated TLS  🟠 (white-label + the SEO enabler)
- **Scope:** `DomainPort` — per-tenant **subdomains** (`*.app.com`) **and customer custom domains**
  (`app.theirbrand.com` via CNAME); a `domains` table (tenant, domain, verified, primary, strategy);
  **Host-header → tenant** resolution feeding the tenant-context middleware + RLS (P4); **DNS TXT/CNAME
  domain verification**; **automated certificate issuance at scale**. Default adapter = **Caddy
  on-demand TLS / CertMagic** (self-host, ACME, ask-endpoint validates ownership before issuing);
  managed seams = **Approximated.app** / **Cloudflare for SaaS**.
- **Toggle/Port:** `include_custom_domains`; `DomainPort`, `domain_strategy` setting (caddy|approximated|cloudflare).
- **Implies/Deps:** tenancy + **P4 RLS** (Host→tenant→RLS); ingress (Caddy/edge). DPDP: self-host
  Caddy in an India DC for residency; managed = cross-border (D2/D17).
- **Security (BUILD-NOW within the phase):** **host-header allowlist** (`TrustedHostMiddleware` against
  verified domains — reject unknown Host), **dangling-DNS / subdomain-takeover** prevention
  (require DNS-record removal before decommission, token rotation, periodic resolver audit, cert
  revocation on takeover) — ties to P6/P29.
- **DoD:** subdomain + custom-domain routing → correct tenant (RLS-scoped); DNS verification flow;
  cert auto-issued/renewed via the default adapter (mocked ACME in CI); unknown Host rejected; per-tenant
  isolation proven. No live ACME in CI.
- **CI:** `custom_domains` row — Host→tenant resolution + allowlist-reject + verification-state tests (mocked DNS/ACME).
- *decompose on pull*

### P32 · Backend SEO surface  🟡
- **Scope (BUILD-NOW in-phase):** dynamic **`sitemap.xml`** (sitemap-index for >50k URLs, lastmod,
  **per-tenant / per-domain** sitemaps, cached/regenerated) + **`robots.txt`** (per-tenant/per-env);
  **canonical-URL + trailing-slash** normalization middleware; **301 redirect** manager (`RedirectPort`
  + table, audited). **SEAM-NOW:** a **`SeoMetadataPort`** serving **JSON-LD (schema.org)** + Open
  Graph + **hreflang/i18n** metadata for an SSR/SSG frontend to embed; pSEO **thin/duplicate-content
  audit** (reporting, not a gate). **OUT-OF-SCOPE:** prerendering / dynamic-rendering for crawlers —
  Google deprecated dynamic rendering (2025) and AI crawlers don't run JS, so the *frontend SSR/SSG*
  owns rendering; the backend just serves the data + structured-data *source*.
- **Toggle/Port:** `include_seo` (sitemap/robots/canonical/redirects); `SeoMetadataPort` (structured
  data, seam); `seo_trailing_slash_mode` setting.
- **Implies/Deps:** db; **pairs with P31** (per-custom-domain sitemaps + canonical). TTFB/Core-Web-Vitals
  backend contribution already covered (caching P20 + observability).
- **DoD:** valid sitemap-index + per-tenant sitemap; robots.txt per env; canonical/trailing-slash
  enforced (301); redirect manager round-trips; JSON-LD endpoint returns valid schema.org; prerendering
  documented as frontend-owned. Validated with golden-file sitemap/robots + schema validation.
- **CI:** `seo` row — sitemap/robots well-formedness + canonical-redirect + JSON-LD schema-valid tests.
- *decompose on pull*

---

## Wave 8 — platform completeness (the final no-gaps sweep)

The remaining genuine platform subsystems found by an adversarial audit ([COMPLETENESS-AUDIT.md](COMPLETENESS-AUDIT.md)).

### P33 · Tax & invoicing compliance  🔴 (India e-invoicing is a legal requirement)
- **Scope:** a **`TaxPort`** behind the billing layer (calculate tax for a sale; validate tax-ids;
  generate compliant invoice). Default = **self-calc** (India **GST 18%**, SAC-998361, place-of-supply
  B2B/B2C, **GSTIN validation**, sequential numbering, retention) + a **GSTN IRP e-invoicing/IRN**
  adapter (**mandatory at AATO ≥₹5Cr**, 30-day rule); compliant **invoice PDF** (WeasyPrint). Managed
  seams: **Stripe Tax / Anrok / Avalara**; global **VAT (OSS/VIES)** + **US nexus**.
- **Toggle/Port:** `include_tax` (implies billing); `TaxPort`, `tax_engine` setting; `InvoiceGenerator`.
- **Implies/Deps:** billing/payments. India e-invoicing flagged in **D18**.
- **DoD:** correct GST per place-of-supply; GSTIN validation; sequential gap-free invoice numbers;
  compliant PDF; IRN adapter stubbed/mocked; VAT/nexus via the managed seam. Golden-invoice + tax-calc tests.
- **CI:** `tax` row (billing) — GST calc + GSTIN-validate + invoice-numbering (mocked IRP).
- *decompose on pull*

### P34 · Analytics & reporting  🟠
- **Scope:** `AnalyticsPort` (per-tenant metrics/time-series — **Postgres-native continuous aggregates /
  TimescaleDB**, RLS-isolated) + `ReportPort` (**WeasyPrint** PDF, **Polars** Excel/CSV, **streaming
  exports**, **scheduled reports** via arq). Event rollup tables. Seams: DuckDB embedded dashboards,
  Metabase/Cube embedded, ClickHouse (>1M events/day).
- **Toggle/Port:** `include_analytics`, `include_reports`; `AnalyticsPort`, `ReportPort`.
- **Implies/Deps:** db (+ cache); jobs (scheduled reports). DPDP: data-classification on event schema.
- **DoD:** time-series query + dimensional breakdown (RLS-scoped); streaming CSV/XLSX export (memory-safe);
  scheduled PDF via worker; mocked data in CI.
- **CI:** `analytics` row — aggregate query + streaming export + PDF render.
- *decompose on pull*

### P35 · Public API / developer platform  🟠
- **Overlay merged (was W9):** contract-quality gates land FIRST and gate everything derived — per-module OpenAPI fragments, operation-level completeness (Spectral), breaking-change gate (oasdiff), RFC 9457 Problem Details, then Scalar/SDKs/MCP/changelog as *derived artifacts*. Key hardening (test/live prefixes, rotation, lifecycle→audit, per-key quotas) rides here.
- **Scope:** be an **OAuth 2.1 / OIDC provider** (Authlib + `oauth_clients`/consent tables;
  `/oauth/authorize|token|revoke`) so third-party apps act on behalf of users (the *provider* side of
  `AuthnPort`); a generalized **inbound-webhook receiver** (HMAC verify → outbox P5) + **app registry /
  marketplace** seam; **SDK generation in CI** (OpenAPI Generator default; Speakeasy seam); a
  self-host **Scalar** developer portal; `ConnectorPort` for native connectors.
- **Toggle/Port:** `include_oauth_provider`, `include_inbound_webhooks`, `include_sdk_generation`,
  `developer_portal` setting.
- **Implies/Deps:** users (OAuth); db (app registry); P17/P8/P7 (versioning/quota/metering); P1/P5 (webhooks).
- **DoD:** authorization-code+PKCE flow (mock client); token issue/revoke; inbound webhook HMAC-verify→outbox;
  app registry CRUD + revoke; SDK generated in CI; Scalar docs served. No live third-party in CI.
- **CI:** `dev_platform` row — OAuth flow + inbound-webhook verify + SDK-gen smoke.
- *decompose on pull*

### P36 · i18n / l10n / multi-currency / timezones  🟠
- **Scope:** `LocalizationPort` — backend string i18n (**Babel/gettext**, ICU plurals), locale
  resolution middleware (Accept-Language → user → org → default), **JSONB-per-locale** translatable
  content; **multi-currency** money type (**py-moneyed + Decimal**, never float), per-region pricing,
  FX-rate source (Frankfurter/ECB); **timezones** (UTC storage + `zoneinfo` per-user). Translation-mgmt
  seam = **Weblate** self-host. Out-of-scope: RTL/number-date display (frontend).
- **Toggle/Port:** `include_localization`; `LocalizationPort`, money type, locale middleware.
- **Implies/Deps:** none core (db for content/prefs). Ties to billing/tax (currency) + SEO (hreflang P32).
- **DoD:** locale resolves + fallback chain; translated email/error strings; JSONB content served per
  locale; money math currency-safe; UTC stored + tz-converted on read. Babel extract/compile in CI.
- **CI:** `localization` row — locale-resolution + money-currency-safety + tz-conversion tests.
- *decompose on pull*

### P37 · File / media processing  🟠 (malware scan = security gate)
- **Scope:** `MediaProcessingPort` on top of object storage — **presigned direct-to-S3 upload** +
  **magic-byte/content-type validation** + size limits; **malware/virus scanning** (**ClamAV**
  self-host default; VirusTotal seam) with **quarantine + audit** (a real security gate); **image
  processing** (**pyvips** in-process / **imgproxy** sidecar — resize/convert/optimize); **document
  OCR** (**Docling**/Tesseract → ties to RAG P23). Video transcoding = out-of-scope (managed seam).
- **Toggle/Port:** `include_media_processing` (implies storage); `MediaProcessingPort` + scan/image/doc adapters.
- **Implies/Deps:** storage; jobs (post-upload worker). Malware scan ties to P29 (untrusted input) + audit.
- **DoD:** presign + magic-byte reject of spoofed types; ClamAV scan → quarantine + audit on infected
  (mock clamd in CI); pyvips resize/convert; OCR extract (mock). No live AV/network in CI.
- **CI:** `media` row (storage) — validation-reject + scan-quarantine + resize (mocked).
- *decompose on pull*

### P38 · Tenant lifecycle & onboarding automation  🟠
- **Scope:** a tenant **state machine** (`PENDING_PAYMENT → ACTIVE → TRIAL → SUSPENDED → OFFBOARDED →
  DELETED`) + provisioning (create org → seed defaults → first-admin invite), **trial** management +
  expiry (arq scheduler), **plan up/downgrade + proration** (via PaymentsPort/Stripe), **suspension/
  reactivation** (status middleware, data preserved), and **DPDP offboarding** (export-window → purge,
  cascade delete + S3 cleanup, **1-yr audit-log retention**) — composes P16 (data-rights) + audit.
- **Toggle/Port:** `include_tenant_lifecycle` (implies tenancy + billing); lifecycle service + state enum.
- **Implies/Deps:** tenancy; billing (trial/plan/proration); **P16** (export/erasure); audit.
- **DoD:** state transitions audited; trial-expiry job; up/downgrade proration via the payments port;
  suspend blocks writes/allows reads; offboard exports-then-purges with retained audit trail. Mocked clock/Stripe.
- **CI:** `tenant_lifecycle` row — state-machine transitions + suspend-blocks-writes + offboard-purge tests.
- *decompose on pull*

---

## Wave 9 — monetization intelligence (revenue model + AI pricing) — see [MONETIZATION.md](MONETIZATION.md)

### P39 · Revenue-model & packaging engine  🟠 ⭐
- **Scope:** packaging as **versioned DATA, not code** behind a **`PricingPort` + `PackagingPort`** — a
  Postgres `PricingCatalog` (products·plans·features·prices·streams) that resolves the effective
  **entitlement + price** for a `(tenant, plan, usage)` tuple and composes every active **revenue stream**
  (subscription · per-seat · usage/overage · prepaid credits/burn-down · one-time/add-on · API-product ·
  marketplace rev-share) into one P7 invoice. Effective-dated prices, plan up/downgrade **proration**,
  published catalog **versions** (audited + reversible). Managed adapters (Stripe Billing/Lago/Metronome/Orb)
  behind the same port. Extends `billing`/P7.
- **Toggle/Port:** `include_pricing` (implies billing + metering); `PricingPort`, `PackagingPort`,
  `pricing_provider`.
- **Implies/Deps:** **P7 metering** (rate→invoice), **P8 entitlements/quotas**, billing.
- **DoD:** a plan/price/packaging change is **data-only** (no deploy); `resolve(...)` deterministic + pure;
  proration correct; ≥2 streams compose into one P7 invoice; every catalog change versioned, audited (P10),
  reversible. Works on sqlite/no-infra with the default adapter.
- **CI:** `pricing` (ALONE: pricing+metering+billing) + `pricing_full` (+API-product +add-ons +proration);
  alembic round-trip.
- *decompose on pull*

### P40 · AI pricing intelligence (revenue optimization)  🟠 ⭐
- **Scope:** a **`PricingIntelligencePort`** that reads metering (P7) + analytics (P34: MRR/ARR/churn/
  expansion/cohorts) + the catalog (P39) and emits **pricing/packaging recommendations** — plan
  recommendation/right-sizing, expansion/upsell timing, dynamic/personalized pricing (guardrailed),
  churn-risk discounting, price-elasticity + usage-forecast, packaging **simulation**, and **price
  experimentation** (A/B via P18, measured by P34). The decision model is a **pluggable adapter**: default
  **`rules+forecast`** (deterministic, no LLM); **`llm`** adapter over the **P21 gateway** (token-metered,
  structured-output) that degrades to rules when unconfigured. **Human-in-the-loop approval** applies via
  P39; revenue **guardrails** (floors/ceilings/max-discount/fairness, ties P26) enforced before surfacing.
- **Toggle/Port:** `include_pricing_ai` (implies pricing P39 + analytics P34); `PricingIntelligencePort`,
  `pricing_ai_provider` (default `rules`; `llm` via P21).
- **Implies/Deps:** **P39**, **P7**, **P34**, **P18** (experiments), **P21** (AI adapter, optional), **P26**
  (price-fairness guardrails), **P10** (audit).
- **DoD:** a recommendation carries rationale + confidence + guardrail-checked bounds; **nothing
  auto-applies** (human gate); an A/B price experiment launches (P18) + lift measured (P34); the `llm`
  adapter degrades to `rules`; every applied change audited + reversible; guardrail violations rejected.
  Fake-LLM on sqlite/no-infra.
- **CI:** `pricing_ai` row (ALONE: pricing_ai+pricing+analytics, fake LLM) — recommend→approve→apply→audit +
  a guardrail-rejection + an llm→rules degradation test.
- **Human gate (D20 ⚠️):** enabling **dynamic/personalized pricing** is a legal/fairness/regional call —
  default **off** (rules baseline + human approval only) until the founder explicitly enables it.
- *decompose on pull*

---

---

## Wave 10 — platform surface & operability (merged overlay; all `decompose on pull`)

### P41 · Clean-room evaluator  🟡  (was W6)
- **Outcome:** `build-judge` grades by RUNNING the generated service against a contract negotiated
  before the build, never by reading diffs, and never sees builder transcripts.
- **Outer lines:** no template body change; `.claude/` + [BUILD-SYSTEM.md](BUILD-SYSTEM.md) only.
- **Blocked-by:** none. **Blocks:** none. *decompose on pull*

### P42 · Generated IaC  🟠  (was W7)
- **Outcome:** Terraform generated for [INFRA-TOPOLOGY.md](INFRA-TOPOLOGY.md) **Stage 2** (default);
  Stage 3 and a sovereign/air-gapped variant behind flags. Stage 1 stays compose-level.
- **Outer lines:** region and residency are variables, never branches.
- **Blocked-by:** none. **Blocks:** P45's air-gap install path. *decompose on pull*

### P43 · Control-plane API  🟠  (was W10)
- **Outcome:** a distinct **versioned management surface**, separate from the product API, under the
  same contract gates: tenants/orgs lifecycle · users/roles/permissions · key administration ·
  quotas/entitlements · feature flags · webhook config · audit query · metering reads · billing
  state · service config.
- **Outer lines:** **everything the admin UI can do goes through this API — no UI-only privileged
  paths** (a UI-only path has no contract, no scope, no SDK and is invisible to the route-coverage
  gate). Fine-grained scopes per resource+verb; **never a blanket `admin` scope**. A future MCP
  management server is a *consumer* of this surface, not a second implementation.
- **Blocked-by:** **P35** (its contract gates). **Blocks:** none. *decompose on pull*

### P44 · Docs platform  🟠  (was W11)
- **Outcome:** the **generated service's** product docs — Diátaxis-separated, tutorials per persona
  (service developer / platform operator / API consumer). Reference is **generated** from the
  OpenAPI contracts, capability manifests and settings schema; **authored reference for these is
  forbidden** (a copy of a fact drifts the moment the fact changes).
- **Outer lines:** static self-hostable output; docs build in CI with broken links and orphaned
  pages failing the build. Tool: **Starlight** recommended on the [P8](PRINCIPLES.md) self-hostable
  rule (SSG + Pagefind = search with zero running infra); ⚠ versioned-docs-per-release is native to
  neither candidate — re-verify before committing. This repo's own `docs/` set stays markdown-in-repo.
- **Blocked-by:** **P35** (generated reference needs gated contracts). **Blocks:** none. *decompose on pull*

### P45 · Enterprise lifecycle  🟠  (was W12)
- **Outcome:** day-0 install (air-gap path; boot-time config validation naming **every** missing
  setting in one pass; `SecretsPort` per **P14**), day-1 operation (HA statelessness proven by a
  two-replica CI leg; graceful shutdown + readiness gates; sanitized support-bundle export reusing
  the F5 redaction key set), day-2 upgrade (stable/edge channels; `MIGRATION.md` mandatory on majors,
  enforced by the release workflow; written deprecation timelines; SBOM **+ license report** as
  release artifacts — the SBOM half already ships via P2c).
- **Outer lines:** the **zero-downtime migration guarantee is blocked on the destructive-migration
  gate (finding F8, open)** — asserting it before that gate exists would be prose-as-enforcement,
  which [SECURITY-BASELINE.md](SECURITY-BASELINE.md) §0 rejects.
- **Blocked-by:** **F8**, **P42** (air-gap path), **P14**. **Blocks:** none. *decompose on pull*

---

## Deliberately deferred (seams exist; do NOT build until a real trigger)

Listed so "not building these" is a *recorded decision*, not an omission ([PRINCIPLES.md#P9](PRINCIPLES.md)):

| Item | Seam already planned | Build trigger |
|---|---|---|
| Cerbos/OpenFGA **live** authz engine | `AuthorizationPort` (P10) | a customer needs ABAC/ReBAC |
| Temporal **cluster** | `WorkflowPort` (P11) | throughput/tenant-isolation beyond DBOS |
| Per-tenant **DB silos** (live) | `DatasourcePort` (P12) | a high-ARR tenant demands isolation |
| **Authentik/WorkOS** live SSO | `AuthnPort` (P13) | first enterprise SSO deal |
| **Vault/Infisical** live | `SecretsPort` (P14) | audit/rotation requirement |
| **Svix** webhook infra | `WebhookPort` seam | replay-UI/rotation worth $490/mo |
| **Meilisearch/Qdrant** | `SearchPort` (P19) | >~50M vectors / FTS scale |
| **Caching** subsystem | optional `CachePort` | a measured hot path |
| **Debezium/Kafka** CDC | outbox relay (P5) | >~1M events/day |
| Managed metering (Lago/Orb) | `MeteringPort` (P7) | volume justifies 2-4% revenue share |
| **LiteLLM proxy / Portkey** gateway | `LLMPort` (P21) | >100 tenants need central governance |
| Dedicated **vector DB** (Qdrant/Weaviate) | `RetrievalPort` (P23) | >~50M vectors / filter-heavy |
| Managed **memory** (Mem0/Zep) | `MemoryPort` (P24) | entity-extraction/temporal reasoning is a revenue lever |
| Self-host **Langfuse** cluster | OTLP GenAI seam (P25) | data-residency mandate / team scale |
| **LangGraph/OpenAI-Agents** as default | `AgentPort` (P22) | a branching/HITL or GPT-committed product |
| Managed real-time (Ably/Pusher) · Centrifugo | `RealtimePort` (P27) | scale/ops beyond FastAPI-WS+Redis |
| Offline-first **sync engine** (PowerSync/ElectricSQL) | `SyncPort` (P28) | a mobile service needs offline |
| Tool **sandbox** infra (Modal/gVisor/E2B) | MCPToolPort (P26/P29) | agents execute untrusted code |
| Custodial crypto (Coinbase/BitPay) · INR off-ramp | `PaymentsPort` crypto (P30) | a deliberate compliance decision (D14) |
| Managed custom-domains (Cloudflare-for-SaaS/Approximated) | `DomainPort` (P31) | scale/ops beyond self-host Caddy, or DDoS need |
| **Frontend SEO**: rendering, meta-injection, content, Core-Web-Vitals-frontend, prerendering | frontend repo (SSR/SSG) | **out of scope** — not a backend-template concern |
| pSEO content generation (the pages themselves) | `SeoMetadataPort` data (P32) | a content/product decision |
| Managed tax (Stripe Tax/Anrok/Avalara) | `TaxPort` (P33) | global VAT/nexus complexity or scale |
| ClickHouse / Cube / Metabase analytics | `AnalyticsPort` (P34) | >1M events/day or formal BI contract |
| Speakeasy SDKs · ReadMe portal · Svix · Authentik | P35 seams | SDK-as-product / enterprise SSO / replay-UI need |
| Weblate translation server · managed FX | `LocalizationPort` (P36) | translators join / high FX volume |
| imgproxy sidecar · Docling OCR · video transcoding | `MediaProcessingPort` (P37) | resize >1M/day · RAG docs · video (managed) |
| SCIM provisioning | tenant-lifecycle (P38) + P13 | enterprise directory-sync deal |

---

## Dependency graph (ship order)

```
P1 SSRF ─┐
P2 CI ───┤ (independent quick wins)
P3 Auth ─┤
P4 RLS ──┘
            P5 Outbox ──┐
            P6 Idem ────┴──► P7 METERING ⭐
P8 RateLimit · P9 Notify · P10 Authz · P11 Workflows · P12 Datasource ·
P13 SSO/MFA · P14 Secrets · P15 PIIEnc ──► P16 DataRights · P17 APIv ·
P18 Flags · P19 Search · P20 Cost/Ops      (P16 also needs P5)

Wave 5 (AI):  P21 LLM-gateway+metering ⭐ (needs P7) ─┐
              P22 AgentRuntime+GenAI-tracing (needs P11 for durable)
              P23 RAG ─► P24 Memory (also needs P11)
              P25 Evals+tracing · P26 Guardrails+prompts+MCP (needs P1/P15/P18)
Wave 6:       P27 Real-time (needs P5+cache) · P28 Mobile/BFF (needs users+P9)
              P29 Agent-safety ⭐ (needs P10/P26/P1/P21 — GATES production agents)
              P30 Crypto payments (needs billing; ⚠ D14 compliance gate)
Wave 7:       P31 Custom domains+auto-TLS (needs tenancy+P4) ─► P32 Backend SEO (per-domain sitemaps)
Wave 8:       P33 Tax+invoicing ⚖ (needs billing; ⚠ D18 India e-invoicing) · P34 Analytics+reporting
              P35 Public-API/dev-platform (OAuth provider; needs users) · P36 i18n/l10n/currency/tz
              P37 Media processing (malware scan; needs storage) · P38 Tenant lifecycle (needs tenancy+billing+P16)
Wave 9:       P39 Revenue-model+packaging ⭐ (needs P7+P8) ─► P40 AI pricing intelligence ⭐ (needs P39+P34+P21; ⚠ D20)
```

Waves 0-1 are parallel-safe; Wave 2 gates Wave 3; Wave 4 is value-ordered and largely independent
(only P16 has an intra-wave dep on P15+P5). **Wave 5 (AI)** rides the platform: P21 needs P7
metering, P22's durable path needs P11, P24 builds on P23, and P26 reuses P1/P15/P18 — but each is
still one shippable `feat:` PR once its deps land. Each phase is its own `feat:` PR + version bump;
arm squash auto-merge per the standing rules.

---

## STEP 5 — skeptic self-review (what I checked)

- **Any SaaS stage missing?** Re-ran a full-platform checklist against the phases. Four small gaps
  found and folded in (ingress security headers + CORS → P2; auth abuse protection → P8; admin-action
  audit → P10 note; backup/DR + retention → P20), plus an org-invitations completeness check (P9).
  Nothing else material uncovered: signup/verify/reset (shipped), multi-currency (Razorpay/INR via the
  payments port), i18n of notifications (a future `NotificationPort` adapter concern, deferred), and
  status-page/incident-comms (ops, out of template scope). **The AI-native application layer**
  (LLM gateway + token metering, RAG, agent memory, evals/tracing, guardrails/MCP-safety) was the
  one substantial omission of the first spec pass — now covered as **Wave 5 (P21-P26)** with its own
  research doc [AI-AGENTIC-STACK.md](AI-AGENTIC-STACK.md).
- **Any STEP-2 requirement uncovered?** All 8 subsystem clusters + all 13 cross-cutting items map to a
  phase or a FINE-AS-IS verdict (cross-checked against [GAP-ANALYSIS.md](GAP-ANALYSIS.md)).
- **Any phase not independently validatable?** Each has a concrete CI row or render-gate/test, and the
  inherited P3 matrix. Dependency-ordered phases (P7 after P5+P6; P16 after P15+P5) are *sequenced*,
  not co-dependent — each still ships as one PR once its deps have landed.
- **Any choice not cost-justified?** Every ADR in [LIBRARY-DECISIONS.md](LIBRARY-DECISIONS.md) carries
  small+large cost, license, and lock-in; defaults are the cheapest credible self-hostable option, with
  the managed swap recorded. The genuinely consequential calls are escalated to
  [DECISIONS-NEEDED.md](DECISIONS-NEEDED.md) rather than guessed.

Verdict: spec is internally consistent, fully covers the brief, and is buildable phase-by-phase on the
existing gate. **No building begins until the founder reviews this set** (esp. D1-D3).
