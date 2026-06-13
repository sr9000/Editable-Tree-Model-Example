"""Factory helpers for creating document tabs."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtWidgets import QWidget

from documents.composition.dependencies import JsonTabServices
from documents.seams.document_protocol import Document
from documents.tab import JsonTab
from themes.icon_provider import IconProvider
from themes.spec import ThemeSpec
from tree.model import JsonTreeModel


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
    prebuilt_model: JsonTreeModel | None = None,
    defer_validation_init: bool = False,
) -> Document:
    """Construct a :class:`JsonTab` and expose it as :class:`Document`."""
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
            prebuilt_model=prebuilt_model,
            defer_validation_init=defer_validation_init,
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
        prebuilt_model=prebuilt_model,
        defer_validation_init=defer_validation_init,
    )


__all__ = ["create_tab"]
