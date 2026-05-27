from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol, runtime_checkable

from themes import LIGHT_DEFAULT
from themes.icon_provider import IconProvider, StubIconProvider
from themes.spec import ThemeSpec

StatusMessageCallback = Callable[[str, int], None]
PermanentMessageCallback = Callable[[str], None]
RefreshActionsCallback = Callable[[], None]


@runtime_checkable
class JsonTabHost(Protocol):
    def refresh_actions(self) -> None: ...

    def show_status_message(self, message: str, timeout_ms: int = 0) -> None: ...

    def show_permanent_message(self, message: str) -> None: ...


class NullJsonTabHost:
    def refresh_actions(self) -> None:
        pass

    def show_status_message(self, message: str, timeout_ms: int = 0) -> None:
        _ = (message, timeout_ms)

    def show_permanent_message(self, message: str) -> None:
        _ = message


class CallbackJsonTabHost:
    def __init__(
        self,
        *,
        refresh_actions: RefreshActionsCallback | None = None,
        show_status_message: StatusMessageCallback | None = None,
        show_permanent_message: PermanentMessageCallback | None = None,
    ) -> None:
        self._refresh_actions = refresh_actions
        self._show_status_message = show_status_message
        self._show_permanent_message = show_permanent_message

    def refresh_actions(self) -> None:
        if self._refresh_actions is not None:
            self._refresh_actions()

    def show_status_message(self, message: str, timeout_ms: int = 0) -> None:
        if self._show_status_message is not None:
            self._show_status_message(message, timeout_ms)

    def show_permanent_message(self, message: str) -> None:
        if self._show_permanent_message is not None:
            self._show_permanent_message(message)


@dataclass(frozen=True, slots=True)
class JsonTabServices:
    host: JsonTabHost = field(default_factory=NullJsonTabHost)
    theme: ThemeSpec = LIGHT_DEFAULT
    icon_provider: IconProvider = field(default_factory=StubIconProvider)


def build_legacy_json_tab_services(
    *,
    update_actions_callback: RefreshActionsCallback | None = None,
    status_message_callback: StatusMessageCallback | None = None,
    permanent_message_callback: PermanentMessageCallback | None = None,
    theme: ThemeSpec | None = None,
    icon_provider: IconProvider | None = None,
) -> JsonTabServices:
    return JsonTabServices(
        host=CallbackJsonTabHost(
            refresh_actions=update_actions_callback,
            show_status_message=status_message_callback,
            show_permanent_message=permanent_message_callback,
        ),
        theme=theme or LIGHT_DEFAULT,
        icon_provider=icon_provider or StubIconProvider(),
    )
