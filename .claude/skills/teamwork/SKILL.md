---
name: teamwork
description: Run work in this repo under its manager/worker operating model — establish a green baseline, take one plan item at a time, delegate mechanical edits and recon to cold low-effort workers, verify every worker diff, run the full gate, and commit. Use when starting plan-based work, when delegating to subagents, when a worker escalates a blocker, or when the user asks to work as a team / manager / coordinator.
argument-hint: [plan item or task to run through the loop]
user-invocable: true
version: 0.2.0
---

# Teamwork — manager/worker delivery loop

This skill is the **procedure**. It deliberately contains no test counts, no
allowlist line numbers, and no gate composition — those live in `AGENTS.md` and
the role contracts, and duplicating them here would create one more copy to rot.
Read the facts from source, every session.

Invoking this skill **authorizes subagent use** for the delegation described
below, and only for that.

---

## 0. Decide your role first

| You are | if | Read |
|:---|:---|:---|
| **Manager** | you are the top-level session, or the user addressed you directly | `AGENTS.md` + `agents/opus-manager.json` |
| **Worker** | you were spawned with a brief | `agents/sonnet-worker.json` — then do exactly the brief |

If you are a worker, stop reading this file after this line and follow your
contract. The rest is the manager's job.

---

## 1. Load the contracts, then a green baseline

```bash
poetry install
. .venv/bin/activate
timeout 1200 make gate
```

Read `AGENTS.md` (shared briefing) and `agents/opus-manager.json` (your
contract) if they are not already in context. Do not re-read what is already
loaded — that is pure cache cost.

**A green baseline before you touch anything is what makes a later red gate
mean something.** If the gate is red on arrival, that is the first thing you
fix, and it is not part of the plan item.

Confirm the test count matches the number stated in `AGENTS.md` §7. A different
count means miscollection — investigate before trusting any run, green or not.

---

## 2. Plan first, then write the ledger

**Plan before you act, even when you cannot see the end.** A plan here is not a
prediction and does not have to be complete or correct. Its real job is to
*manufacture milestones* — the points where work becomes durable and context can
be dropped. No plan means no milestones, and context then grows untended to the
end of the session.

Write the next item or two concretely and the rest as placeholders, then refine
as you go. A far item that turns out wrong costs nothing, because it was never
load-bearing. Waiting until the whole shape is clear before planning is the
expensive move, not the careful one.

**Your context is not durable storage. The ledger is.** A plan you are holding
in your head is erased by the next compaction, and you will not notice it went:
you will simply continue with a narrower goal than the user asked for.

Before the first edit, write `READ_AFTER_COMPACT.md` at the repo root:

```markdown
# READ AFTER COMPACT
GOAL: <the user's ask, in their terms, in full — not your current sub-task>
BRANCH: <branch> · BASELINE: <gate green? test count?>

## Items
- [x] <done item> — commit <sha>
- [ ] <in-flight item> — worker <label>, files: <paths>
- [ ] <not started>

## Decisions (do not relitigate)
- <architectural call> — <one-line reason>

## Deliberately excluded
- <thing> — <why it is out of scope>

## Next action
<the single next thing to do>
```

Rules that make it worth the tokens:

- Update it at every loop step boundary — not at the end. A ledger written once
  is a ledger that is already wrong.
- It is the **first** thing you read after a compaction, before any source file.
- It is gitignored session state, not a deliverable. Delete it when the work
  lands.
- The GOAL line is the guard against the most expensive failure mode in this
  workflow: silently finishing a smaller task than the one you were given.

## 2b. The delivery loop

Execute exactly this, one item at a time:

1. **Pick one unchecked plan item** from `plans/` — single scope. Record it in
   the ledger as in-flight.
2. **Implement only that scope** — directly, or via workers (§3).
3. **Run targeted tests** for the touched files.
4. **Run the full gate** — `timeout 1200 make gate`.
5. **Commit immediately**, message referencing the plan item.
6. **Mark the checkbox `[x]`** — in the plan and in the ledger — only after the
   commit exists.
7. **Update the ledger, then compact.** The committed item is a milestone: its
   file bodies, diffs, worker reports and logs are now dead weight you re-read
   on every remaining turn. Move what survives into the ledger — that comes
   first, always, because compaction is lossy whoever fires it. Then compact:
   in a tmux session, issue `/compact` yourself (§6b); outside one, say plainly
   that now is a cheap moment for the user to run it.
8. Repeat.

Hard stops, no exceptions:

- Gate red → back to implementation. **No commit.** Never relax, allowlist
  around, or delete a check to reach green.
- Never push to `master`. Feature branches only.
- Do not batch plan items into one commit unless the plan says so.
- "Green but uncommitted" is an unfinished task, not a handoff.

---

## 3. Delegation

**Delegate when** the task is mechanical and fits a self-contained brief; or it
is recon (read N files, return a digest) so raw text never enters your context;
or several independent tasks touch disjoint files and can run in parallel.

**Delegation is the default, not the exception.** Manager tokens are the most
expensive in the system; a measured session put ~80% of its cost on the
manager's cache reads alone. If you are typing prose, editing a doc, or applying
a decision you have already made, that is *execution* — hand it down.

**Do not delegate** a task that needs a design choice not yet made, or two tasks
that would edit the same file.

There is one narrow exception: a task genuinely smaller than the brief it would
need — a one-line fix, a single string replacement. **This exception is a
scalpel, not a shield.** "Rewriting this document needs judgment" is not a
reason to keep it; make the judgment, put it in the brief as a decision, and let
a worker write the prose. Keeping routine work because you can do it well is the
single easiest way to burn a session's budget.

Pick the worker shape deliberately:

| Need | Spawn | Why |
|:---|:---|:---|
| Very mechanical: string swaps, label removal, docstring trims, renames across known files | `general-purpose`, `model: "haiku"` | Cheapest tier; ample when the brief leaves nothing to infer |
| Mechanical edit or prose rewrite from a decided spec | `general-purpose`, `model: "sonnet"` | Cold, low-effort, matches the worker contract |
| Recon / search | `Explore`, `model: "sonnet"` | Read-only; returns conclusions, not file dumps |
| **You are uncertain and about to guess** | `general-purpose`, `model: "opus"` — a **critic** | A fresh Opus with a clean, single-question context judges better than you do at 150k tokens of accumulated bias. Give it the question and the evidence, not your conclusion. Cheaper than committing the wrong call |
| Recon over context you already hold | `subagent_type: "fork"` | Keeps output out of your context — but a fork inherits your context and runs on **your** model, so it is not a cold worker; never use it for work the worker contract governs |

Match the tier to the brief: if the brief specifies exact literals and leaves
nothing to infer, haiku is enough. Reach for sonnet when the worker must read
surrounding code to place a change. Reach for the opus critic only for a
genuine fork in the road — and ask it the question, never "check my work".

### Brief template

Fresh workers inherit nothing. Every brief carries all of it:

```
Read agents/sonnet-worker.json first — it is your session contract.

CONTEXT: <full background; no "as discussed", no references to this conversation>
FILES:   <exact paths you may edit — and only these>
CHANGE:  <exact literal content where precision matters: regexes, TOML, Makefile tabs>
CHECK:   <the single acceptance command to run, and what output means pass>

Stop and report — do not fix anything beyond the change above.
If the brief and the files disagree, escalate; do not guess.
Report: verdict (DONE / BLOCKED / PARTIAL) plus at most 5 bullets.
Write full detail (logs, diffs) to a file and return the path — do not paste it.
Let every command exit before replying; never report a pending state.
```

The first line is load-bearing. A cold worker only ever sees its contract if
the brief tells it to read the file.

### Verify — a report states intent, not outcome

Re-check every worker's work before trusting or committing it:

- `git diff --stat` for shape,
- a targeted `grep` for the exact changed token,
- the acceptance check for the touched files.

Never pull a full diff into your context to verify. Read the worker's detail
file only when something failed.

---

## 4. Escalations are yours

A worker that stops and asks is cheap. A worker that silently resolves a
blocker is the most expensive thing in this workflow — a blocker is an
architectural decision wearing a bug's clothing, and settling it inside a
low-effort context hides that decision where nobody reviews it.

On receipt:

1. Decide the architectural question yourself.
2. Record it in the plan, or in `agents/todo-n-fixme.md` if it outlives the session.
3. Re-brief the worker with the decision made explicit, or take the task back.

---

## 5. Protect the invariants

Before you accept any diff, check it against the invariants listed in
`AGENTS.md` §4 and `agents/*.json` — isolation rules, the reflection ban, the
`JsonTab` import rule, `data_store` leaks. Read them from those files; they
change, and a remembered copy is a stale copy.

Pay particular attention to the **file:line allowlist trap** documented in
`AGENTS.md` §4: if an edit shifts the allowlisted lines, the allowlist must be
fixed in the same commit, or the gate either breaks or silently exempts the
wrong import.

---

## 6. Context economics

Manager cost is dominated by cache reads ≈ context size × turns, not by output.
See `AGENTS.md` §8 for the measured numbers. Both factors compound: a large
context is re-read on *every* subsequent turn, so context you fail to drop is
paid for again and again until the session ends.

**No tool measures or clears your context.** `/context` and `/compact` are not
on the tool surface — verified against the full deferred-tool list, not assumed
— and an automatic compaction fires when the window fills without warning you
first. So a milestone's job is unchanged: make it **survivable**, so that
whichever compaction arrives costs you nothing.

- **Update the ledger at every milestone.** It is the only thing that crosses a
  compaction intact. This is the whole reason it exists.
- **Keep what you never need out of context in the first place.** This is the
  lever you genuinely control: a recon worker's raw output never enters your
  context, only its digest does. Prefer a worker over reading files yourself.

What *has* changed is who fires the compaction — see §6b.

**Never claim a compaction you did not actually queue.** Outside tmux you cannot
cause one at all; inside it, a `send-keys` you did not issue did not happen. An
instruction to do something impossible does not fail loudly — it is silently
skipped, which is worse than a broken reference.

---

## 6b. Self-drive: your own `/commands` in a tmux session

When the TUI runs inside tmux, a Bash call can type into the pane running you,
so `/compact` and `/context` become yours to issue. **Check, do not assume:**

```bash
[ -n "$TMUX" ] && echo "self-drive: yes ($TMUX_PANE)" || echo "self-drive: no"
```

Queue a command — literal text first, `Enter` as its own call — then **end the
turn**, because queued input only submits once the current turn finishes.

**A slash command's output does not re-invoke you** — it is buffered and control
returns to the human, so a bare self-issued `/compact` parks the session at the
worst possible moment. **And you cannot queue the prompt behind it:** plain text
is injected into the *running* turn while the slash command waits for turn end,
so the prompt would arrive first. Detach a typist instead:

```bash
S="${TMUX%%,*}"; P="$TMUX_PANE"
setsid bash -c "sleep 45; \
  tmux -u -S '$S' send-keys -t '$P' -l 'Continue: read READ_AFTER_COMPACT.md and resume from its Next action.'; \
  tmux -u -S '$S' send-keys -t '$P' Enter" </dev/null >/dev/null 2>&1 &
disown
tmux -u -S "$S" send-keys -t "$P" -l '/compact'
tmux -u -S "$S" send-keys -t "$P" Enter
```

Fire the typist last and end the turn immediately — the delay is wall-clock from
send time. Err long (~10s after `/context`, 40s+ after `/compact`). Write the
prompt self-contained: after a compaction it and the ledger are all you have.

Read your own screen with `capture-pane -p -J -S -200` (scrollback without
moving the view) when you need something the transcript never shows; a local
slash command's own output comes back to you as `<local-command-stdout>` and
needs no capture.

The non-negotiables, in full in `agents/tmux-self-drive.md`:

- **Ledger first, `/compact` second.** Reversing them destroys the state the
  ledger exists to carry, and you will not notice it went.
- **Never answer your own prompts** — no `y` / `Enter` / `Escape` into a pending
  permission or confirmation dialog. That is granting yourself the permission a
  human was asked for.
- **Never send a kill** (`C-c`, `C-d`, `/exit`, `kill-server`) — that pane is
  the process you are running in.
- **One slash command per turn, plus one detached typist**, targeted at
  `$TMUX_PANE`, and say in your closing message what you queued.
- **Do not build a send/capture polling loop.** Each iteration is a
  full-context turn that buys nothing.

**This is the real reason to plan first (§2).** The plan is what manufactures
the milestones. Without one there is no natural place to compact, so context
grows to the end of the session — which is precisely how a session ends up
spending most of its budget re-reading its own history.

In order of impact:

1. **Compact aggressively, and early.** This is the highest-leverage lever
   because it is the only one that reduces cost *retroactively* for the whole
   remaining session — every other lever only avoids adding more. Compact at
   each committed item (§2 step 7), after a large recon digest has been acted
   on, and before any long tail of verification turns — yourself when the
   session is self-drivable (§6b), otherwise by telling the user. Do not wait
   to be told the context is full; by then you have already paid for it on
   every turn since it filled. If you are unsure whether something is still
   needed, it is cheaper to drop it and re-read the one file you actually need
   than to carry twenty you might.
2. Delegate **reading**, not just writing — a recon worker's raw text never
   enters your context; only its digest does.
3. Batch shell work — one call doing install + config + verify beats three turns.
4. Cap worker reports; open the detail file only on failure.
5. Verify with `--stat` and targeted `grep`, never full diffs.

**Do not poll.** Waiting on a background command or worker by re-checking it
every turn is the cheapest-looking and most expensive habit here: each poll is a
full-context turn that buys nothing. Harness-tracked work notifies you when it
finishes — do other work, or wait for the notification.

---

## 7. Keep the record honest

After a change lands, update what it invalidated — `agents/repo-map.md`,
`agents/pros-n-cons.md`, `agents/todo-n-fixme.md`, the role contracts, `plans/`.
A stale guide costs more than a missing one.

If you delete a completed plan file, **grep for references first**
(`README.md`, `Makefile`, `.githooks/*`, `agents/*`, docstrings) and retarget
them in the same commit. Dangling plan pointers are a known recurring defect in
this repo.

---

## 8. When you cannot delegate

If subagents are unavailable in this session, the loop does not change — only
step 2 does. Do the work yourself, but keep the manager's discipline: read
narrowly and on demand rather than bulk-loading files, verify with `--stat` and
`grep` as if the diff came from someone else, and shrink scope before you widen
context. Say plainly in your report that the work ran single-agent.
