# Big-file loading, string parsing limits, and real cancellation review

_Date: 2026-06-13. Scope: current code paths for opening, reloading, parsing, model construction, progress UI, and cancellation._

## Executive findings

- Opening and reloading are currently synchronous on the GUI thread. [`MainWindow._open_path()`](app/main_window.py:303) calls [`load_file_with_format()`](io_formats/load.py:64), then [`MainWindow._add_tab()`](app/main_window.py:297), then [`TabLifecyclePresenter.add_tab()`](app/tab_lifecycle.py:64), then [`create_tab()`](documents/composition/factory.py:16), then [`JsonTab.__init__()`](documents/tab.py:53), then [`bootstrap()`](documents/composition/init.py:34), then [`init_model()`](documents/composition/setup.py:108), then [`JsonTreeModel.__init__()`](tree/model.py:25), then recursive [`JsonTreeItem.__init__()`](tree/item.py:37) and [`JsonTreeItem._apply_typed_value()`](tree/item.py:253).
- Parsing is split into two broad phases, but not into cancellable phases: file text is parsed into Python data by [`load_file_with_format()`](io_formats/load.py:64), and the Qt model/tree is built later by [`init_model()`](documents/composition/setup.py:108). UI binding occurs immediately after model construction via [`TreeFilterProxy.setSourceModel()`](documents/composition/setup.py:113) and [`QTreeView.setModel()`](documents/composition/setup.py:116). There is no background worker, progress object, cancellation token, or event-loop yielding between these calls.
- Reload is different from initial open: [`MainWindow._reload_tab_from_path()`](app/main_window.py:362) loads Python data, then recursively mutates the existing tree through [`DiffApplier.apply()`](undo/diff.py:13) rather than rebuilding a whole tab. This keeps view state better, but cancellation after diff starts is currently impossible without adding cooperative checkpoints or changing reload to an atomic build-then-swap strategy.
- Existing large-value limits protect only manual editor opening. [`STRING_EDIT_WARNING_LIMIT_CHARS`](settings.py:8), [`MULTILINE_EDIT_WARNING_LIMIT_CHARS`](settings.py:9), and binary limits are consumed by [`create_value_editor()`](editors/factory.py:83) through [`DefaultEditContext.confirm_large_text_edit()`](delegates/edit_context.py:129) and [`DefaultEditContext.confirm_large_binary_edit()`](delegates/edit_context.py:149). They do not protect file loading, type inference, schema discovery, model construction, validation, display formatting, or search.
- The main crash/performance risk is repeated expensive string inference. [`_decode_number_affixes()`](io_formats/load.py:41) calls [`parse_json_type()`](tree/types.py:125) for every string during load, then every [`JsonTreeItem.__init__()`](tree/item.py:37) calls [`parse_json_type()`](tree/types.py:125) again during model construction. String inference can perform full-string scans, regex checks, date parsing, number-affix parsing, base64 decoding, and zlib/gzip decompression in [`parse_json_type()`](tree/types.py:151).
- There is no current implementation of loading progress or real cancellation. Repository search found no loading use of [`QThread`](app/main_window.py:5), [`QRunnable`](app/main_window.py:5), [`QProgressDialog`](app/main_window.py:5), or cooperative cancellation primitives. The status message set by [`MainWindow._open_path()`](app/main_window.py:305) can be visually delayed because the GUI thread immediately enters blocking parse/model work.

## Current open and reload flow

| Stage | Initial open | Reload from disk | Planning implication |
|---|---|---|---|
| User entry | [`open_file_dialog()`](app/main_window.py:389), [`dropEvent()`](app/main_window.py:185), [`setup_model()`](app/main_window.py:239), [`Schema open`](app/validation_presenter.py:180) | [`reload_from_disk()`](app/main_window.py:412) | All entry points converge on [`MainWindow._open_path()`](app/main_window.py:303) or [`MainWindow._reload_tab_from_path()`](app/main_window.py:362), so a loading coordinator can start there. |
| File parse | [`load_file_with_format()`](io_formats/load.py:64) | [`load_file_with_format()`](io_formats/load.py:64) | Parser currently returns only after full parse and number-affix postprocess. |
| Number-affix pass | [`_decode_number_affixes()`](io_formats/load.py:41) | [`_decode_number_affixes()`](io_formats/load.py:41) | This pass is recursive and calls [`parse_json_type()`](tree/types.py:125), so it is a prime place for string length guards and progress/cancel checks. |
| Model/tree build | [`JsonTreeModel.__init__()`](tree/model.py:25) | Existing model is changed by [`DiffApplier.apply()`](undo/diff.py:13) | Initial open builds a new item tree; reload mutates an old item tree. The plan must handle both paths explicitly. |
| UI bind | [`init_model()`](documents/composition/setup.py:108), [`init_delegates_and_connections()`](documents/composition/setup.py:125) | Existing view remains bound | Initial open can cancel before adding a tab. Reload must preserve old tab until successful completion. |
| Validation/schema | [`TabValidationController.init_state()`](documents/controllers/validation.py:84), [`discover_schema()`](validation/schema_source.py:89), [`TabValidationController.revalidate()`](documents/controllers/validation.py:145) | [`tab.validation.revalidate()`](app/main_window.py:380) | Validation can add noticeable work after model build and can call file/schema loading through [`load_schema()`](validation/schema_source.py:76). |
| Recent files/status | [`push_recent()`](app/main_window.py:316) after tab add | Status update after reload | Cancellation should not call [`push_recent()`](app/main_window.py:316), should not add tabs, and should leave dirty state unchanged. |

## Expensive parsing and string-length guard hotspots

### High-priority guard locations

1. [`parse_json_type()`](tree/types.py:125) is the central inference function. For strings, it currently checks text shape, color regexes, datetime parsing, affix parsing, base64 decode, zlib decompress, gzip decompress, then text fallback at [`tree/types.py:151`](tree/types.py:151). Add cheap length-based gates before expensive calls.
2. [`parse_datetime_text()`](core/datetime_parsing/regex.py:36) uses [`DATETIME_RE.fullmatch()`](core/datetime_parsing/regex.py:37), then can call pandas timestamp construction through [`to_timestamp()`](core/datetime_parsing/compat.py:19). The regex is anchored and narrow, but a length guard should short-circuit obviously non-date giant strings before regex and pandas work.
3. [`parse_number_affix()`](units/number_affix.py:79) has an affix length validator, but both regexes still scan the input first. Add total string length prechecks before [`_CURRENCY_RE.fullmatch()`](units/number_affix.py:80) and [`_UNITS_RE.fullmatch()`](units/number_affix.py:92).
4. [`_looks_like_base64()`](tree/types.py:32) currently requires length divisible by four, regex, then base64 decode. Very large base64-like strings can allocate large decoded bytes at [`base64.b64decode()`](tree/types.py:45), then [`parse_json_type()`](tree/types.py:125) decodes again at [`tree/types.py:186`](tree/types.py:186), then tries decompression at [`tree/types.py:189`](tree/types.py:189) and [`tree/types.py:195`](tree/types.py:195). Add a maximum inference length or a separate binary probe limit.
5. [`compute_editable()`](tree/item_coercion.py:578) decodes and decompresses binary strings to decide editability. This is called by [`JsonTreeItem._apply_typed_value()`](tree/item.py:253), so it can run during load for every binary-like node. It should respect a safe decode/decompress cap or rely on already-known safe metadata.
6. [`format_with_type()`](delegates/formatting/value_formatting.py:132) decodes bytes for display at [`decode_bytes()`](delegates/formatting/value_formatting.py:167). This can occur during painting after load and should avoid large decompression on every paint.
7. [`TreeFilterProxy.filterAcceptsRow()`](tree/filter_proxy.py:23) converts leaf values to strings and casefolds them at [`tree/filter_proxy.py:44`](tree/filter_proxy.py:44). This is not part of open, but can become a post-load problem for giant values.

### Double-classification concern

[`_decode_number_affixes()`](io_formats/load.py:41) calls [`parse_json_type()`](tree/types.py:125) to decide whether a string should become [`NumberAffix`](units/number_affix.py:21). Later [`JsonTreeItem.__init__()`](tree/item.py:37) calls [`parse_json_type()`](tree/types.py:125) again on the same value. If a giant string is not an affix, it still pays both costs. A real plan should consider either a cheaper affix-only predicate for [`_decode_number_affixes()`](io_formats/load.py:41), or a parse metadata object that avoids repeated full inference.

## Cancellability assessment

### What can be cancelled today

- User can cancel the file picker before loading through [`QFileDialog.getOpenFileName()`](app/main_window.py:390).
- User can cancel dirty reload confirmation through [`_confirm_reload_dirty_tab()`](app/main_window.py:338).
- User can cancel manual large-value editors through [`create_value_editor()`](editors/factory.py:83), [`DefaultEditContext.confirm_large_text_edit()`](delegates/edit_context.py:129), and [`DefaultEditContext.confirm_large_binary_edit()`](delegates/edit_context.py:149).

### What cannot be cancelled today

- After [`MainWindow._open_path()`](app/main_window.py:303) calls [`load_file_with_format()`](io_formats/load.py:64), the GUI thread is blocked until file parsing and recursive affix decoding finish.
- After [`TabLifecyclePresenter.add_tab()`](app/tab_lifecycle.py:64) calls [`create_tab()`](documents/composition/factory.py:16), model construction and tab bootstrapping run synchronously until [`bootstrap()`](documents/composition/init.py:34) completes.
- After [`MainWindow._reload_tab_from_path()`](app/main_window.py:362) calls [`DiffApplier.apply()`](undo/diff.py:13), the existing tab may be partially mutated if cancellation were naively added mid-diff.
- JSON parsing through [`simplejson.load()`](io_formats/load.py:69) and YAML parsing through [`yaml.load_all()`](io_formats/load.py:79) are not cooperative. A cancel button cannot interrupt those calls directly unless parsing is moved out of the GUI thread and the app discards the result, or a separate process is used when hard termination is required.

### Practical meaning of REALLY cancel

For a future plan, define real cancellation as:

- Initial open: no tab is added, no recent-file entry is pushed, and no validation/schema state is registered if cancellation occurs before commit. This is straightforward if [`push_recent()`](app/main_window.py:316) remains after successful tab creation.
- Reload: existing tab data, dirty state, undo stack, validation state, and view state remain unchanged if cancellation occurs before atomic commit. Current [`DiffApplier.apply()`](undo/diff.py:13) is not atomic under cancellation, so reload needs either build-then-swap or a cancellable diff with rollback.
- File parser in background: cancellation stops UI waiting and prevents result commit. If hard CPU/IO termination is required while parser is inside [`simplejson.load()`](io_formats/load.py:69) or [`yaml.load_all()`](io_formats/load.py:79), use a worker process rather than only a [`QThread`](app/main_window.py:5).

## Progress UI assessment

- Triggering a progress dialog after five seconds fits a delayed-timer pattern: start a timer in a loading coordinator, show dialog only if the task is still active, and hide it on finish/cancel/error.
- Because current loading blocks the GUI thread, a five-second delayed dialog cannot appear unless parse/model work is moved to a worker or broken into event-loop-yielding chunks.
- Progress granularity is not currently available from [`load_file_with_format()`](io_formats/load.py:64), [`JsonTreeItem._apply_typed_value()`](tree/item.py:253), or [`DiffApplier.apply()`](undo/diff.py:13). A plan should introduce a small progress/cancel protocol and report coarse stages first: reading, parsing, decoding affixes, building item tree, binding UI, validation.
- The current status-bar messages in [`MainWindow._open_path()`](app/main_window.py:305) and [`MainWindow._reload_tab_from_path()`](app/main_window.py:364) are useful as fallback status, but not enough for long blocking work.

## Modules and symbols likely involved in implementation

| Area | Involved code | Why it matters |
|---|---|---|
| App-level open/reload orchestration | [`MainWindow._open_path()`](app/main_window.py:303), [`MainWindow._reload_tab_from_path()`](app/main_window.py:362), [`open_file_dialog()`](app/main_window.py:389), [`dropEvent()`](app/main_window.py:185), [`setup_model()`](app/main_window.py:239) | Best insertion point for a loading coordinator, progress dialog, result commit, cancellation semantics, recent-file behavior, and status messages. |
| Tab creation | [`TabLifecyclePresenter.add_tab()`](app/tab_lifecycle.py:64), [`create_tab()`](documents/composition/factory.py:16), [`JsonTab.__init__()`](documents/tab.py:53), [`bootstrap()`](documents/composition/init.py:34) | Current construction is synchronous and all-or-nothing only by exception. A future plan may need a prebuilt tree/model input or separate loading state. |
| Model setup | [`init_model()`](documents/composition/setup.py:108), [`JsonTreeModel.__init__()`](tree/model.py:25), [`JsonTreeItem.__init__()`](tree/item.py:37), [`JsonTreeItem._apply_typed_value()`](tree/item.py:253) | This is where Python data becomes tree items and where recursive inference happens. |
| File parsing | [`load_file_with_format()`](io_formats/load.py:64), [`_decode_number_affixes()`](io_formats/load.py:41), [`detect_format()`](io_formats/detect.py:1) | Needs cancellable/progress-aware API or a wrapper that safely runs it off-thread/off-process. |
| Type inference | [`parse_json_type()`](tree/types.py:125), [`_looks_like_base64()`](tree/types.py:32), [`parse_datetime_text()`](core/datetime_parsing/regex.py:36), [`parse_number_affix()`](units/number_affix.py:79) | Main location for length guards and cheaper string classification. |
| Binary handling | [`decode_bytes()`](tree/codecs/bytes_codec.py:8), [`compute_editable()`](tree/item_coercion.py:578), [`format_with_type()`](delegates/formatting/value_formatting.py:132), [`create_value_editor()`](editors/factory.py:83) | Avoid repeated full decode/decompress during load, paint, and editability checks. |
| Reload mutation | [`DiffApplier.apply()`](undo/diff.py:13), [`DiffApplier.diff_object()`](undo/diff.py:110), [`DiffApplier.diff_array()`](undo/diff.py:139) | Existing reload updates in place. Cancellation must not leave partial mutations. |
| Validation and schema | [`TabValidationController.init_state()`](documents/controllers/validation.py:84), [`TabValidationController.revalidate()`](documents/controllers/validation.py:145), [`discover_schema()`](validation/schema_source.py:89), [`load_schema()`](validation/schema_source.py:76), [`SchemaRegistry.acquire()`](validation/schema_registry.py:50) | These can add post-load work and can load schema files. Decide whether loading progress includes schema and validation. |
| Existing limits/settings | [`settings.py`](settings.py:1), [`state/edit_limits.py`](state/edit_limits.py:1), [`DefaultEditContext`](delegates/edit_context.py:81) | Current limits are UI edit warnings; new load/inference limits may need separate settings or constants. |
| Existing tests | [`tests/test_file_io_phase4.py`](tests/test_file_io_phase4.py:43), [`tests/test_reload_from_disk.py`](tests/test_reload_from_disk.py:48), [`tests/test_phase_5_1_carryover.py`](tests/test_phase_5_1_carryover.py:121), [`tests/test_smoke_mainwindow.py`](tests/test_smoke_mainwindow.py:1) | Good places to extend coverage for open/reload cancellation, string guard behavior, and no-regression of large editor warnings. |

## Suggested planning direction

1. Add safe string inference caps first in [`parse_json_type()`](tree/types.py:125), [`parse_datetime_text()`](core/datetime_parsing/regex.py:36), [`parse_number_affix()`](units/number_affix.py:79), [`compute_editable()`](tree/item_coercion.py:578), and [`format_with_type()`](delegates/formatting/value_formatting.py:132). This directly reduces crash risk even before async loading exists.
2. Introduce a load-result coordinator around [`MainWindow._open_path()`](app/main_window.py:303) and [`MainWindow._reload_tab_from_path()`](app/main_window.py:362). Keep commit points explicit: initial open commits by adding a tab; reload commits only after a complete, successful, non-cancelled load.
3. Use a delayed progress dialog or equivalent delayed widget controlled by the coordinator. The five-second trigger must be timer-based and can only work if the load is off the GUI thread or chunked.
4. Decide worker strategy before implementation:
   - A [`QThread`](app/main_window.py:5) worker is simpler and can keep UI responsive, but cannot forcibly stop a blocked parser; cancellation discards late results.
   - A worker process is heavier but closer to hard cancellation for parser crashes or runaway C/Python work.
   - Chunked cooperative model building on the GUI thread can support cancellation during item creation, but does not solve blocking parser calls.
5. Treat reload as atomic. Prefer building a new root item tree or new model off to the side, then swap/apply only after success. If preserving view state is mandatory, either capture/restore view state around swap or make [`DiffApplier.apply()`](undo/diff.py:13) cancellable only before mutation boundaries with rollback.
6. Add tests that assert cancellation has no side effects: no tab added, no recent push, old reload data preserved, dirty state preserved, no schema registration leaks, and late worker results are ignored after cancel.

## Open questions for the real plan

- Should load-time string caps be fixed constants in [`settings.py`](settings.py:1), persisted settings like [`state/edit_limits.py`](state/edit_limits.py:1), or hard safety limits not exposed in UI?
- Does REALLY cancel require killing in-progress parser CPU work, or is responsive UI cancellation plus ignored late results acceptable for the first implementation?
- Should the five-second progress bar include validation/schema discovery after model build, or only file parse and model build?
- For reload, is preserving current minimal-diff behavior more important than simpler atomic swap semantics?

## Fast index summary

- Current split: file parse in [`io_formats/load.py`](io_formats/load.py:1), model/tree build in [`tree/model.py`](tree/model.py:25) and [`tree/item.py`](tree/item.py:37), UI binding in [`documents/composition/setup.py`](documents/composition/setup.py:108), validation in [`documents/controllers/validation.py`](documents/controllers/validation.py:84).
- Current blocker: everything is called synchronously from [`app/main_window.py`](app/main_window.py:303).
- Highest-risk expensive functions: [`parse_json_type()`](tree/types.py:125), [`parse_datetime_text()`](core/datetime_parsing/regex.py:36), [`parse_number_affix()`](units/number_affix.py:79), [`decode_bytes()`](tree/codecs/bytes_codec.py:8), [`compute_editable()`](tree/item_coercion.py:578), [`format_with_type()`](delegates/formatting/value_formatting.py:132).
- Existing cancellation precedent: manual large editor warnings in [`editors/factory.py`](editors/factory.py:83) and [`delegates/edit_context.py`](delegates/edit_context.py:129), not file loading.
- Most important implementation risk: reload through [`DiffApplier.apply()`](undo/diff.py:13) is in-place and not safe to interrupt mid-recursion.
