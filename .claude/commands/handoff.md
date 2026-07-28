---
description: Verify the ticket is finished, select the next one, emit a paste-ready NEXT SESSION block.
argument-hint: [ACTIVE-TICKET-ID]
allowed-tools: Bash(git:*), Bash(grep:*), Bash(sed:*), Bash(gh pr:*), Read, Glob, Grep
model: claude-sonnet-4-6
---
Example: `/handoff GC-1` — refuses if GC-1 is unfinished, else emits the block for the next ticket.

End the session that just finished a ticket. Argument: $ARGUMENTS ($1 = the ticket ID just worked).
If $1 is empty, derive it from the current branch name and say what you derived; if that yields
nothing, stop and ask for the ID rather than guessing.

**Assemble every field by quoting the ledger. Never write a field the ticket does not contain** —
this command exists because a hand-written opening prompt is where an invented File set enters, and
an invented File set binds the next session's staging guard to the wrong slice, where it passes.

## 1. VERIFY — refuse to hand off an unfinished ticket

Run these and let their output decide. Do not substitute judgement for the exit codes.

```bash
ID="<the id>"
git status --porcelain                                  # uncommitted work
grep -n "^### ${ID} ·" docs/ROADMAP.md                  # ticket still filed as OPEN?
grep -n "${ID}" docs/ROADMAP.md | grep -v "^[0-9]*:### " # breadcrumb lines, if any
```

- **Ledger status is updated** ⇔ the second grep finds **nothing**. Landed work *exits* the ledger
  (ROADMAP's own convention), so a surviving `### <ID> ·` heading means the status was never updated.
- **Breadcrumbs are written** ⇔ the third grep finds **at least one** line. Both exit styles count:
  a dedicated `*`<ID>` exits …*` note and a batch note naming the ID. **Print the matched lines** —
  this check proves a breadcrumb is *present*, not that it is *good*, and printing it is what makes
  that judgeable by the person reading the handoff.

**If either fails, STOP.** Emit no NEXT SESSION block — not a partial one, not a draft. Print exactly
what remains, one line per gap, in the form:

```
HANDOFF REFUSED — <ID> is not finished.
  [ ] ledger status not updated — docs/ROADMAP.md:<line> still carries "### <ID> ·"
  [ ] breadcrumbs not written — no line in docs/ROADMAP.md mentions <ID> outside its heading
Finish these, then re-run /handoff.
```

List only the gaps that actually failed. If `git status --porcelain` was non-empty, print a
`WARNING: <n> uncommitted file(s) — closing this window loses them:` line with the paths above the
verdict. It does **not** by itself refuse the handoff (a ticket may legitimately end with its PR
open), but it is the one thing a window-close destroys, so it is never silent.

## 2. SELECT — the next ticket, from the ledger only

Read `docs/ROADMAP.md`'s `## NEXT UP — decomposed` section. Candidates are its `### ` ticket
headings, in file order. Pick the **first** whose **Blocked-by** field is satisfied — `none`, or a
ticket that has already exited. Skip and name any candidate you pass over, with the blocker.

If NEXT UP contains no ticket headings, output exactly this and stop:

```
Queue empty — next move is a decompose-on-pull planning session; consult the architect conversation before pulling a capability phase.
```

## 3. EMIT — the NEXT SESSION block

Resolve the JIT reads by reading the **Reading contract** table in `AGENTS.md` and choosing the rows
whose "Doing this" clause the selected ticket matches; name the row you matched. Do not use a list
embedded here — a second copy of that table would drift from the one sessions actually follow.

Then print, verbatim in shape:

```
CLOSE THIS WINDOW. Open a new terminal, run plain `claude` (never --continue or --resume), paste everything below.

Pull <ID> from NEXT UP. First act: set .claude/slice-scope from the ticket's File set (<paths>). Read the always-read set + this ticket + JIT: <matched docs>. Failing-test-first entry: <ticket's entry field>. Done: <ticket's done-contract sketch>. Report per ticket; show the failing run before any fix.
```

Every `<…>` is quoted from the selected ticket. **Where the ticket has no such field, write
`MISSING: <field name>` in its place** and add a line under the block naming what the ticket is
missing — a ticket short a mandatory field is a filing defect worth seeing, and inventing the field
hides it.
