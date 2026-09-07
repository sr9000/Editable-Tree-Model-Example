# Agent Guide — Editable-Tree-Model-Example

_How agents are expected to work in this repository. High-signal and prescriptive; keep it that way._
**Last updated:** 2026-09-07

---

## 0) Start here — which agent are you?

Work in this repo runs as a **manager/worker split**. Decide your role before doing anything else,
then read your own contract:

| Role | Model / effort | Contract | One-line job |
|:---|:---|:---|:---|
| **Manager / architect** | Opus, high effort | `agents/opus-manager.json` | Decide, decompose, review, gate, commit. |
| **Worker / subagent** | Haiku or Sonnet, low effort | `agents/sonnet-worker.json` | Execute one prescriptive task. Escalate, never improvise. |

The two JSON files are the machine-readable session contracts — scope, allowed commands, escalation
triggers, report format. **This file is the shared briefing; those files are your role's rules.**

The manager's loop is also packaged as an invocable skill at
`.claude/skills/teamwork/SKILL.md` — **tracked in this repo**, so cloning restores it and
Claude Code discovers it with no setup step. Run it with `/teamwork [item]`. Delegation is gated
on the skill's four preconditions, not on the act of invoking it — the skill states them and every
one is checkable. The skill is the *procedure* only: it deliberately carries no test counts,
no allowlist line numbers, and no gate composition, because those live here and in the contracts.
Nothing else under `.claude/` is tracked (`settings.local.json` is machine-local and ignored).

**The single rule that matters most:** _workers do not resolve blockers._ A blocker is an
architectural decision wearing a bug's clothing, and settling it inside a low-effort context hides
that decision where nobody reviews it. A worker that stops and asks is cheap. A worker that silently
"fixes" it is the most expensive thing in this workflow.

---

## 1) First commands (always)

```bash
poetry install
. .venv/bin/activate
timeout 1200 make gate
```

- Poetry-managed; in-project venv at `.venv/`. **Python 3.14 is required.**
- `poetry run <cmd>` works instead of activating.
- A green baseline before you change anything is what makes a later red gate meaningful.

---

## 2) The delivery loop (do not skip steps)

For plan-based work, execute exactly this loop:

1. **Pick one next unchecked plan item** (single scope).
2. **Implement only that scope.**
3. **Run targeted tests** for the touched files.
4. **Run the full gate** — `timeout 1200 make gate`.
5. **Commit immediately** (message references the plan item).
6. **Mark the plan checkbox `[x]`** — only after the commit exists.
7. **Sweep for stale processes.** Run `ps aux` after every milestone and kill shells or agents left
   running by the work just committed — a `pgrep -f` waiter can match its own command line and spin
   forever; see `.claude/skills/teamwork/SKILL.md` §2b for the measured example and the fix.
8. **Update `READ_AFTER_COMPACT.md`.** A committed item is a milestone; its file bodies, diffs
   and worker reports are dead weight you re-read on every later turn. The ledger is what makes a
   compaction cost nothing, so it is written *first*, always.
9. **Check context, then compact — then end the turn.** If the session is running inside tmux you
   issue `/context` and `/compact` yourself (`agents/tmux-self-drive.md`); if it is not, say
   plainly that now is a cheap moment for the user to run it, and stop there. Check which case you
   are in — `[ -n "$TMUX" ]` — instead of assuming either.
10. Repeat — *after* the compaction, never before.

Hard rules:

- **Run the gate alone.** No concurrent builds, no parallel workers doing heavy
  work — a gate run alongside other heavy work proves nothing, green or red.
- Gate red → back to implementation. **No commit.** Never relax a check to get green.
- Do not batch plan items into one commit unless the plan says so.
- Do not stop at "green but uncommitted". That is an unfinished task, not a handoff.
- **Never push to `master`.** Feature branches only.
- **Steps 8 and 9 are unconditional, and step 9 ends the turn.** Not "when context is high" —
  every committed item, at any reading. There is no percentage that excuses skipping the
  boundary, because the threshold *is* the loophole: mid-task you will always judge your current
  context affordable and reason your way past it. A committed item you have not compacted after
  is an item that is not done, and the next item does not begin.

---

## 3) How the split actually runs

**Manager.** Owns architecture, decomposition, sequencing, **all** blocker resolution, review of
every diff, the gate, and the commit. Delegates mechanical edits *and reading* — a recon worker that
returns a digest is far cheaper than five large files landing permanently in the manager's context.

**Delegate by default, and tier the worker.** Manager tokens are the most expensive in the system.
Haiku is enough for very mechanical work whose brief leaves nothing to infer; Sonnet for edits and
prose rewrites from a decided spec; a fresh **Opus critic** — given the question and the evidence,
never your conclusion — when you are uncertain and about to guess. "This needs judgment" is a reason
to make the judgment and put it in the brief, not a reason to keep the typing.

**Worker briefs must be self-contained.** Fresh workers inherit nothing. Every brief carries:

- full context (no "as discussed"), exact file paths, and exact literal content wherever precision
  matters — regexes, TOML, Makefile tabs;
- the one acceptance check to run;
- an explicit **"stop and report, do not fix"**;
- a report cap: _verdict plus at most 5 bullets; write full detail to a file and return the path._

**Trust but verify.** A worker report states intent, not outcome. Re-check with `git diff --stat`
and a targeted `grep` for the exact changed token — never by pulling a full diff into context.

**Do not delegate** a task needing a design choice not yet made, or two tasks that touch the same
file. The "smaller than its brief" exception covers a one-line fix — it is a scalpel, not a shield:
"this needs judgment" means make the judgment, put it in the brief, and let a worker write it.

**Hypothesis verification, diagnosis, and benchmarking are delegable by default** — running an
experiment is execution, not judgement; only choosing the hypothesis and reading the result is. A
worker may drive its own scratch tmux session when its brief says so (`agents/tmux-self-drive.md`);
see `.claude/skills/teamwork/SKILL.md` §3 for the incident that established this.

**Known worker failure mode:** backgrounding a long command and reporting "waiting for X" instead of
the result. Require the command to actually exit before replying.

---

## 4) Guardrails the gate enforces

`make gate` = `lint` → `check-no-reflection` → `test`. The `check-no-reflection` target runs
`.githooks/pre-commit-ci`, which is **five** checks, not one:

1. **No reflection** — `getattr` / `hasattr` / `TYPE_CHECKING` / **`AttributeError`** outside the
   allowlist (`jsontream/__init__.py`, `validation/error_adapter.py`, `app/runtime_compat.py`).
   In `tests/*` they are allowed only with an inline `# allow: <reason>` on the same line.
2. **No `data_store.<retired-attr>` leaks** — `_check_data_store_leaks.sh`.
3. **No concrete `JsonTab` import outside `documents/`** — `_check_jsontab_import_leaks.sh`.
4. **Editors isolation** — `editors/inline/*`, `editors/windowed/*` must not import `app/`,
   `documents/`, `tree/`; `editors/factory.py`, `editors/context.py` must not import `app/`,
   `documents/`.
5. **Tree isolation** — `tree/` must not import `app/`, `documents/`, `editors/`, `delegates/`,
   `state/`, `validation/`. **Lazy imports inside function bodies count too.**

> **Trap:** `_check_tree_isolation.sh` allowlists by **file:line** (`tree/item.py:30`,
> `tree/item.py:31`). Inserting a line above them shifts the numbers — the gate either breaks or,
> worse, silently exempts a different import. If your edit moves those lines, fix the allowlist in
> the same commit.

Run a single check in isolation with `make check-tree-isolation` / `make check-editors-isolation`.

---

## 5) Architecture facts that are easy to miss

1. **The undo edit path bypasses `JsonTreeItem.set_data()`.**
   Real replay path: `DocumentMutationGateway` → undo command → `undo/diff.py:DiffApplier.apply()`.
   Type/value fixes usually need changes in both the item logic *and* `DiffApplier`.

2. **`mpq` whole numbers infer as FLOAT unless converted.** Convert `mpq(n,1)` to `int` where
   integer semantics are required (so it displays `42`, not `42.0`).

3. **The UI runs on a proxy model.** Map indices proxy↔source before touching tree items.

4. **Base64 auto-inference has a persisted minimum-length guard.** String→`BYTES`/`ZLIB`/`GZIP`
   inference only runs at or above `edit_limits/base64_min_length_chars` (default `100`). Short
   valid base64 stays `STRING` unless the type is pinned or the threshold is lowered.

5. **`make lint`'s `autoflake` step is a no-op.** It runs bare `autoflake .`; without `--in-place`
   autoflake only prints diffs. So `make lint` is effectively isort + black — never assume unused
   imports were removed. Enabling it would rewrite imports repo-wide, so it needs its own commit.
   Tracked in `agents/todo-n-fixme.md`.

6. **Lint/test config lives in `pyproject.toml`.** `[tool.black]`, `[tool.isort]`,
   `[tool.pytest.ini_options]`. `pytest.ini` was deleted; re-adding one would silently override
   `pyproject.toml`. isort uses `extend_skip`, not `skip` — `skip` *replaces* isort's built-in skip
   list (`.venv`, `build`, `dist`).

---

## 6) Minimal file map

- Types/coercion — `tree/types.py`, `tree/item_coercion.py`
- Item/model behavior — `tree/item.py`, `tree/model.py`
- Undo replay — `undo/commands.py`, `undo/diff.py`
- Tab composition/lifecycle — `documents/composition/*`, `app/tab_lifecycle.py`, `app/main_window.py`
- Validation — `documents/controllers/validation.py`, `validation/*`

---

## 7) Testing rules

- `QT_QPA_PLATFORM=offscreen` is required for pytest.
- Focused tests while developing, full gate before the commit.
- Every bug fix and plan checkpoint gets a regression test.
- The full suite is **1813 tests**, all passing on Python 3.14. This is the single
  canonical statement of the count — every other file points here rather than
  repeating it. **A different count means something is miscollected — investigate
  before trusting a green run.**

---

## 8) Context economics (measured 2026-09-06)

Manager cost is dominated by **cache reads ≈ context size × turns**, not by output. One migration
session burned 33.2M cache reads against a 239k context over ~140 turns while emitting only 290k
output tokens. Shrinking context and cutting turn count beat delegating more tasks.

Both factors compound: context you fail to drop is re-read, and re-paid for, on every remaining
turn of the session.

**Part of your context is fixed and compaction cannot touch it.** Measured on this repo
(2026-09-07, via `/context`): immediately after a compaction the window still held ~35.8k tokens
before a single message — system tools 21.2k (16.6k of that deferred tool schemas), memory files
8.2k, system prompt 3.6k, skills 2.8k. Compaction only ever reclaims the *message* half. One
milestone of manager work cost ~35k of messages, so a milestone roughly doubles the window and a
compaction roughly halves it back. Two consequences: compacting at 7% is not premature — the
message half is what you are clearing, and it is already the same size as the floor; and no amount
of compaction discipline buys you the fixed 35.8k, so keeping the *number of milestones per
session* low matters as much as compacting at each one.

Levers, by impact:

1. **Make every milestone survivable, then compact at it.** No *tool* exposes your context size or
   clears it, and an automatic compaction never warns you first — so the ledger, written at every
   milestone, remains the only thing that crosses a compaction intact. What changes is who fires
   the compaction. **In a tmux session you can run `/compact` and `/context` on yourself** by
   typing into your own pane with `send-keys`; see `agents/tmux-self-drive.md` for the exact
   mechanism, its deferred timing, and the things you must never send. Outside tmux they are still
   the user's commands and the most you can do is say when compacting is cheap. Either way: write
   the ledger *before* the compaction, never after, and never claim a compaction you did not
   actually queue.
2. **Delegate reading, not just writing.** Five large docs cost ~50k of permanent context, re-read
   on every later turn. Send a recon worker for a digest, or use a context-inheriting fork so the
   raw output never lands in the manager.
3. **Do not poll.** Re-checking a background command or worker each turn is the cheapest-looking
   and most expensive habit available: every poll is a full-context turn that buys nothing.
   Harness-tracked work notifies on completion — do other work until it does.
4. **Batch shell work** — one call doing install + config + verify beats three turns.
5. **Cap worker reports** and read the detail file only when something failed.
6. **Verify with `--stat` and targeted `grep`**, never full diffs.
7. **One shared briefing file** per project context; each task prompt becomes "read it, then do X".

**Plan first — it is what creates the milestones.** A plan need not be complete or correct; the far
items can be placeholders refined as you go, and a wrong one costs nothing because it was never
load-bearing. Its real job is to manufacture the points at which work becomes durable and context
can be dropped. Without a plan there is no natural place to compact, so context grows to the end of
the session — which is how a session ends up spending most of its budget re-reading its own history.

**Keep a ledger.** `READ_AFTER_COMPACT.md` at the repo root holds the goal in the user's own terms,
item status, decisions already made, deliberately excluded scope, and the next action. Update it at
every loop step and read it first after any compaction. Being able to *fire* a compaction from
inside tmux does not make the ledger optional: compaction is lossy either way, the harness can
still fire one unannounced, and a self-issued `/compact` with no ledger behind it destroys exactly
the state you were about to need.

---

## 9) Keep the record honest

These files are load-bearing for every future agent; a stale one costs more than a missing one.
After a change lands, update what it invalidated:

- `agents/repo-map.md` — module-by-module map.
- `agents/pros-n-cons.md` — strengths, caveats, gaps.
- `agents/todo-n-fixme.md` — open work only; delete what is done.
- `agents/opus-manager.json`, `agents/sonnet-worker.json` — the role contracts.
- `agents/tmux-self-drive.md` — self-issued slash commands and pane capture when running in tmux.
- `.claude/skills/teamwork/SKILL.md` — the invocable form of the delivery loop. It restates §2 and
  §8 as a procedure; when either changes, bump the skill's `version:` and change it in step.
- `plans/` — plans and definitions of done. **A plan file may be deleted when complete; if you
  delete one, grep for references to it first** (`README.md`, `Makefile`, `.githooks/*`, docstrings)
  and retarget them, or you leave dangling pointers behind.
