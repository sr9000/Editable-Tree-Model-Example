# Unsupported raw numeric values design

## Intent derived from current changes

- The current implementation protects the app from unsafe rational conversion by routing loader failures into [`FrozenValue`](core/frozen_value.py:5), preserving raw output with [`mpq_json_default()`](mpq2py/__init__.py:84) and [`_frozen_value_yaml_represent()`](mpq2py/__init__.py:158).
- That implementation intentionally makes those values read-only in [`compute_editable()`](tree/item_coercion.py:573), which now conflicts with the desired behavior: unsupported numeric literals must be editable as raw text.
- The normal numeric path is based on safe Decimal-to-MPQ parsing in [`safe_mpq_from_text()`](core/safe_mpq.py:100), numeric type inference in [`parse_json_type()`](tree/types.py:126), value coercion in [`coerce_value_for_type()`](tree/item_coercion.py:335), numeric editors in [`create_value_editor()`](editors/factory.py:84), and serialization in [`dump_text()`](io_formats/dump.py:33).

## Recommended architecture

Use a dedicated raw numeric wrapper plus a non-user-selectable pseudo type. This is the clean version of the fake frozen-float idea: it keeps raw unsupported numerics distinguishable without pretending they are regular parsed numbers.

### Alternatives considered

1. Keep only the wrapper and continue reporting [`JsonType.FLOAT`](tree/types.py:224).
   - Pro: minimal enum churn.
   - Con: every editor, formatter, validator, and type-change path must special-case value objects under a regular float type; users cannot reliably distinguish raw unsupported floats from normal floats in the type column.
2. Convert unsupported numerics to plain strings on load.
   - Pro: editing and validation are simple.
   - Con: saving quotes the token, numeric identity is lost, and the app can no longer round-trip external numeric literals exactly.
3. Store sidecar metadata keyed by model path.
   - Pro: leaves scalar values primitive.
   - Con: paths change under rename, reorder, drag/drop, paste, and undo; metadata drift is likely.
4. Recommended: evolve [`FrozenValue`](core/frozen_value.py:5) into a raw numeric value object and add a pseudo numeric type near [`JsonType.FLOAT`](tree/types.py:227).
   - Pro: lossless raw text, explicit unsupported state, plain-text editor, safe numeric conversion when possible, and clean serialization boundaries.
   - Con: requires coordinated changes across type inference, editing, internal clipboard codecs, validation sanitization, and theme/type metadata.

## Core decisions

1. Replace or evolve [`FrozenValue`](core/frozen_value.py:5) into [`RawNumericValue`](core/raw_numeric.py:1).
   - Fields: exact raw string, reason, source syntax, and optional detail.
   - Keep a compatibility alias from [`FrozenValue`](core/frozen_value.py:5) to [`RawNumericValue`](core/raw_numeric.py:1) for one transition if useful.
   - Reason values should be stable strings: overflow, underflow, non-finite, invalid-format, precision-limit, parser-rejection, and unknown.
2. Add [`JsonType.RAW_FLOAT`](tree/types.py:224) with a display value such as raw float.
   - It is pseudo-derived, not user-selectable, like the pseudo text types in [`PSEUDO_TEXT_FAMILY`](tree/types.py:311).
   - It belongs to numeric display/grouping logic where helpful, but editor dispatch must treat it separately from [`JsonType.FLOAT`](tree/types.py:227).
   - The type delegate should map it to the canonical parent [`JsonType.FLOAT`](tree/types.py:227) for the combo, but committing that same parent must not coerce unsupported raw text to a stub.
3. Normal numeric values remain regular [`mpq`](core/safe_mpq.py:6) values. Raw numeric values remain [`RawNumericValue`](core/raw_numeric.py:1) until an edit produces a safely parseable value.

## Loading and parsing flow

1. Extend [`core.safe_mpq`](core/safe_mpq.py:1) with a result API that preserves rejection cause instead of returning only [`None`](core/safe_mpq.py:37).
   - Keep [`safe_mpq_from_text()`](core/safe_mpq.py:100) as a compatibility wrapper.
   - New result should distinguish Decimal signals such as overflow and underflow from non-finite input and format rejection.
2. In JSON and JSONL loading, keep using [`simplejson.load()`](io_formats/load.py:89) and [`simplejson.loads()`](io_formats/load.py:96), but route both float tokens and constants through the safe parser.
   - [`_safe_parse_float()`](io_formats/load.py:43) should return [`mpq`](core/safe_mpq.py:6) on success or [`RawNumericValue`](core/raw_numeric.py:1) on parser rejection.
   - Add parse-constant handling for non-standard tokens such as NaN and Infinity when the parser exposes them.
   - Do not attempt recovery from syntactically broken JSON where the parser cannot identify a numeric token boundary; that should remain a controlled load error, not a crash.
3. In YAML loading, update [`mpq_yaml_float_construct()`](mpq2py/__init__.py:113).
   - Do not fall back to native Python float for special values; non-finite values should become [`RawNumericValue`](core/raw_numeric.py:1) so rendering and validation do not depend on Python NaN or infinity behavior.
   - Preserve [`node.value`](mpq2py/__init__.py:113) exactly instead of stripping it.

## Type inference, model state, and coercion

1. Update [`parse_json_type()`](tree/types.py:126) so [`RawNumericValue`](core/raw_numeric.py:1) maps to [`JsonType.RAW_FLOAT`](tree/types.py:224), not [`JsonType.FLOAT`](tree/types.py:227).
2. Update [`USER_SELECTABLE_TYPES`](tree/types.py:332) to exclude [`JsonType.RAW_FLOAT`](tree/types.py:224).
3. Update [`JsonTreeItem._apply_typed_value()`](tree/item.py:253) so applying [`JsonType.FLOAT`](tree/types.py:227) to [`RawNumericValue`](core/raw_numeric.py:1) redirects to [`JsonType.RAW_FLOAT`](tree/types.py:224) rather than storing a raw value under a regular float type.
4. Update [`compute_editable()`](tree/item_coercion.py:573) so raw numeric values are editable.
5. Add raw-numeric edit coercion in [`JsonTreeItem.set_data()`](tree/item.py:129):
   - If current type is [`JsonType.RAW_FLOAT`](tree/types.py:224) and the edit text parses through [`safe_mpq_from_text()`](core/safe_mpq.py:100), store it as normal [`JsonType.FLOAT`](tree/types.py:227) with an [`mpq`](core/safe_mpq.py:6) value.
   - If the edited text equals the original raw text, keep [`RawNumericValue`](core/raw_numeric.py:1) exactly, regardless of whether the narrow edit regex would accept it.
   - If the edited text matches the allowed raw numeric regex but remains unsupported, store a new [`RawNumericValue`](core/raw_numeric.py:1) with the updated reason.
   - If the edited text does not match the allowed raw numeric regex, reject the edit by returning false from [`set_data()`](tree/item.py:129).
6. Update [`coerce_value_for_type()`](tree/item_coercion.py:335) so explicit type changes never silently replace raw unsupported numerics with [`stub_float()`](tree/item_coercion.py:35). Converting raw numeric to text should use the exact raw string; converting to normal float should preserve raw if it is still unsupported.

## Editing UX

1. Add a narrow raw numeric text validator, separate from [`MpqValidator`](editors/inline/mpq_spinbox/validator.py:33).
   - Proposed accepted edit shape: optional sign, decimal digits with optional fractional part, optional exponent with a bounded number of exponent digits, plus a small explicit set of non-finite spellings if the app chooses to preserve them.
   - The regex is intentionally not a full float grammar. It is only the recovery/edit grammar for raw unsupported numerics.
   - Unchanged original raw text is allowed even if it was accepted by the loader but is outside the edit regex.
2. Update [`create_value_editor()`](editors/factory.py:84) so [`JsonType.RAW_FLOAT`](tree/types.py:224) uses a plain line editor, not [`QMpqSpinBox`](editors/inline/mpq_spinbox/spinbox.py:12).
3. Add a warning seam to [`DelegateEditContext`](delegates/edit_context.py:45), for example a raw numeric edit warning method.
   - [`DefaultEditContext`](delegates/edit_context.py:81) should show a modal warning with [`QMessageBox.warning`](delegates/edit_context.py:140).
   - Production context should use the same message and be test-spyable.
4. Warning text must include:
   - the raw value is unsupported as a regular float or number;
   - the known cause when available;
   - the user may change it into a normally parseable numeric value;
   - the user may leave it unchanged to preserve data for external software that accepts it.
5. Show the warning once per editor session, when the raw numeric editor is opened. Do not warn on every keystroke.

## Formatting, tooltips, and distinct presentation

1. Update [`format_default()`](delegates/formatting/value_formatting.py:62) and [`display_role_value()`](tree/model_roles.py:43) to display [`RawNumericValue.raw`](core/raw_numeric.py:1) exactly.
2. Update [`tooltip_role_for_value()`](tree/model_roles.py:26) to include the unsupported numeric warning and reason for raw numeric values.
3. Add default theme styling for [`JsonType.RAW_FLOAT`](tree/types.py:224) in [`themes/_defaults.py`](themes/_defaults.py:55) and [`themes/_defaults.py`](themes/_defaults.py:85), preferably inheriting float coloring with warning-like italic or foreground.
4. Update theme loading keys in [`themes/loader.py`](themes/loader.py:17) so custom themes can style raw float explicitly.

## Saving and internal serialization

1. Keep same-format file round-trip exact.
   - JSON and JSONL dumping should emit raw JSON-compatible numeric tokens through [`mpq_json_default()`](mpq2py/__init__.py:84).
   - YAML dumping should emit raw numeric scalars through [`_frozen_value_yaml_represent()`](mpq2py/__init__.py:158), renamed for [`RawNumericValue`](core/raw_numeric.py:1).
2. Add target-format checks before raw injection.
   - A raw token loaded from YAML may not be a valid app-supported JSON raw token.
   - Cross-format save should fail with a controlled error or require an explicit conversion, rather than silently quoting the value or emitting invalid JSON.
   - The IO controller must report that error without crashing the app.
3. Add an app-native internal value codec for clipboard and drag/drop metadata.
   - Current [`build_tree_mime()`](tree_actions/clipboard.py:179) serializes metadata as JSON and [`entries_from_mime()`](tree_actions/clipboard.py:205) decodes it with the standard JSON parser, which can lose raw numeric wrappers.
   - Metadata should encode [`RawNumericValue`](core/raw_numeric.py:1) as a tagged object, then decode it back before inserting into the model.
   - Human-readable clipboard text can still be the raw scalar literal.

## Validation behavior

1. Update [`to_jsonschema_input()`](validation/_sanitize.py:23) so [`RawNumericValue`](core/raw_numeric.py:1) becomes its raw string for schema validation.
   - This prevents validator crashes and causes schemas expecting number to report a normal type mismatch.
   - The original model value remains unchanged.
2. Validation badges from [`VALIDATION_SEVERITY_ROLE`](tree/model_roles.py:13) should remain schema-driven; raw numeric unsupported state should be communicated by type, tooltip, and edit warning unless a schema also rejects it.

## Test plan

1. Core parser tests in [`tests/test_safe_mpq.py`](tests/test_safe_mpq.py:1): accepted safe values, overflow, underflow, non-finite constants, invalid format, precision-limit, and parser-rejection reasons.
2. Loader and saver tests in [`tests/test_mpq_overflow_protection.py`](tests/test_mpq_overflow_protection.py:1): JSON, JSONL, and YAML raw unsupported numeric values round-trip exactly without constructing unsafe [`mpq`](core/safe_mpq.py:6) values.
3. Model tests: raw numeric values infer [`JsonType.RAW_FLOAT`](tree/types.py:224), are editable, remain distinguishable from regular [`JsonType.FLOAT`](tree/types.py:227), and convert to normal float after a safe edit.
4. Editor tests: [`create_value_editor()`](editors/factory.py:84) returns a text editor for raw numeric values, not [`QMpqSpinBox`](editors/inline/mpq_spinbox/spinbox.py:12); warning context is called once per edit session; invalid regex edits are rejected.
5. Serialization tests: [`dump_text()`](io_formats/dump.py:33), [`build_tree_mime()`](tree_actions/clipboard.py:179), and [`entries_from_mime()`](tree_actions/clipboard.py:205) preserve tagged raw numeric values in app-internal paths.
6. Validation tests: [`to_jsonschema_input()`](validation/_sanitize.py:23) converts raw numeric values to strings and schema validation reports normal issues without crashing.
7. Regression update: change the current read-only assertion in [`test_frozen_float_is_not_inline_editable()`](tests/test_mpq_overflow_protection.py:37) to assert raw numeric values are editable through the raw text path.

## Implementation order

1. Introduce [`RawNumericValue`](core/raw_numeric.py:1), parser result reasons, and compatibility wrappers in [`core.safe_mpq`](core/safe_mpq.py:1).
2. Add [`JsonType.RAW_FLOAT`](tree/types.py:224), inference, pseudo-type exclusion, formatting, tooltip, and theme defaults.
3. Update JSON, JSONL, and YAML loaders and dumpers.
4. Update model editability and raw numeric edit coercion.
5. Add raw numeric line editor validation and warning context.
6. Add internal clipboard and drag/drop metadata encoding.
7. Update validation sanitization.
8. Add and adjust focused tests, then run the full test suite.

## Key risk

The largest risk is silent data loss at boundaries that serialize through ordinary JSON, especially current clipboard metadata. Treat file IO and internal app metadata separately: files preserve raw scalar syntax for external compatibility; internal metadata should use tagged objects so the model can reconstruct [`RawNumericValue`](core/raw_numeric.py:1) exactly.
