# Agent Guide — Editable-Tree-Model-Example

_How agents are expected to work in this repository. High-signal and prescriptive; keep it that way._
**Last updated:** 2026-09-06

---

## 0) Start here — which agent are you?

Work in this repo runs as a **manager/worker split**. Decide your role before doing anything else,
then read your own contract:

| Role | Model / effort | Contract | One-line job |
|:---|:---|:---|:---|
| **Manager / architect** | Opus, high effort | `agents/opus-manager.json` | Decide, decompose, review, gate, commit. |
| **Worker / subagent** | Sonnet, low effort | `agents/sonnet-worker.json` | Execute one prescriptive task. Escalate, never improvise. |

The two JSON files are the machine-readable session contracts — scope, allowed commands, escalation
triggers, report format. **This file is the shared briefing; those files are your role's rules.**

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
7. Repeat.

Hard rules:

- Gate red → back to implementation. **No commit.** Never relax a check to get green.
- Do not batch plan items into one commit unless the plan says so.
- Do not stop at "green but uncommitted". That is an unfinished task, not a handoff.
- **Never push to `master`.** Feature branches only.

---

## 3) How the split actually runs

**Manager.** Owns architecture, decomposition, sequencing, **all** blocker resolution, review of
every diff, the gate, and the commit. Delegates mechanical edits *and reading* — a recon worker that
returns a digest is far cheaper than five large files landing permanently in the manager's context.

**Worker briefs must be self-contained.** Fresh workers inherit nothing. Every brief carries:

- full context (no "as discussed"), exact file paths, and exact literal content wherever precision
  matters — regexes, TOML, Makefile tabs;
- the one acceptance check to run;
- an explicit **"stop and report, do not fix"**;
- a report cap: _verdict plus at most 5 bullets; write full detail to a file and return the path._

**Trust but verify.** A worker report states intent, not outcome. Re-check with `git diff --stat`
and a targeted `grep` for the exact changed token — never by pulling a full diff into context.

**Do not delegate** a task that needs a design choice, a task smaller than the brief describing it,
or two tasks that touch the same file.

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
- The full suite is **1813 tests**, all passing on Python 3.14. **A count other than 1813 means
  something is miscollected — investigate before trusting a green run.**

---

## 8) Context economics (measured 2026-09-06)

Manager cost is dominated by **cache reads ≈ context size × turns**, not by output. One migration
session burned 33.2M cache reads against a 239k context over ~140 turns while emitting only 290k
output tokens. Shrinking context and cutting turn count beat delegating more tasks.

Levers, by impact:

1. **Delegate reading, not just writing.** Five large docs cost ~50k of permanent context, re-read
   on every later turn. Send a recon worker for a digest, or use a context-inheriting fork so the
   raw output never lands in the manager.
2. **Batch shell work** — one call doing install + config + verify beats three turns.
3. **Cap worker reports** and read the detail file only when something failed.
4. **Verify with `--stat` and targeted `grep`**, never full diffs.
5. **One shared briefing file** per project context; each task prompt becomes "read it, then do X".
6. **Compact at phase boundaries** — detail from a committed phase is dead weight.

---

## 9) Keep the record honest

These files are load-bearing for every future agent; a stale one costs more than a missing one.
After a change lands, update what it invalidated:

- `agents/repo-map.md` — module-by-module map.
- `agents/pros-n-cons.md` — strengths, caveats, gaps.
- `agents/todo-n-fixme.md` — open work only; delete what is done.
- `agents/opus-manager.json`, `agents/sonnet-worker.json` — the role contracts.
- `plans/` — plans and definitions of done. **A plan file may be deleted when complete; if you
  delete one, grep for references to it first** (`README.md`, `Makefile`, `.githooks/*`, docstrings)
  and retarget them, or you leave dangling pointers behind.
