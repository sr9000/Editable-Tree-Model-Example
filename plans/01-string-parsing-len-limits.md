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

- [ ] **Commit 1.1 — Add `INFERENCE_*` constants to settings**
  - Add the constants above to [`settings.py`](../settings.py) with provisional
    defaults and explanatory comments distinguishing them from the existing
    *edit-warning* limits.
  - **DoD:** constants importable; a unit test asserts they are positive ints and
    documents the inference-vs-edit-warning distinction. Gate passes.

- [ ] **Commit 1.2 — Pure length-gate helpers (tree-isolation safe)**
  - Add `tree/inference_limits.py` (or extend `tree/types.py`) with small pure
    predicates, e.g. `datetime_inference_allowed(s)`, `affix_inference_allowed(s)`,
    `color_inference_allowed(s)`, `base64_probe_allowed(s)`, each a cheap `len()`
    check against the relevant constant.
  - **DoD:** unit tests cover boundary lengths (exactly at / just over limit);
    helpers import only `settings`. Gate passes (`make check-tree-isolation`).

- [ ] **Commit 1.3 — Gate `parse_datetime_text`**
  - In [`parse_datetime_text()`](../core/datetime_parsing/regex.py:36) (or at its
    call site in [`parse_json_type`](../tree/types.py:166)), short-circuit when
    `len(s) > INFERENCE_MAX_DATETIME_CHARS` **before** `DATETIME_RE.fullmatch`.
    Keep `core/` Qt-free.
  - **DoD:** test proves a giant near-date string returns "not a datetime" without
    invoking the regex/pandas path (assert via timing budget from Plan 0 harness
    and/or a spy). Existing datetime tests still pass. Gate passes.

- [ ] **Commit 1.4 — Gate `parse_number_affix`**
  - Add a `len()` precheck before `_CURRENCY_RE` / `_UNITS_RE` `fullmatch` in
    [`parse_number_affix()`](../units/number_affix.py:79) (guard string total
    length, not just affix length).
  - **DoD:** giant near-affix string returns `None` fast; affix round-trip tests
    in [`tests/test_io_number_affix.py`](../tests/test_io_number_affix.py:1) pass.
    Gate passes.

- [ ] **Commit 1.5 — Gate color inference**
  - Short-circuit `looks_like_color_rgb/rgba` when `len(s) > INFERENCE_MAX_COLOR_CHARS`.
  - **DoD:** `"#" + "f"*N` returns not-a-color in O(1); color tests pass. Gate passes.

- [ ] **Commit 1.6 — Gate base64 / decompress probe**
  - In [`_looks_like_base64()`](../tree/types.py:32) and the base64→zlib/gzip
    branch of [`parse_json_type`](../tree/types.py:185), skip decode/decompress
    when `len(s) > INFERENCE_MAX_BASE64_PROBE_CHARS`; classify as text instead.
  - **DoD:** huge base64-like string classifies as `STRING`/`UNICODE` without
    allocating a giant decoded buffer; existing BYTES/ZLIB/GZIP tests pass. Gate passes.

- [ ] **Commit 1.7 — Top-level total-length fast path in `parse_json_type`**
  - At the start of the `str` branch in [`parse_json_type`](../tree/types.py:151),
    when `len(s) > INFERENCE_MAX_TOTAL_CHARS`, skip all heuristic branches and
    return only the cheap text classification (multiline vs line, ascii vs unicode).
  - **DoD:** giant strings of every Plan 0 family classify to a text type within
    budget; small strings keep current behavior exactly (regression test diffs the
    inferred type for a fixture corpus before/after). Gate passes.

- [ ] **Commit 1.8 — Cap `compute_editable` decode/decompress**
  - In [`compute_editable()`](../tree/item_coercion.py:578), bound the decode/
    decompress used to decide editability by `EDITABLE_DECODE_LIMIT_BYTES`
    (or trust already-known metadata) so load-time per-node checks stay cheap.
  - **DoD:** binary-like node above the cap is handled without full decompress;
    editability of normal binary nodes unchanged (tests). Gate passes.

- [ ] **Commit 1.9 — Cap `format_with_type` paint-time decode**
  - In [`format_with_type()`](../delegates/formatting/value_formatting.py:132),
    only decode what the preview needs (first ~16 bytes) and bound work by
    `FORMAT_PREVIEW_DECODE_LIMIT_BYTES`; avoid full decompression on every paint.
  - **DoD:** preview for a huge binary value renders within budget; preview text
    for normal values unchanged (snapshot test). Gate passes.

- [ ] **Commit 1.10 — MILESTONE: explicit type-change bypasses the gates**
  - **Requirement:** when the user picks a target type in the Type column, run the
    full expensive parser **for that target kind**, ignoring the inference caps.
  - **Investigation required (exact seam must be confirmed in code):**
    - Trace the explicit type-change path from the Type delegate
      ([`delegates/type_delegate.py`](../delegates/type_delegate.py:1)) through
      `commit_set_data` → [`DocumentMutationGateway`](../documents/seams/mutation_gateway.py:1)
      → model → [`tree/item_coercion.py`](../tree/item_coercion.py:1).
    - Identify where coercion currently decides whether to parse (e.g. the
      `explicit_type` flag on [`JsonTreeItem`](../tree/item.py:49)) and what
      function performs target-kind conversion (color/datetime/affix/base64).
    - Decide the bypass mechanism: a `force: bool` / `allow_expensive: bool`
      parameter threaded into the gated helpers (default `False` = inference,
      `True` = explicit coercion), **without** widening `parse_json_type`'s public
      signature in a way that breaks tree isolation.
  - After investigation, **edit this commit** into concrete sub-commits (e.g.
    "add `force` param to gated helpers", "pass `force=True` from coercion",
    "wire explicit path").
  - **DoD (target behavior):** changing a 10 MB string field's type to
    `datetime` / `bytes` / `currency` runs the real target parser and either
    converts or shows the normal failure/placeholder — it does **not** silently
    fall back due to the length gate. Inference of the same value (on load) still
    short-circuits. Tests assert both paths. Gate passes.

- [ ] **Commit 1.11 — Regression sweep vs Plan 0 harness**
  - Re-run the Plan 0 scaling/budget tests against the now-gated functions and
    confirm previously-flagged functions pass within budget.
  - Update `reports/parsing-vulnerability-<date>.md` with before/after numbers.
  - **DoD:** no candidate function from Plan 0 remains super-linear under
    inference; report updated; full suite green. Gate passes.
