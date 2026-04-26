# Phase 5.3 — Status bar breadcrumb

> **Status (2026-04-26): ✅ done** — `JsonTab` accepts a
> `permanent_message_callback`; `_on_current_changed` builds a JSON-style
> qualified path with type + size hint. Open / Save / tree actions emit
> transient messages via `_status_message_callback`.

## Goal

Give the user always-on context about what they have selected, plus
transient feedback for long-running actions.

## Entry criteria

- Phase 5.1 merged.
- Status callback plumbing already in place
  (`JsonTab._status_message_callback` exists; `MainWindow` passes
  `self.statusBar.showMessage`).

## Exit criteria

- Selecting a node writes a permanent status-bar breadcrumb of the
  form `$.foo.bar[2].baz  (string, 24 chars)` and clears when nothing
  is selected.
- Open / Save / Sort / Paste / Cut / Delete each produce a transient
  status message (≤ 2 s).

## Work items

### Permanent breadcrumb channel
- [ ] [tab] Add a second callback parameter
      `permanent_message_callback: Callable[[str], None] | None` to
      `JsonTab.__init__` (defaults to `None`); store on `self`.
      — `json_tab.py:JsonTab.__init__`
- [ ] [shell] In `MainWindow._add_tab`, pass
      `permanent_message_callback=self.statusBar.showMessage` with
      `timeout=0` semantics — i.e. wrap as
      `lambda msg: self.statusBar.showMessage(msg, 0)`.
      — `ui.py:MainWindow._add_tab`
- [ ] [tab] Connect `view.selectionModel().currentChanged` to a new
      `JsonTab._on_current_changed(self, current, previous)` that:
      - returns early when `current` is invalid → call permanent
        callback with `""`.
      - else builds `breadcrumb = self._qualified_name(current)`,
        plus `(json_type, size_hint)` where `size_hint` is e.g.
        `f"{len(value)} chars"` for strings, `f"{count} items"` for
        OBJECT/ARRAY, `f"{units.bits(len(decoded))}"` for bytes types.
        — `json_tab.py`
- [ ] [tests] New test asserts the permanent callback receives a
      breadcrumb on `setCurrentIndex(...)` and `""` after the
      selection is cleared.

### Transient action feedback
- [ ] [shell] In `MainWindow._open_path`, prepend
      `self.statusBar.showMessage("Loading…", 0)` and replace it on
      success/failure (already partially wired — make sure long YAML
      loads still display the loading message).
      — `ui.py:MainWindow._open_path`
- [ ] [shell] In `MainWindow._save_tab`, show
      `"Saving…"` then `"Saved: <path>"` (already in `JsonTab.save`,
      no change needed beyond verifying the order).
      — `ui.py:MainWindow._save_tab` / `json_tab.py:JsonTab.save`
- [ ] [tab] In `_run_tree_action` ensure every action has a status
      success message. Add for `sort_keys` if missing.
      — `json_tab.py:JsonTab._run_tree_action`

## Risks / notes

- Mixing permanent (`timeout=0`) and transient (`timeout>0`) status
  messages on the same `QStatusBar` is fine — the transient one
  temporarily replaces the permanent one and reverts.
- Avoid emitting a breadcrumb on every `dataChanged` — listen only to
  `currentChanged`.
