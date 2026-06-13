# Plan 1 — `len()`-based limits for expensive parsing, with explicit-type bypass

**Goal:** Make automatic type **inference** cheap and safe by short-circuiting
expensive parsing/regex/decode work when the input string is longer than a
per-kind `len()` threshold. Inference of a giant string must fall back to a
safe text type (`STRING` / `UNICODE` / `TEXT`) quickly.

**Critical exception:** When the **user explicitly changes a field's type** via
the Type column, the app must run the **full, expensive parser for that target
kind regardless of length** (the user asked for it). The length gates apply only
to *automatic inference*, never to *explicit coercion*.

See [`plans/index.md`](index.md) for the **mandatory gate** every commit must pass.

## Background (where inference vs explicit coercion happen)

- Automatic inference runs in:
  - [`_decode_number_affixes()`](../io_formats/load.py:41) (calls `parse_json_type` per string during load),
  - [`JsonTreeItem.__init__()`](../tree/item.py:37) → `parse_json_type(value)` per node during model build,
  - [`infer_text_json_type()`](../tree/types.py:81) / container conversions.
- Explicit coercion runs when the user picks a type in the Type column. The
  request flows delegate → `commit_set_data` → `DocumentMutationGateway` →
  `QUndoCommand` → model → item, with `explicit_type` set on the item
  ([`tree/item.py`](../tree/item.py:49)) and conversion handled in
  [`tree/item_coercion.py`](../tree/item_coercion.py:1).

> **Design constraint:** The length gate must live where `tree/` isolation holds
> — pure helpers in `tree/`, `core/`, or `tree/codecs/`, importing only
> `settings.py`. No `app/`, `documents/`, `editors/`, etc.

## Threshold storage — DECISION (default chosen, revisit allowed)

The report asks: fixed constants, persisted `state/edit_limits.py` settings, or
hard non-UI safety limits?

**Default decision for this plan:** add **hard safety constants** in
[`settings.py`](../settings.py) (named `INFERENCE_*`), *not* user-exposed. These
are correctness/DoS guards, distinct from the existing UX warning limits
(`STRING_EDIT_WARNING_LIMIT_CHARS`, etc.) which gate *editor opening*, not parsing.
If product later wants them tunable, a follow-up can mirror them into
`state/edit_limits.py`. This keeps Plan 1 self-contained and avoids QSettings I/O
inside hot parsing loops.

## Threshold values — **TBD from [`Plan 0`](00-parsing-vulnerability-tests.md)**

| Constant | Guards | Provisional default | Final value |
|---|---|---|---|
| `INFERENCE_MAX_TOTAL_CHARS` | overall cap before `parse_json_type` attempts any non-trivial branch | 64 * 1024 | TBD (Plan 0) |
| `INFERENCE_MAX_DATETIME_CHARS` | `parse_datetime_text` precheck | 64 | TBD |
| `INFERENCE_MAX_AFFIX_CHARS` | `parse_number_affix` precheck | 64 | TBD |
| `INFERENCE_MAX_COLOR_CHARS` | color regex precheck | 9 | TBD |
| `INFERENCE_MAX_BASE64_PROBE_CHARS` | base64 syntactic + decode probe | 1 * 1024 * 1024 | TBD |
| `EDITABLE_DECODE_LIMIT_BYTES` | `compute_editable` decode/decompress cap | reuse `BINARY_EDIT_WARNING_LIMIT_BYTES`? TBD | TBD |
| `FORMAT_PREVIEW_DECODE_LIMIT_BYTES` | `format_with_type` paint-time decode cap | small (only need first 16 bytes) | TBD |

> Provisional defaults let development proceed before Plan 0 completes, but the
> final values **must** be confirmed against the Plan 0 report. Color cap is safe
> to finalize immediately (a valid color is ≤ 9 chars).

---

## Commits

### Commit 1.1 — Add `INFERENCE_*` constants to settings
- [ ] Completed

**Problem it solves:** Every subsequent gate in this plan reads a per-kind `len()` threshold. Those thresholds need a single canonical home, with provisional defaults, so that helpers and call sites can import them without scattering magic numbers. The constants must be visibly distinct from the existing *editor-opening* warning limits.

**Files it touches:**
- [`settings.py`](../settings.py) — add the `INFERENCE_*` constants with provisional defaults and comments distinguishing them from the existing edit-warning limits.
- A new unit test (e.g. `tests/test_inference_constants.py`) — asserts the constants are positive ints and documents the inference-vs-edit-warning distinction.

**DoD and gates:**
- Constants are importable from `settings`.
- Unit test asserts positive ints and documents the inference-vs-edit-warning distinction.
- Mandatory gate passes.

### Commit 1.2 — Pure length-gate helpers (tree-isolation safe)
- [ ] Completed

**Problem it solves:** Call sites in `parse_json_type` and the parse helpers need a uniform way to ask "is this string short enough to attempt the expensive parse?". Embedding raw `len(s) > N` checks at every call site would scatter policy and break tree isolation if done inside `app/`/etc.

**Files it touches:**
- `tree/inference_limits.py` — new module (or `tree/types.py` extension) with small pure predicates: `datetime_inference_allowed(s)`, `affix_inference_allowed(s)`, `color_inference_allowed(s)`, `base64_probe_allowed(s)`. Each is a cheap `len()` check against the relevant `INFERENCE_*` constant. Imports only `settings`.
- A new unit test — covers boundary lengths (exactly at / just over limit) for each helper.

**DoD and gates:**
- Helpers import only `settings`; no `app/`, `documents/`, `editors/`, `delegates/`, `state/`, `validation/` imports.
- Boundary tests pass.
- Mandatory gate passes (including `make check-tree-isolation`).

### Commit 1.3 — Gate `parse_datetime_text`
- [ ] Completed

**Problem it solves:** A giant near-date string (e.g. 10 MB of digits prefixed date-like) currently makes `parse_datetime_text` attempt `DATETIME_RE.fullmatch` and possibly the pandas/dateutil fallback — both expensive. We must short-circuit on length before the regex.

**Files it touches:**
- [`core/datetime_parsing/regex.py`](../core/datetime_parsing/regex.py:36) — add `len()` precheck using `INFERENCE_MAX_DATETIME_CHARS` *before* `DATETIME_RE.fullmatch`. Keep `core/` Qt-free.
- Or alternatively, gate at the call site in [`parse_json_type`](../tree/types.py:166).
- A new unit test — proves a giant near-date string returns "not a datetime" without invoking the regex/pandas path (assert via Plan 0 timing budget and/or a spy).

**DoD and gates:**
- Giant near-date string returns not-a-datetime in O(1).
- Existing datetime tests still pass.
- Mandatory gate passes.

### Commit 1.4 — Gate `parse_number_affix`
- [ ] Completed

**Problem it solves:** A long currency/unit prefix combined with a huge digit run can make `_CURRENCY_RE` / `_UNITS_RE` slow. The existing `NUMBER_AFFIX_MAX_LEN` guards the affix length, but a giant *string total length* with a near-affix prefix can still be expensive. We need a guard on the total input length.

**Files it touches:**
- [`units/number_affix.py`](../units/number_affix.py:79) — add `len()` precheck (string total length) before `_CURRENCY_RE` / `_UNITS_RE` `fullmatch`.
- Existing affix tests in [`tests/test_io_number_affix.py`](../tests/test_io_number_affix.py:1) — must continue to pass.

**DoD and gates:**
- Giant near-affix string returns `None` fast.
- Existing affix round-trip tests pass.
- Mandatory gate passes.

### Commit 1.5 — Gate color inference
- [ ] Completed

**Problem it solves:** `"#" + "f" * N` makes the color regexes scan arbitrarily long inputs. A valid color is ≤ 9 chars, so a hard cap is safe to finalize immediately.

**Files it touches:**
- `tree/types.py` — short-circuit `looks_like_color_rgb` / `looks_like_color_rgba` when `len(s) > INFERENCE_MAX_COLOR_CHARS`.
- Existing color tests — must continue to pass.

**DoD and gates:**
- `"#" + "f"*N` returns not-a-color in O(1).
- Color tests pass.
- Mandatory gate passes.

### Commit 1.6 — Gate base64 / decompress probe
- [ ] Completed

**Problem it solves:** The base64→zlib/gzip decode probe in `parse_json_type` can be tricked into allocating giant decoded buffers for huge base64-like strings. We must cap the probe by total input length and fall back to text classification above the cap.

**Files it touches:**
- [`tree/types.py`](../tree/types.py:32) — in `_looks_like_base64()` and the base64→zlib/gzip branch of [`parse_json_type`](../tree/types.py:185), skip decode/decompress when `len(s) > INFERENCE_MAX_BASE64_PROBE_CHARS`; classify as text instead.
- Existing BYTES / ZLIB / GZIP tests — must continue to pass.

**DoD and gates:**
- Huge base64-like string classifies as `STRING`/`UNICODE` without allocating a giant decoded buffer.
- Existing BYTES/ZLIB/GZIP tests pass.
- Mandatory gate passes.

### Commit 1.7 — Top-level total-length fast path in `parse_json_type`
- [ ] Completed

**Problem it solves:** Even with per-branch gates, a giant string still walks through several cheap-but-not-free checks (multiline, ws-only, ASCII). We need an O(1) fast path at the top of the `str` branch that, above `INFERENCE_MAX_TOTAL_CHARS`, skips every heuristic and returns only the cheap text classification (multiline vs line, ASCII vs unicode).

**Files it touches:**
- [`tree/types.py`](../tree/types.py:151) — at the start of the `str` branch in `parse_json_type`, when `len(s) > INFERENCE_MAX_TOTAL_CHARS`, skip all heuristic branches and return only the cheap text classification.
- A new regression test — diffs the inferred type for a fixture corpus before/after, asserting small strings keep current behavior exactly and giant strings classify to a text type within budget.

**DoD and gates:**
- Giant strings of every Plan 0 family classify to a text type within budget.
- Small strings keep current behavior exactly (regression test).
- Mandatory gate passes.

### Commit 1.8 — Cap `compute_editable` decode/decompress
- [ ] Completed

**Problem it solves:** Load-time per-node editability checks can call full decode/decompress of a binary-like value to decide whether the field is editable. For a giant binary node this is unnecessarily expensive; we must bound the decode by `EDITABLE_DECODE_LIMIT_BYTES` (or trust already-known metadata) so the per-node check stays cheap.

**Files it touches:**
- [`tree/item_coercion.py`](../tree/item_coercion.py:578) — bound the decode/decompress used to decide editability by `EDITABLE_DECODE_LIMIT_BYTES`.
- Existing binary-editability tests — must continue to pass.

**DoD and gates:**
- A binary-like node above the cap is handled without full decompress.
- Editability of normal binary nodes is unchanged.
- Mandatory gate passes.

### Commit 1.9 — Cap `format_with_type` paint-time decode
- [ ] Completed

**Problem it solves:** `format_with_type` is called on every paint of a binary value, and a full decompression of a multi-MB binary on every paint is wasted work. Only the first ~16 bytes are needed for the preview, so the decode must be bounded by `FORMAT_PREVIEW_DECODE_LIMIT_BYTES`.

**Files it touches:**
- [`delegates/formatting/value_formatting.py`](../delegates/formatting/value_formatting.py:132) — only decode what the preview needs (first ~16 bytes) and bound work by `FORMAT_PREVIEW_DECODE_LIMIT_BYTES`; avoid full decompression on every paint.
- A snapshot test — asserts preview text for normal values is unchanged.

**DoD and gates:**
- Preview for a huge binary value renders within budget.
- Preview text for normal values is unchanged (snapshot test).
- Mandatory gate passes.

### Commit 1.10 — MILESTONE: explicit type-change bypasses the gates
- [ ] Completed

**Problem it solves:** The gates added in Commits 1.3–1.9 protect *automatic inference* on load. But when the user explicitly picks a target type in the Type column, the app must run the **full, expensive parser for that target kind** — the user asked for it. We must thread a "force / allow_expensive" signal through coercion so explicit type-changes bypass the gates while inference still short-circuits. Getting the seam wrong silently re-introduces the bug for the user-driven path.

**Required investigations:**
- Trace the explicit type-change path from the Type delegate ([`delegates/type_delegate.py`](../delegates/type_delegate.py:1)) through `commit_set_data` → [`DocumentMutationGateway`](../documents/seams/mutation_gateway.py:1) → model → [`tree/item_coercion.py`](../tree/item_coercion.py:1).
- Identify where coercion currently decides whether to parse (e.g. the `explicit_type` flag on [`JsonTreeItem`](../tree/item.py:49)) and which function performs target-kind conversion (color/datetime/affix/base64).
- Decide the bypass mechanism: a `force: bool` / `allow_expensive: bool` parameter threaded into the gated helpers (default `False` = inference, `True` = explicit coercion), **without** widening `parse_json_type`'s public signature in a way that breaks tree isolation.
- After investigation, expand this commit into concrete sub-commits (e.g. "add `force` param to gated helpers", "pass `force=True` from coercion", "wire explicit path").

**Files it touches:**
- The gated helpers from Commits 1.3–1.9 — accept a new `force` / `allow_expensive` parameter (default `False`).
- The coercion path in [`tree/item_coercion.py`](../tree/item_coercion.py:1) and the `explicit_type` flag plumbing in [`tree/item.py`](../tree/item.py:49) — pass `force=True` from the explicit-coercion entry point.
- New tests — assert both paths.

**DoD and gates (target behavior):**
- Changing a 10 MB string field's type to `datetime` / `bytes` / `currency` runs the real target parser and either converts or shows the normal failure/placeholder — it does **not** silently fall back due to the length gate.
- Inference of the same value (on load) still short-circuits.
- Mandatory gate passes.

### Commit 1.11 — Regression sweep vs Plan 0 harness
- [ ] Completed

**Problem it solves:** We have added nine per-branch gates; we must prove they actually fixed the Plan 0 findings (no candidate function remains super-linear under inference) and capture the before/after numbers in the report for posterity.

**Files it touches:**
- The Plan 0 scaling/budget tests in `tests/perf/` — re-run against the now-gated functions.
- `reports/parsing-vulnerability-<date>.md` — append a before/after section.
- Plan 1's threshold table — confirm final values now match the report.

**DoD and gates:**
- No candidate function from Plan 0 remains super-linear under inference.
- Report is updated with before/after numbers.
- Full test suite is green.
- Mandatory gate passes.
