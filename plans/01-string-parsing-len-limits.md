# Plan 1 — Length limits for expensive inference, with explicit-type bypass

**Goal:** Make automatic type inference cheap for oversized strings by checking `len(text)` before regex, datetime, number-affix, base64, decode, and decompress work. When an input exceeds the configured inference limit, automatic inference returns a text type (`STRING`, `UNICODE`, or `TEXT`) without entering the expensive branch.

**Critical exception:** An explicit user type change from the Type column is not automatic inference. Explicit coercion must call the target parser/converter with `allow_expensive=True` so the requested target type is attempted even when the source string exceeds the inference limit. The explicit path may still fail with the same validation or conversion failure used today; it must not silently fall back because of an inference gate.

**Dependency:** Start this plan only after [`Plan 0`](00-parsing-vulnerability-tests.md) Commit 0.8 has produced `reports/parsing-vulnerability-<YYYY-MM-DD>.md` and confirmed or changed the threshold values below.

See [`plans/index.md`](index.md) for the mandatory gate every commit must pass.

## Inference and coercion boundaries

Automatic inference currently runs in these locations:

- [`_decode_number_affixes()`](../io_formats/load.py:41), which calls [`parse_json_type()`](../tree/types.py:125) while loading data.
- [`JsonTreeItem.__init__()`](../tree/item.py:37), which calls [`parse_json_type()`](../tree/types.py:125) while building model items.
- [`infer_text_json_type()`](../tree/types.py:81), which classifies string text fallback cases.

Explicit coercion currently starts when the Type delegate commits a user-selected type and flows through [`delegates/type_delegate.py`](../delegates/type_delegate.py:1), `commit_set_data`, [`DocumentMutationGateway`](../documents/seams/mutation_gateway.py:1), `QUndoCommand`, [`JsonTreeModel.setData()`](../tree/model.py:1), [`JsonTreeItem.set_data()`](../tree/item.py:1), and [`tree/item_coercion.py`](../tree/item_coercion.py:1). This path must pass `allow_expensive=True` to target-specific conversion helpers.

## Storage decision

Add hard safety constants in [`settings.py`](../settings.py) with names beginning `INFERENCE_`, plus decode/preview caps named below. These values are not user-exposed settings and must not use `QSettings`. They are distinct from `STRING_EDIT_WARNING_LIMIT_CHARS`, `MULTILINE_EDIT_WARNING_LIMIT_CHARS`, and binary editor-opening warning limits, which control manual editor UX rather than load-time inference.

## Threshold table

Commit 0.8 confirmed these values based on [`reports/parsing-vulnerability-2026-06-13.md`](../reports/parsing-vulnerability-2026-06-13.md). The report measured 832 rows across 16 registry entries and 13 adversarial families (including trace_repetition, source_code_repetition, and escape_heavy for realistic content) at sizes 1024, 4096, 16384, and 65536. All functions pass at 65536 except `decode_bytes` which errors on non-base64 input (expected behavior). The superlinear scaling observations (141 rows) are within acceptable bounds for the configured 3.0 ratio threshold.

| Constant | Guards | Value | Plan 0 justification |
|---|---|---:|---|
| `INFERENCE_MAX_TOTAL_CHARS` | Top of the `str` branch in [`parse_json_type()`](../tree/types.py:125) | `65536` | Report: all text fallback checks pass at 65536 with median < 1ms |
| `INFERENCE_MAX_DATETIME_CHARS` | [`parse_datetime_text()`](../core/datetime_parsing/regex.py:36) regex and datetime conversion | `128` | Report: DATETIME_RE.fullmatch passes at 65536; 128 is conservative for valid datetime strings |
| `INFERENCE_MAX_AFFIX_CHARS` | [`parse_number_affix()`](../units/number_affix.py:79) regex checks | `256` | Report: parse_number_affix passes at 65536 for valid inputs; 256 is conservative for valid affix strings |
| `INFERENCE_MAX_COLOR_CHARS` | [`looks_like_color_rgb()`](../tree/types.py:24) and [`looks_like_color_rgba()`](../tree/types.py:28) | `9` | Maximum length of `#RGB`, `#RRGGBB`, `#RGBA`, and `#RRGGBBAA` color strings |
| `INFERENCE_MAX_BASE64_PROBE_CHARS` | `_looks_like_base64()` and base64/zlib/gzip inference branches in [`parse_json_type()`](../tree/types.py:125) | `1048576` | Report: _looks_like_base64 passes at 65536; extended to 1MB for reasonable base64 payloads |
| `EDITABLE_DECODE_LIMIT_BYTES` | [`compute_editable()`](../tree/item_coercion.py:578) decode/decompress checks | `1048576` | Report: compute_editable passes at 65536; 1MB provides headroom for valid encoded payloads |
| `FORMAT_PREVIEW_DECODE_LIMIT_BYTES` | [`format_with_type()`](../delegates/formatting/value_formatting.py:132) display preview | `64` | Preview needs only enough bytes to render the existing prefix text |

## Isolation rules for this plan

- New inference helpers under `tree/`, `core/`, or `tree/codecs/` may import [`settings.py`](../settings.py) and standard-library modules only.
- Files under `tree/` must not import `app/`, `documents/`, `editors/`, `delegates/`, `state/`, or `validation/`.
- Files under `core/` must remain Qt-free.
- UI and delegate files may call bounded helpers but must not own inference policy.

---

## Commits

### Commit 1.1 — Add safety constants to settings
- [ ] Completed

**Problem it solves:** Every gate needs one canonical source for threshold values, and those values must be visibly separate from editor-opening warning limits.

**Files it touches:**
- [`settings.py`](../settings.py) — add the constants listed in the threshold table with integer values.
- `tests/test_inference_constants.py` — new unit test for constant type, positivity, and distinction from editor-opening warning limits.

**Expected behavior:** Production and tests import the constants from `settings` without initializing Qt or `QSettings`.

**Acceptance criteria:**
- Each constant is an `int` greater than zero.
- Test names explicitly state that inference limits are load-time safety limits, not editor-warning limits.
- Mandatory gate passes.

### Commit 1.2 — Add pure length-gate helpers with bypass flag
- [ ] Completed

**Problem it solves:** Call sites need one policy API for checking whether an expensive inference branch may run, and explicit coercion needs a shared bypass flag.

**Files it touches:**
- `tree/inference_limits.py` — new module with `datetime_inference_allowed(text, allow_expensive=False)`, `affix_inference_allowed(text, allow_expensive=False)`, `color_inference_allowed(text, allow_expensive=False)`, `base64_probe_allowed(text, allow_expensive=False)`, `total_inference_allowed(text)`, `editable_decode_allowed(byte_count)`, and `format_preview_decode_allowed(byte_count)`.
- `tests/test_inference_limits.py` — new tests for boundary lengths at exactly the limit and one character/byte above the limit.

**Expected behavior:** For the four `*_inference_allowed` helpers, `allow_expensive=True` returns `True` regardless of text length. `total_inference_allowed`, `editable_decode_allowed`, and `format_preview_decode_allowed` do not have a bypass because they protect automatic inference or repeated display/editability work.

**Acceptance criteria:**
- The helper module imports only `settings` and standard-library modules.
- Boundary tests cover allowed-at-limit and rejected-above-limit for every helper.
- Mandatory gate passes, including `make check-tree-isolation`.

### Commit 1.3 — Trace and test the explicit coercion bypass seam
- [ ] Completed

**Problem it solves:** Gates added in later commits must not change explicit type-change behavior. The implementation needs a tested seam before any parser starts rejecting oversized inference inputs.

**Files it touches:**
- [`tree/item_coercion.py`](../tree/item_coercion.py:1) — identify the explicit-coercion entry point and pass `allow_expensive=True` to target-specific converters introduced or updated by later commits.
- [`tree/item.py`](../tree/item.py:49) — use the existing `explicit_type` state to distinguish user-selected types from inferred types.
- `tests/test_explicit_type_bypass.py` — new tests with monkeypatched target converters that record the `allow_expensive` value for automatic inference versus explicit coercion.

**Expected behavior:** Automatic inference passes `allow_expensive=False`. Explicit type changes pass `allow_expensive=True` before any length gate is evaluated.

**Acceptance criteria:**
- Tests cover at least datetime, number-affix, color, and binary target conversions.
- No public `parse_json_type()` signature change is required for the explicit path.
- Mandatory gate passes.

### Commit 1.4 — Gate datetime inference
- [ ] Completed

**Problem it solves:** Oversized near-date strings must not run `DATETIME_RE.fullmatch` or datetime conversion during automatic inference.

**Files it touches:**
- [`core/datetime_parsing/regex.py`](../core/datetime_parsing/regex.py:36) — add an `allow_expensive=False` parameter to [`parse_datetime_text()`](../core/datetime_parsing/regex.py:36) and return the existing not-a-datetime result before regex work when `datetime_inference_allowed(text, allow_expensive)` is `False`.
- Call sites in [`tree/types.py`](../tree/types.py:125) and [`tree/item_coercion.py`](../tree/item_coercion.py:1) — pass `allow_expensive=False` for inference and `True` for explicit coercion.
- `tests/test_datetime_inference_limits.py` — new tests for oversized automatic inference and explicit bypass.

**Expected behavior:** A near-date string longer than `INFERENCE_MAX_DATETIME_CHARS` returns not-a-datetime during inference without invoking the regex. The same string reaches the datetime parser when explicitly coerced.

**Acceptance criteria:**
- Spy test proves `DATETIME_RE.fullmatch` is not called for oversized inference input.
- Existing datetime tests pass unchanged for strings at or below the limit.
- Mandatory gate passes.

### Commit 1.5 — Gate number-affix inference
- [ ] Completed

**Problem it solves:** Oversized near-affix strings must not run `_CURRENCY_RE.fullmatch` or `_UNITS_RE.fullmatch` during automatic inference.

**Files it touches:**
- [`units/number_affix.py`](../units/number_affix.py:79) — add `allow_expensive=False` to [`parse_number_affix()`](../units/number_affix.py:79) and return `None` before regex work when `affix_inference_allowed(text, allow_expensive)` is `False`.
- Call sites in [`io_formats/load.py`](../io_formats/load.py:41), [`tree/types.py`](../tree/types.py:125), and [`tree/item_coercion.py`](../tree/item_coercion.py:1) — pass the correct flag for inference versus explicit coercion.
- Existing affix tests in [`tests/test_io_number_affix.py`](../tests/test_io_number_affix.py:1) plus a new oversized-inference test.

**Expected behavior:** A near-affix string longer than `INFERENCE_MAX_AFFIX_CHARS` returns `None` during inference before regex matching. Existing valid affix strings at or below the limit keep their current parse result.

**Acceptance criteria:**
- Spy test proves neither affix regex is called for oversized inference input.
- Explicit type change to an affix target reaches the converter with `allow_expensive=True`.
- Mandatory gate passes.

### Commit 1.6 — Gate color inference
- [ ] Completed

**Problem it solves:** Strings longer than the maximum valid color length must not scan color regexes during automatic inference.

**Files it touches:**
- [`tree/types.py`](../tree/types.py:24) — gate `looks_like_color_rgb(text, allow_expensive=False)` and [`looks_like_color_rgba()`](../tree/types.py:28) with `color_inference_allowed`.
- [`tree/item_coercion.py`](../tree/item_coercion.py:1) — pass `allow_expensive=True` for explicit color coercion.
- Existing color tests plus `tests/test_color_inference_limits.py`.

**Expected behavior:** `"#" + "f" * 1000` returns not-a-color during inference before regex work. Strings of length `3`, `4`, `7`, and `9` keep their current behavior.

**Acceptance criteria:**
- Oversized inference test proves the regex wrapper is not called.
- Explicit color coercion bypasses the length gate and returns the existing success/failure result.
- Mandatory gate passes.

### Commit 1.7 — Gate base64, zlib, and gzip inference probes
- [ ] Completed

**Problem it solves:** Oversized base64-like strings must not allocate decoded buffers or attempt zlib/gzip decompression during automatic inference.

**Files it touches:**
- [`tree/types.py`](../tree/types.py:32) — gate `_looks_like_base64(text, allow_expensive=False)` with `base64_probe_allowed`.
- [`tree/types.py`](../tree/types.py:185) — skip base64 decode, zlib decompress, and gzip decompress branches when `base64_probe_allowed(text, False)` is `False`.
- [`tree/item_coercion.py`](../tree/item_coercion.py:1) and [`tree/codecs/bytes_codec.py`](../tree/codecs/bytes_codec.py:8) — expose/pass `allow_expensive=True` for explicit binary coercion where target conversion uses the same probe.
- Existing BYTES/ZLIB/GZIP tests plus a new oversized base64-like regression test.

**Expected behavior:** Oversized base64-like inference input classifies as `STRING`, `UNICODE`, or `TEXT` without calling `base64.b64decode`, zlib decompress, or gzip decompress. Explicit binary coercion reaches the existing converter and returns the existing result or failure placeholder.

**Acceptance criteria:**
- Spy test proves no decode/decompress function is called for oversized inference input.
- Valid BYTES/ZLIB/GZIP fixtures at or below the limit keep current inferred types.
- Mandatory gate passes.

### Commit 1.8 — Add top-level total-length text fast path
- [ ] Completed

**Problem it solves:** Oversized strings need one top-level path that skips all non-text heuristics once their length exceeds the total inference cap.

**Files it touches:**
- [`tree/types.py`](../tree/types.py:151) — at the start of the `str` branch in [`parse_json_type()`](../tree/types.py:125), when `total_inference_allowed(text)` is `False`, return only a text type based on these checks: contains newline -> `TEXT`; contains non-ASCII -> `UNICODE`; otherwise `STRING`.
- `tests/test_parse_json_type_limits.py` — new fixture corpus asserting small-string behavior is unchanged and oversized strings use the text fast path.

**Expected behavior:** Oversized strings from all ten Plan 0 families classify to a text type without running datetime, affix, color, base64, zlib, or gzip inference branches.

**Acceptance criteria:**
- Small fixture corpus has identical inferred types before and after this commit.
- Oversized family tests complete within the Plan 0 budget.
- Mandatory gate passes.

### Commit 1.9 — Cap `compute_editable` decode/decompress work
- [ ] Completed

**Problem it solves:** Load-time editability checks must not fully decode/decompress binary-like values larger than `EDITABLE_DECODE_LIMIT_BYTES`.

**Files it touches:**
- [`tree/item_coercion.py`](../tree/item_coercion.py:578) — use `editable_decode_allowed` before decode/decompress work used only to decide editability.
- Existing binary editability tests plus a new oversized binary-like test.

**Expected behavior:** A binary-like node above the cap avoids full decode/decompress and receives the conservative editability result defined in the test. Normal binary nodes at or below the cap keep current editability.

**Acceptance criteria:**
- Spy test proves oversized editability checks do not call full decode/decompress.
- Existing binary editability tests pass.
- Mandatory gate passes.

### Commit 1.10 — Cap paint-time binary preview decode
- [ ] Completed

**Problem it solves:** Display formatting must not fully decode/decompress multi-megabyte binary values during every paint.

**Files it touches:**
- [`delegates/formatting/value_formatting.py`](../delegates/formatting/value_formatting.py:132) — decode at most `FORMAT_PREVIEW_DECODE_LIMIT_BYTES` bytes needed for the existing preview format.
- `tests/test_value_formatting_preview_limits.py` — new snapshot tests for normal previews and oversized binary previews.

**Expected behavior:** Normal preview text is unchanged. Oversized binary preview returns the same prefix format with an explicit truncation marker and does not decode beyond the preview cap.

**Acceptance criteria:**
- Snapshot tests cover BYTES, ZLIB, and GZIP preview text at normal sizes.
- Oversized preview test proves decode/decompress work is capped.
- Mandatory gate passes.

### Commit 1.11 — Regression sweep against Plan 0 harness
- [ ] Completed

**Problem it solves:** The gates must eliminate the vulnerabilities measured in Plan 0 under automatic inference, while preserving explicit conversion behavior.

**Files it touches:**
- `tests/perf/` — rerun Plan 0 perf tests against the gated implementation.
- `reports/parsing-vulnerability-<YYYY-MM-DD>.md` — append a before/after section with the same row schema used by Plan 0.
- This threshold table — update any value changed by the before/after run and cite the row that justifies it.

**Expected behavior:** Automatic inference rows for target functions are no longer classified as `superlinear` or `allocation_exceeded`. Rows for explicit conversion tests show the target parser/converter was reached.

**Acceptance criteria:**
- Plan 0 opt-in report contains before/after rows for every original vulnerable function.
- No automatic-inference row remains `superlinear` or `allocation_exceeded` after gates.
- Full test suite and mandatory gate pass.
