## `getattr` usage

```bash
grep -Irn --exclude-dir=.venv --exclude-dir=tests -E "getattr"
```

```terminaloutput
themes/registry.py:52:    meipass = getattr(sys, "_MEIPASS", None)
themes/registry.py:64:        fspath = getattr(traversable, "__fspath__", None)
state/view_state.py:72:    if not getattr(tab, "file_path", None):
state/view_state.py:84:    font_pt = int(getattr(tab, "_font_pt", tab.view.font().pointSize() or 10))
state/view_state.py:94:    if not getattr(tab, "file_path", None):
state/affix_mru.py:12:        configured = getattr(settings, "NUMBER_AFFIX_MRU_SIZE", 50)
state/affix_mru.py:40:            if hasattr(node, "value") and isinstance(getattr(node, "value", None), NumberAffix):
state/affix_mru.py:41:                value = getattr(node, "value")
state/affix_mru.py:44:                for child in getattr(node, "child_items", []):
qt2py/__init__.py:11:    tzid = getattr(dt.tzinfo, "key", None) or getattr(dt.tzinfo, "zone", None)
tree_actions/structure.py:217:    callback = getattr(tab, "_status_message_callback", None)
tree_actions/structure.py:223:    callback = getattr(tab, "_status_message_callback", None)
tree_actions/structure.py:337:                placed_total.extend(getattr(tab, "_last_move_placed", []))
tree_actions/structure.py:424:                placed_total.extend(getattr(tab, "_last_move_placed", []))
tree_actions/context_menu.py:88:        trigger = getattr(tab, "edit_name_or_value_from_enter", None)
tree_actions/context_menu.py:134:    cb = getattr(tab, "_status_message_callback", None) if tab is not None else None
tree_actions/context_menu.py:143:    search_edit = getattr(tab, "search_edit", None)
tree_actions/context_menu.py:167:    search_edit = getattr(tab, "search_edit", None)
tree_actions/context_menu.py:173:        apply_filter = getattr(tab, "_apply_filter", None)
tree_actions/dnd.py:89:    if tab is None or getattr(tab, "_status_message_callback", None) is None:
model_actions.py:175:    if not row0.isValid() and getattr(model, "show_root", False):
undo/commands.py:178:        mru = getattr(self._tab, "affix_mru", None)
undo/commands.py:293:        return self._source_names.get(source, getattr(item, "name", None))
app/validation_dock.py:145:                    getattr(self._tab, sig_name).disconnect(
app/validation_dock.py:146:                        getattr(self, f"_on_{sig_name.replace('Changed', '_changed')}")
app/validation_dock.py:189:        has_url = getattr(ref, "url", None) is not None
app/validation_dock.py:226:            self._tab.schema_ref.path is not None or getattr(self._tab.schema_ref, "url", None) is not None
app/theme_controller.py:183:        setter = getattr(style_hints, "setColorScheme", None)
app/font_controller.py:194:        apply = getattr(target, "apply_font_profile", None)
app/font_controller.py:202:        set_font = getattr(target, "setFont", None)
app/font_controller.py:205:                set_font(self._profile.regular_font(base=getattr(target, "font", lambda: None)()))
validation/validator.py:119:        value = getattr(err, attr, None)
validation/validator.py:134:    return getattr(err, "validator", None) in ("oneOf", "anyOf") and bool(getattr(err, "context", None))
validation/validator.py:144:    sp = list(getattr(err, "schema_path", ()) or ())
validation/validator.py:192:        instance_depth = len(list(getattr(err, "path", ()) or ()))
validation/validator.py:193:        schema_depth = len(list(getattr(err, "schema_path", ()) or ()))
validation/validator.py:231:    parent_path = list(getattr(err, "path", ()) or ())
validation/validator.py:232:    parent_schema_path = list(getattr(err, "schema_path", ()) or ())
validation/validator.py:242:    raw_instance_path = getattr(err, "instance_path", None)
validation/validator.py:244:        raw_instance_path = getattr(err, "path", ())
validation/validator.py:246:        message=str(getattr(err, "message", err)),
validation/validator.py:248:        schema_path=_schema_path_resolving_refs(root_schema, getattr(err, "schema_path", ())),
documents/tab.py:135:        view = getattr(self, "view", None)
documents/tab.py:485:            font.setPointSize(max(6, int(getattr(self, "_font_pt", 10) or 10)))
documents/tab.py:615:        if not getattr(self.type_delegate, "_interactive", False):
documents/tab_setup.py:44:        cb = getattr(self._tab, "_status_message_callback", None)
documents/tab_setup.py:53:        return getattr(self._tab, "_icon_provider", None)
documents/tab_setup.py:56:        return getattr(self._tab, "affix_mru", None)
documents/tab_validation.py:37:    return getattr(_tab_module, "schema_registry", _default_registry)
main.py:17:    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
```
