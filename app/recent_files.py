from pathlib import Path


def recent_files(window) -> list[str]:
    return window._settings.value("recent_files", [], type=list)


def push_recent(window, path: str) -> None:
    resolved = str(Path(path).resolve())
    recent = [resolved] + [p for p in recent_files(window) if p != resolved]
    window._settings.setValue("recent_files", recent[:8])
    refresh_recent_menu(window)


def refresh_recent_menu(window) -> None:
    window._recent_menu.clear()
    for path in recent_files(window):
        if not Path(path).exists():
            continue
        action = window._recent_menu.addAction(path)
        action.triggered.connect(lambda _checked=False, p=path: window._open_path(p))
    window._recent_menu.setEnabled(bool(window._recent_menu.actions()))
