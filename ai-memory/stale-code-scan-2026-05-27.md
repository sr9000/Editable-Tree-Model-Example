# Automated stale-code scan report

Scope: production Python files only, excluding `.venv`, `tests`, `build`, `dist`, `tmp`, `__pycache__`, and `ai-memory`. Tests were also used in a second pass as references.

## Tooling run

- `vulture 2.16` on production files: `182` findings.
- `vulture 2.16` on production + tests: `158` findings.
- `pyflakes` on production files: `44` findings.
- Custom AST/text triage: exact token/attribute/call counts across production and tests; Qt override names tagged as likely false positives.

## Highest-confidence stale code candidates

These were reported by Vulture and had no exact token/call/attribute references outside their own definition file and no test references in the custom pass. Still review public API expectations before deletion.

| Kind | Symbol | Location | Size |
|---|---|---:|---:|
| `method` | `unsubscribe` | `app/font_controller.py:129` | `2` |
| `method` | `_rebuild_theme_menu_entries` | `app/main_window.py:327` | `2` |
| `method` | `_refresh_theme_menu_checks` | `app/main_window.py:330` | `2` |
| `method` | `_open_themes_folder` | `app/main_window.py:339` | `2` |
| `method` | `_refresh_theme_watcher_paths` | `app/main_window.py:342` | `2` |
| `method` | `_reload_themes_from_disk` | `app/main_window.py:348` | `2` |
| `method` | `insert_column` | `app/main_window.py:529` | `2` |
| `method` | `_size_hint_for_item` | `documents/tab.py:741` | `2` |
| `method` | `_clear_children` | `documents/tab.py:890` | `2` |
| `method` | `_convert_to_leaf` | `documents/tab.py:902` | `2` |
| `method` | `_diff_object` | `documents/tab.py:915` | `2` |
| `method` | `_diff_array` | `documents/tab.py:918` | `2` |
| `method` | `isSensitive` | `qmultiline_editor.py:165` | `2` |
| `method` | `secretRevealed` | `qmultiline_editor.py:173` | `2` |
| `function` | `_get_val_str` | `tree_actions/clipboard.py:33` | `2` |
| `class` | `FontProfileAware` | `app/font_controller.py:59` | `3` |
| `property` | `default_point_size` | `app/font_controller.py:109` | `3` |
| `property` | `_MAX_CLOSED_TABS` | `app/main_window.py:374` | `3` |
| `function` | `action_insert_row` | `model_actions.py:49` | `3` |
| `method` | `setFontColor` | `qhexedit/color_manager.py:45` | `3` |
| `method` | `setAreaStyle` | `qhexedit/color_manager.py:61` | `3` |
| `class` | `MultiLineInfo` | `settings.py:48` | `3` |
| `function` | `write_schema_url` | `state/validation_settings.py:56` | `3` |
| `method` | `append_child` | `tree/item.py:57` | `3` |
| `method` | `insert_columns` | `tree/item.py:215` | `3` |
| `method` | `remove_columns` | `tree/item.py:219` | `3` |
| `function` | `paste_insert_zip` | `tree_actions/paste.py:437` | `3` |
| `method` | `zoom_reset` | `documents/tab.py:593` | `4` |
| `method` | `setSecretRevealed` | `qmultiline_editor.py:168` | `4` |
| `method` | `_get_indent_str` | `jsontream/__init__.py:78` | `5` |
| `class` | `IntegerInfo` | `settings.py:33` | `5` |
| `class` | `SingleLineInfo` | `settings.py:53` | `5` |
| `function` | `schema_source_from_ref` | `validation/schema_source.py:20` | `5` |
| `function` | `is_color_text` | `delegates/color_codec.py:71` | `6` |
| `class` | `FloatInfo` | `settings.py:40` | `6` |
| `method` | `acquire_ref` | `validation/schema_registry.py:125` | `6` |
| `method` | `monospace_font` | `app/font_controller.py:50` | `7` |
| `function` | `_int_from_exact` | `tree/item_coercion.py:312` | `7` |
| `method` | `_convert_container` | `documents/tab.py:893` | `8` |
| `function` | `qtdatetime` | `qt2py/__init__.py:7` | `8` |
| `method` | `copy_action` | `app/main_window.py:643` | `9` |
| `function` | `pydatetime` | `qt2py/__init__.py:17` | `11` |
| `method` | `remove_column` | `app/main_window.py:556` | `13` |
| `method` | `setDynamicBytesPerLine` | `qhexedit/__init__.py:328` | `15` |
| `function` | `infer_text_json_type` | `tree/types.py:79` | `18` |
| `function` | `_select_placed_rows` | `undo/commands.py:16` | `20` |
| `function` | `format_hex_dump` | `binary/__init__.py:1` | `48` |
| `class` | `DateTimeEditor` | `datetime_editor/__init__.py:11` | `58` |

## Candidate methods needing API review

Methods with Vulture reports and weak/no attribute references, but not strong enough to auto-delete because names may be interface hooks or factory-called.

| Kind | Symbol | Location | Evidence |
|---|---|---:|---|
| `method` | `set_edit_context` | `delegates/name_delegate.py:32` | `prod_tok=2, prod_attr=0, prod_call=2, test_tok=0, flags=HAS_EXTERNAL_TEXT_REFS` |
| `method` | `set_edit_context` | `delegates/type_delegate.py:68` | `prod_tok=2, prod_attr=0, prod_call=2, test_tok=0, flags=HAS_EXTERNAL_TEXT_REFS` |
| `method` | `set_edit_context` | `delegates/value.py:51` | `prod_tok=2, prod_attr=0, prod_call=2, test_tok=0, flags=HAS_EXTERNAL_TEXT_REFS` |

## Production pyflakes findings

These are usually safer micro-cleanups or actual errors; undefined names deserve attention.

- `app/validation_dock.py:21:1: 'validation.schema_registry.SchemaSource' imported but unused`
- `app/validation_panel_model.py:95:9: local variable 'src_index' is assigned to but never used`
- `delegates/editor_factory.py:200:17: local variable 'icon' is assigned to but never used`
- `documents/tab.py:953:17: undefined name 'MoveAnchor'`
- `documents/tab.py:992:13: local variable 'insert_row' is assigned to but never used`
- `mainwindow.py:11:1: 'PySide6.QtCore.QDate' imported but unused`
- `mainwindow.py:11:1: 'PySide6.QtCore.QDateTime' imported but unused`
- `mainwindow.py:11:1: 'PySide6.QtCore.QLocale' imported but unused`
- `mainwindow.py:11:1: 'PySide6.QtCore.QObject' imported but unused`
- `mainwindow.py:11:1: 'PySide6.QtCore.QPoint' imported but unused`
- `mainwindow.py:11:1: 'PySide6.QtCore.QSize' imported but unused`
- `mainwindow.py:11:1: 'PySide6.QtCore.QTime' imported but unused`
- `mainwindow.py:11:1: 'PySide6.QtCore.QUrl' imported but unused`
- `mainwindow.py:11:1: 'PySide6.QtCore.Qt' imported but unused`
- `mainwindow.py:14:1: 'PySide6.QtGui.QBrush' imported but unused`
- `mainwindow.py:14:1: 'PySide6.QtGui.QColor' imported but unused`
- `mainwindow.py:14:1: 'PySide6.QtGui.QConicalGradient' imported but unused`
- `mainwindow.py:14:1: 'PySide6.QtGui.QCursor' imported but unused`
- `mainwindow.py:14:1: 'PySide6.QtGui.QFont' imported but unused`
- `mainwindow.py:14:1: 'PySide6.QtGui.QFontDatabase' imported but unused`
- `mainwindow.py:14:1: 'PySide6.QtGui.QGradient' imported but unused`
- `mainwindow.py:14:1: 'PySide6.QtGui.QIcon' imported but unused`
- `mainwindow.py:14:1: 'PySide6.QtGui.QImage' imported but unused`
- `mainwindow.py:14:1: 'PySide6.QtGui.QKeySequence' imported but unused`
- `mainwindow.py:14:1: 'PySide6.QtGui.QLinearGradient' imported but unused`
- `mainwindow.py:14:1: 'PySide6.QtGui.QPainter' imported but unused`
- `mainwindow.py:14:1: 'PySide6.QtGui.QPalette' imported but unused`
- `mainwindow.py:14:1: 'PySide6.QtGui.QPixmap' imported but unused`
- `mainwindow.py:14:1: 'PySide6.QtGui.QRadialGradient' imported but unused`
- `mainwindow.py:14:1: 'PySide6.QtGui.QTransform' imported but unused`
- `mainwindow.py:19:1: 'PySide6.QtWidgets.QApplication' imported but unused`
- `mainwindow.py:19:1: 'PySide6.QtWidgets.QMainWindow' imported but unused`
- `mainwindow.py:19:1: 'PySide6.QtWidgets.QSizePolicy' imported but unused`
- `qhexedit/__init__.py:20:1: '.commands.CommandType' imported but unused`
- `tree_actions/anchors.py:208:5: local variable 'n_sources' is assigned to but never used`
- `undo/commands.py:41:29: undefined name 'JsonTab'`
- `undo/commands.py:64:29: undefined name 'JsonTab'`
- `undo/commands.py:106:29: undefined name 'JsonTab'`
- `undo/commands.py:144:14: undefined name 'JsonTab'`
- `undo/commands.py:209:29: undefined name 'JsonTab'`
- `undo/commands.py:235:29: undefined name 'JsonTab'`
- `undo/commands.py:278:14: undefined name 'JsonTab'`
- `undo/commands.py:419:29: undefined name 'JsonTab'`
- `undo/commands.py:440:29: undefined name 'JsonTab'`

## Modules not reached from `main`/`mainwindow` import graph

Import graph reachability is conservative and misses dynamic/manual entry points. Treat this as a stale-module shortlist, not proof of dead code.

- `app/__init__.py: module=app lines=1 external_token_mentions=259`
- `app/validation_dock_actions.py: module=app.validation_dock_actions lines=51 external_token_mentions=2`
- `binary/__init__.py: module=binary lines=48 external_token_mentions=20`
- `delegates/__init__.py: module=delegates lines=1 external_token_mentions=84`
- `header_view_editor.py: module=header_view_editor lines=79 external_token_mentions=0`
- `jsontream/__init__.py: module=jsontream lines=206 external_token_mentions=2`
- `qhexedit/chunks.py: module=qhexedit.chunks lines=285 external_token_mentions=18`
- `qhexedit/color_manager.py: module=qhexedit.color_manager lines=158 external_token_mentions=2`
- `qhexedit/commands.py: module=qhexedit.commands lines=157 external_token_mentions=16`
- `qt2py/__init__.py: module=qt2py lines=27 external_token_mentions=0`
- `themes/_contrast.py: module=themes._contrast lines=21 external_token_mentions=1`
- `themes/builtin/__init__.py: module=themes.builtin lines=1 external_token_mentions=15`
- `tree/__init__.py: module=tree lines=1 external_token_mentions=163`
- `tree_actions/__init__.py: module=tree_actions lines=5 external_token_mentions=109`
- `undo/__init__.py: module=undo lines=1 external_token_mentions=161`

## Likely false positives / keep unless deeper evidence says otherwise

Mostly Qt virtual methods, delegate methods, undo command `mergeWith`, widget public APIs, and code exercised from tests only.

- Qt/PySide virtuals flagged by static analysis include `paintEvent`, `sizeHint`, `dragEnterEvent`, `dropEvent`, `mouseMoveEvent`, `mousePressEvent`, `createEditor`, `displayText`, model drag/drop methods, `insertRows`, `stepBy`, `stepEnabled`, and `mergeWith`.
- Public widget API methods in `qhexedit`, `qbigint_spinbox`, and `qmpq_spinbox` may intentionally be unused internally.
- Test-used-only APIs can be removed only if the tests are obsolete too; examples include several `app/main_window.py` back-compat shims and schema/view-state helpers.
