"""Factory for constructing :class:`documents.tab.JsonTab` widgets.

External callers (``app/``) construct tabs through this factory so they
do not need to import the concrete ``JsonTab`` class. The factory's
return type is :class:`documents.document_protocol.Document` -- the
narrow façade declared in Phase K1 of
``plans/21-promote-substates-to-controllers.md``.

The pre-commit guard ``.githooks/_check_jsontab_import_leaks.sh``
(installed by Plan 21 Phase K4) forbids ``from documents.tab import``
outside ``documents/``; this factory is the single legitimate route.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtWidgets import QWidget

from documents.document_protocol import Document
from documents.tab import JsonTab
from documents.tab_dependencies import JsonTabServices
from themes.icon_provider import IconProvider
from themes.spec import ThemeSpec


def create_tab(
    *,
    update_actions_callback: Callable[[], None] | None = None,
    status_message_callback: Callable[[str, int], None] | None = None,
    data: Any = None,
    file_path: str | None = None,
    show_root: bool = False,
    parent: QWidget | None = None,
    permanent_message_callback: Callable[[str], None] | None = None,
    theme: ThemeSpec | None = None,
    icon_provider: IconProvider | None = None,
    save_format: str | None = None,
    services: JsonTabServices | None = None,
) -> Document:
    """Construct a JSON tab widget and return it typed as :class:`Document`.

    Thin wrapper around :class:`documents.tab.JsonTab`'s constructor.
    ``data`` defaults to ``None`` here so callers don't need to know
    about the concrete tab's ``_DEFAULT_DATA`` sentinel; the wrapper
    forwards the constructor's own default when ``data is None``.
    """
    if data is None:
        return JsonTab(
            update_actions_callback=update_actions_callback,
            status_message_callback=status_message_callback,
            file_path=file_path,
            show_root=show_root,
            parent=parent,
            permanent_message_callback=permanent_message_callback,
            theme=theme,
            icon_provider=icon_provider,
            save_format=save_format,
            services=services,
        )

    return JsonTab(
        update_actions_callback=update_actions_callback,
        status_message_callback=status_message_callback,
        data=data,
        file_path=file_path,
        show_root=show_root,
        parent=parent,
        permanent_message_callback=permanent_message_callback,
        theme=theme,
        icon_provider=icon_provider,
        save_format=save_format,
        services=services,
    )


__all__ = ["create_tab"]
