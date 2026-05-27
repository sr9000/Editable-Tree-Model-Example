# Class-aware stale-method rescan

Date: 2026-05-27

## Methodology fix

The previous scan trusted Vulture too much for methods. Vulture is mostly name-based, so a module-level function call can mask a same-named class method. The concrete failure was:

- `delegates/editor_factory.py:378` calls the free function `_category_for_json_type(...)`.
- `delegates/editor_factory.py:441` defines that free function.
- `delegates/value.py:229` defines `ValueDelegate._category_for_json_type(...)`.
- There are no `self._category_for_json_type`, `delegate._category_for_json_type`, or `ValueDelegate._category_for_json_type` references.

The revised scan parses ASTs and treats class methods as used only when it sees method-style attribute references (`self.x`, `cls.x`, `ClassName.x`, or unknown `.x`). Direct `Name` references no longer count as method usage.

## Confirmed miss from previous report

| Symbol                                  |                 Location | Evidence                                                                                                            |
|-----------------------------------------|-------------------------:|---------------------------------------------------------------------------------------------------------------------|
| `ValueDelegate._category_for_json_type` | `delegates/value.py:229` | `0` method-style refs; `1` direct-name ref, which is the replacement free function in `delegates/editor_factory.py` |

## Focused strong no-method-reference candidates

Filtered to remove dunder methods, obvious callbacks, and property shims. These have `0` method-style references across production + tests.

| Symbol                                        |                     Location | Size | Notes                                                      |
|-----------------------------------------------|-----------------------------:|-----:|------------------------------------------------------------|
| ❌ `FontController.unsubscribe`                | `app/font_controller.py:129` |  `2` |                                                            |
| ✅ `MainWindow._rebuild_theme_menu_entries`    |     `app/main_window.py:327` |  `2` |                                                            |
| ✅ `MainWindow._refresh_theme_menu_checks`     |     `app/main_window.py:330` |  `2` |                                                            |
| ✅ `MainWindow._open_themes_folder`            |     `app/main_window.py:339` |  `2` |                                                            |
| ✅ `MainWindow._refresh_theme_watcher_paths`   |     `app/main_window.py:342` |  `2` |                                                            |
| ✅ `MainWindow._reload_themes_from_disk`       |     `app/main_window.py:348` |  `2` |                                                            |
| ✅ `MainWindow.insert_column`                  |     `app/main_window.py:529` |  `2` |                                                            |
| ✅ `MainWindow.remove_column`                  |     `app/main_window.py:556` | `13` |                                                            |
| ✅ `MainWindow.copy_action`                    |     `app/main_window.py:643` |  `9` |                                                            |
| `ValueDelegate._category_for_json_type`       |     `delegates/value.py:229` | `14` | missed by Vulture because same-named free function is used |
| `JsonTab.zoom_reset`                          |       `documents/tab.py:593` |  `4` |                                                            |
| `JsonTab._size_hint_for_item`                 |       `documents/tab.py:741` |  `2` |                                                            |
| `JsonTab._clear_children`                     |       `documents/tab.py:890` |  `2` |                                                            |
| `JsonTab._convert_container`                  |       `documents/tab.py:893` |  `8` |                                                            |
| `JsonTab._convert_to_leaf`                    |       `documents/tab.py:902` |  `2` |                                                            |
| `JsonTab._diff_object`                        |       `documents/tab.py:915` |  `2` |                                                            |
| `JsonTab._diff_array`                         |       `documents/tab.py:918` |  `2` |                                                            |
| `StreamingJSONEncoderWrapper._get_indent_str` |   `jsontream/__init__.py:78` |  `5` |                                                            |

## Callback-shaped no-method-reference candidates

These may be stale, but callback names can be wired dynamically; verify signal connections before deleting.

| Symbol                                       |                 Location | Size |
|----------------------------------------------|-------------------------:|-----:|
| `MainWindow._on_tab_validation_changed`      | `app/main_window.py:243` |  `2` |
| `MainWindow._on_validation_issue_activated`  | `app/main_window.py:248` |  `2` |
| `MainWindow._on_system_color_scheme_changed` | `app/main_window.py:351` |  `2` |

## Property/public API review bucket

No method-style refs, but deletion depends on whether these are compatibility shims or public API.

| Symbol                        |                 Location | Size | Flags      |
|-------------------------------|-------------------------:|-----:|------------|
| `MainWindow._MAX_CLOSED_TABS` | `app/main_window.py:375` |  `2` | `property` |

## Ignored as expected false positives

Dunder/protocol methods with no explicit calls are expected in Python/Qt and were excluded from the focused list:

- `_StrongRef.__call__` at `app/font_controller.py:222`
- `_coalesce.__getitem__` at `coalesce/__init__.py:2`
- `EditResult.__bool__` at `delegates/edit_context.py:41`
- `Chunks.__getitem__` at `qhexedit/chunks.py:233`
- `TypeStyle.__hash__` at `themes/spec.py:26`
- `ValidationStyle.__hash__` at `themes/spec.py:39`
- `Palette.__hash__` at `themes/spec.py:61`
- `ThemeSpec.__hash__` at `themes/spec.py:84`
