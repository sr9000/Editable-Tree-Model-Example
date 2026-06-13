# Plan 1 — Length limits for expensive inference, with explicit-type bypass

**Goal:** Make automatic type inference cheap for oversized strings by checking `len(text)` before regex, datetime, number-affix, and color work. When an input exceeds the configured inference limit, automatic inference returns a text type (`STRING`, `UNICODE`, or `TEXT`) without entering the expensive branch. For base64/zlib/gzip, use content-based syntax validation (length mod 4 + alphabet regex) instead of a length cap — if the syntax is valid, decoding is allowed regardless of size.

**Critical exception:** An explicit user type change from the Type column is not automatic inference. Explicit coercion must call the target parser/converter with `allow_expensive=True` so the requested target type is attempted even when the source string exceeds the inference limit. The explicit path may still fail with the same validation or conversion failure used today; it must not silently fall back because of an inference gate.

**Dependency:** Start this plan only after [`Plan 0`](00-parsing-vulnerability-tests.md) Commit 0.8 has produced `reports/parsing-vulnerability-<YYYY-MM-DD>.md` and confirmed or changed the threshold values below.

See [`plans/index.md`](index.md) for the mandatory gate every commit must pass.

## Inference and coercion boundaries

Automatic inference currently runs in these locations:

- [`_decode_number_affixes()`](../io_formats/load.py:41), which calls [`parse_json_type()`](../tree/types.py:125) while loading data.
- [`JsonTreeItem.__init__()`](../tree/item.py:37), which calls [`parse_json_type()`](../tree/types.py:125) while building model items.
- [`infer_text_json_type()`](../tree/types.py:81), which classifies string text fallback cases.

**Note on double classification (out of scope for this plan):** The review report flags that [`_decode_number_affixes()`](../io_formats/load.py:41) calls [`parse_json_type()`](../tree/types.py:125) for every string, and [`JsonTreeItem.__init__()`](../tree/item.py:37) calls it again on the same value during model construction. The parsing-vulnerability report confirms both paths exhibit the same superlinear scaling (e.g., 32–36ms at 65536 on `digits` and `pathological_repetition`). This plan addresses the **length** dimension only. A follow-up plan should consider either a cheaper affix-only predicate for [`_decode_number_affixes()`](../io_formats/load.py:41) or a parse-metadata object that avoids repeated full inference. That follow-up is **not** part of Plan 1.

Explicit coercion currently starts when the Type delegate commits a user-selected type and flows through [`delegates/type_delegate.py`](../delegates/type_delegate.py:1), `commit_set_data`, [`DocumentMutationGateway`](../documents/seams/mutation_gateway.py:1), `QUndoCommand`, [`JsonTreeModel.setData()`](../tree/model.py:1), [`JsonTreeItem.set_data()`](../tree/item.py:1), and [`tree/item_coercion.py`](../tree/item_coercion.py:1). This path must pass `allow_expensive=True` to target-specific conversion helpers.

## Storage decision

Add hard safety constants in [`settings.py`](../settings.py) with names beginning `INFERENCE_`, plus a preview cap named below. These values are not user-exposed settings and must not use `QSettings`. They are distinct from `STRING_EDIT_WARNING_LIMIT_CHARS`, `MULTILINE_EDIT_WARNING_LIMIT_CHARS`, and binary editor-opening warning limits, which control manual editor UX rather than load-time inference.

## Threshold table

The report (`reports/parsing-vulnerability-2026-06-13.md`) measured 832 rows across 16 registry entries and 13 adversarial families (including `trace_repetition`, `source_code_repetition`, and `escape_heavy` for realistic content) at sizes 1024, 4096, 16384, and 65536. Key findings driving the threshold values:

- The 100ms per-call budget is never exceeded at any measured size.
- The worst automatic-inference median at 65536 is 36ms (`parse_json_type` on `pathological_repetition`), with a peak allocation of ~1555 bytes.
- 141 rows are classified `superlinear` (ratio > 3.0); all are on automatic inference paths and will be gated by the constants below.
- 44 rows are classified `error`: 4 are `parse_number_affix`/`parse_json_type` on `near_affix` at 16384+ hitting a pre-existing 4300-digit integer limit (not a regression; the 100-char affix gate prevents reaching this path); the remaining ~40 are `decode_bytes` on non-base64 input (expected `binascii.Error` failures, not crashes).

| Constant | Guards | Value | Plan 0 justification |
|---|---|---:|---|
| `INFERENCE_MAX_DATETIME_CHARS` | [`parse_datetime_text()`](../core/datetime_parsing/regex.py:36) regex and datetime conversion | `40` | Report: `DATETIME_RE.fullmatch` median is 0.00ms even at 65536 across all families; 40 is enough for any practically meaningful datetime string. |
| `INFERENCE_MAX_AFFIX_CHARS` | [`parse_number_affix()`](../units/number_affix.py:79) regex checks | `100` | Report: `parse_number_affix` is superlinear on `digits`, `plain_ascii`, `pathological_repetition` at 4096+ (ratio up to 4.89). 100 is well below the pre-existing 4300-digit integer limit, so the gate fires before the error path. |
| `INFERENCE_MAX_COLOR_CHARS` | [`looks_like_color_rgb()`](../tree/types.py:24) and [`looks_like_color_rgba()`](../tree/types.py:28) | `10` | Maximum length of `#RGB`, `#RRGGBB`, `#RGBA`, and `#RRGGBBAA` color strings. |
| `FORMAT_PREVIEW_DECODE_LIMIT_BYTES` | [`format_with_type()`](../delegates/formatting/value_formatting.py:132) display preview | `100` | Preview needs only enough bytes to render the existing prefix text. |

### Design decisions (removed constants)

- **No `INFERENCE_MAX_TOTAL_CHARS`**: The individual gates (datetime, affix, color) effectively skip all unnecessary checks for oversized strings. A top-level total-length fast path is redundant because once datetime, affix, color, and base64 probes are individually gated, the remaining work in `parse_json_type()` for strings is O(n) text classification (newline check, non-ASCII check, multiline check).

- **No `INFERENCE_MAX_BASE64_PROBE_CHARS`**: Instead of a length cap, base64 inference uses content-based syntax validation: (1) `len(text) % 4 == 0` (base64 encoding always produces length divisible by 4), then (2) regex check against the base64 alphabet `[A-Za-z0-9+/]+={0,2}` (whitespace and other characters are not valid). If both checks pass, the string is syntactically valid base64 and decoding is allowed regardless of size. This avoids false negatives on large valid base64 payloads while still rejecting non-base64 strings cheaply via the regex.

- **No `EDITABLE_DECODE_LIMIT_BYTES`**: If a string passes the base64 syntax validation (len mod 4 + alphabet regex), it is a valid encoded payload and decoding/decompressing is allowed. The `compute_editable()` function only decodes to verify editability; if the syntax is valid, the decode will succeed and the editability result is correct.

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
- [`settings.py`](../settings.py) — add the constants listed in the threshold table with integer values. Remove `INFERENCE_MAX_TOTAL_CHARS`, `INFERENCE_MAX_BASE64_PROBE_CHARS`, and `EDITABLE_DECODE_LIMIT_BYTES` (design decisions above).
- `tests/test_inference_constants.py` — update unit tests to cover only the four remaining constants.

**Expected behavior:** Production and tests import the constants from `settings` without initializing Qt or `QSettings`.

**Acceptance criteria:**
- Each constant is an `int` greater than zero.
- Test names explicitly state that inference limits are load-time safety limits, not editor-warning limits.
- Each constant's docstring cites the specific report row(s) that justify its value.
- Mandatory gate passes.

### Commit 1.2 — Add pure length-gate helpers with bypass flag
- [ ] Completed

**Problem it solves:** Call sites need one policy API for checking whether an expensive inference branch may run, and explicit coercion needs a shared bypass flag.

**Files it touches:**
- `tree/inference_limits.py` — new module with:
  - `datetime_inference_allowed(text, allow_expensive=False)` — returns `True` if `len(text) <= INFERENCE_MAX_DATETIME_CHARS` or `allow_expensive` is `True`.
  - `affix_inference_allowed(text, allow_expensive=False)` — returns `True` if `len(text) <= INFERENCE_MAX_AFFIX_CHARS` or `allow_expensive` is `True`.
  - `color_inference_allowed(text, allow_expensive=False)` — returns `True` if `len(text) <= INFERENCE_MAX_COLOR_CHARS` or `allow_expensive` is `True`.
  - `base64_syntax_valid(text)` — returns `True` if `len(text) % 4 == 0` and the text matches the base64 alphabet regex `^[A-Za-z0-9+/]*={0,2}$`. No bypass flag: this is a content validation, not a length gate.
  - `format_preview_decode_allowed(byte_count)` — returns `True` if `byte_count <= FORMAT_PREVIEW_DECODE_LIMIT_BYTES`. No bypass flag.
- `tests/test_inference_limits.py` — new tests for boundary lengths at exactly the limit and one character/byte above the limit.

**Expected behavior:** For the three `*_inference_allowed` helpers, `allow_expensive=True` returns `True` regardless of text length. `base64_syntax_valid` and `format_preview_decode_allowed` do not have a bypass because they protect content validation or repeated display work.

**Acceptance criteria:**
- The helper module imports only `settings` and standard-library modules.
- Boundary tests cover allowed-at-limit and rejected-above-limit for every length-gated helper.
- `base64_syntax_valid` tests cover: valid base64 at various sizes, invalid length (not mod 4), invalid characters (whitespace, special chars), empty string.
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

**Problem it solves:** Oversized near-affix strings must not run `_CURRENCY_RE.fullmatch` or `_UNITS_RE.fullmatch` during automatic inference. The gate must fire **before** the pre-existing 4300-digit integer limit so automatic inference never reaches the error path.

**Files it touches:**
- [`units/number_affix.py`](../units/number_affix.py:79) — add `allow_expensive=False` to [`parse_number_affix()`](../units/number_affix.py:79) and return `None` before regex work when `affix_inference_allowed(text, allow_expensive)` is `False`.
- Call sites in [`io_formats/load.py`](../io_formats/load.py:41), [`tree/types.py`](../tree/types.py:125), and [`tree/item_coercion.py`](../tree/item_coercion.py:1) — pass the correct flag for inference versus explicit coercion.
- Existing affix tests in [`tests/test_io_number_affix.py`](../tests/test_io_number_affix.py:1) plus a new oversized-inference test.

**Expected behavior:** A near-affix string longer than `INFERENCE_MAX_AFFIX_CHARS` returns `None` during inference before regex matching. Existing valid affix strings at or below the limit keep their current parse result.

**Acceptance criteria:**
- Spy test proves neither affix regex is called for oversized inference input.
- Spy test proves the gate fires before the pre-existing 4300-digit integer limit; the error path ("Exceeds the limit (4300 digits) for integer string") is not reached for automatic inference.
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

### Commit 1.7 — Gate base64, zlib, and gzip inference probes with syntax validation
- [ ] Completed

**Problem it solves:** Non-base64 strings must not allocate decoded buffers or attempt zlib/gzip decompression during automatic inference. The gate uses content-based syntax validation (length mod 4 + alphabet regex) instead of a length cap, so valid large base64 payloads are still decoded.

**Files it touches:**
- [`tree/types.py`](../tree/types.py:32) — refactor `_looks_like_base64(text)` to use `base64_syntax_valid(text)` from `tree/inference_limits.py` as the cheap pre-check before `base64.b64decode`. The existing `_B64_RE` regex already enforces the base64 alphabet; the refactor extracts the `len % 4` and regex checks into the shared helper.
- [`tree/types.py`](../tree/types.py:185) — the base64 decode, zlib decompress, and gzip decompress branches are only reached when `base64_syntax_valid(text)` returns `True`. No length cap is applied; if the syntax is valid, decoding proceeds.
- [`tree/item_coercion.py`](../tree/item_coercion.py:1) and [`tree/codecs/bytes_codec.py`](../tree/codecs/bytes_codec.py:8) — explicit binary coercion uses the same `base64_syntax_valid` check (no bypass needed since it's content validation, not a length gate).
- Existing BYTES/ZLIB/GZIP tests plus a new test proving that a large valid base64 string is still classified correctly.

**Expected behavior:** A string that fails `base64_syntax_valid` (wrong length mod 4 or invalid alphabet characters) classifies as `STRING`, `UNICODE`, or `TEXT` without calling `base64.b64decode`, zlib decompress, or gzip decompress. A large valid base64 string (e.g., 1MB) is still decoded and classified as `BYTES`/`ZLIB`/`GZIP` correctly.

**Acceptance criteria:**
- Spy test proves `base64.b64decode`, `zlib.decompress`, and `gzip.decompress` are not called for strings that fail syntax validation.
- Large valid base64 fixture (e.g., 1MB) is correctly classified as `BYTES`.
- Valid BYTES/ZLIB/GZIP fixtures keep current inferred types.
- Mandatory gate passes.

### Commit 1.8 — Cap paint-time binary preview decode
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

### Commit 1.9 — Regression sweep against Plan 0 harness
- [ ] Completed

**Problem it solves:** The gates must eliminate the vulnerabilities measured in Plan 0 under automatic inference, while preserving explicit conversion behavior.

**Files it touches:**
- `tests/perf/` — rerun Plan 0 perf tests against the gated implementation.
- `reports/parsing-vulnerability-<YYYY-MM-DD>.md` — append a before/after section with the same row schema used by Plan 0.
- This threshold table — update any value changed by the before/after run and cite the row that justifies it.

**Expected behavior:** Automatic inference rows for target functions are no longer classified as `superlinear` or `allocation_exceeded`. Rows for explicit conversion tests show the target parser/converter was reached.

**Acceptance criteria:**
- Plan 0 opt-in report contains before/after rows for every original vulnerable function.
- The before/after report shows that the 4 `parse_number_affix`/`parse_json_type` `near_affix` error rows from the original report are eliminated for automatic inference paths.
- The before/after report shows that the 141 `superlinear` rows from the original report are reduced to 0 for automatic inference paths (explicit-coercion rows are not affected).
- No automatic-inference row remains `superlinear` or `allocation_exceeded` after gates.
- Full test suite and mandatory gate pass.

## Out of scope (deferred to follow-up plans)

The following concerns are flagged by the review report and the parsing-vulnerability data but are **not** addressed by Plan 1:

1. **Double classification of strings**: [`_decode_number_affixes()`](../io_formats/load.py:41) and [`JsonTreeItem.__init__()`](../tree/item.py:37) both call [`parse_json_type()`](../tree/types.py:125). A follow-up plan should introduce either a cheaper affix-only predicate or a parse-metadata object to avoid repeated full inference.
2. **Cooperative cancellation during load**: The GUI thread remains blocked during parse and model build. Plan 2 (progress dialog) and Plan 3 (cancel button) address the user-visible side; the underlying cooperative-checkpoint work is not part of Plan 1.
3. **Atomic reload cancellation**: [`DiffApplier.apply()`](undo/diff.py:13) is in-place and not safe to interrupt mid-recursion. This is a Plan 3 concern.
4. **Extended-size perf runs**: Plan 0's acceptance criteria mention extended sizes (262144, 1048576, 10485710) that are not present in the current `reports/parsing-vulnerability-2026-06-13.md`. A follow-up should run and document those sizes before Plan 1 Commit 1.9 runs its regression sweep.
