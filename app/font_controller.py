"""Aspect-oriented font management.

Centralizes the application's font state (regular family, monospace family,
editor point size, monospace-fields toggle) in a single ``FontController``.
Widgets that need to react to font changes register themselves once and the
controller broadcasts an immutable ``FontProfile`` to every subscriber on
each change. This keeps font wiring out of ``MainWindow`` book-keeping and
out of ad-hoc per-call-site updates.

Subscriber protocol:

* If the subscriber exposes ``apply_font_profile(profile)``, it is called.
* Otherwise, if it has ``setFont`` (any ``QWidget``), the controller pushes
  the profile's *regular* font onto it.

A subscriber is notified once at registration time so it picks up the
current profile without the caller having to remember.
"""

from __future__ import annotations

import weakref
from dataclasses import dataclass, replace
from typing import Protocol, runtime_checkable

from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QWidget

_MIN_PT = 6
_MAX_PT = 48


@dataclass(frozen=True)
class FontProfile:
    """Immutable snapshot of the user's font preferences."""

    regular_family: str  # "" means "use the application default family"
    monospace_family: str
    editor_point_size: int
    monospace_fields_enabled: bool

    def regular_font(self, *, base: QFont | None = None) -> QFont:
        font = QFont(base) if base is not None else QFont()
        if self.regular_family:
            font.setFamily(self.regular_family)
        font.setPointSize(self.editor_point_size)
        return font

    def monospace_font(self, *, base: QFont | None = None) -> QFont:
        font = QFont(base) if base is not None else QFont()
        font.setFamily(self.monospace_family)
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setFixedPitch(True)
        font.setPointSize(self.editor_point_size)
        return font


@runtime_checkable
class FontProfileAware(Protocol):
    def apply_font_profile(self, profile: FontProfile) -> None: ...  # pragma: no cover


class FontController(QObject):
    """Single source of truth for app-wide font preferences.

    Owns persistence (``QSettings``), broadcasting and the policy methods
    (``zoom_in``/``set_regular_family``/...). Callers mutate state through
    these methods only — never by poking subscribers directly.
    """

    profileChanged = Signal(object)  # FontProfile

    _SETTINGS_REGULAR = "view/regular_font_family"
    _SETTINGS_MONOSPACE = "view/monospace_font_family"
    _SETTINGS_POINT_SIZE = "view/editor_font_point_size"
    _SETTINGS_MONO_FIELDS = "view/monospace_fields"

    def __init__(self, settings: QSettings, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = settings

        app_pt = QApplication.font().pointSize()
        self._default_point_size = int(app_pt) if app_pt and app_pt > 0 else 10

        sys_mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()

        self._profile = FontProfile(
            regular_family=str(settings.value(self._SETTINGS_REGULAR, "", type=str) or ""),
            monospace_family=str(settings.value(self._SETTINGS_MONOSPACE, sys_mono, type=str) or sys_mono),
            editor_point_size=self._clamp_pt(
                settings.value(self._SETTINGS_POINT_SIZE, self._default_point_size, type=int)
                or self._default_point_size
            ),
            monospace_fields_enabled=bool(settings.value(self._SETTINGS_MONO_FIELDS, False, type=bool)),
        )

        # Use a list of callables (``weakref.ref`` or ``_StrongRef``) so
        # deleted Qt objects drop out automatically without us having to
        # track close events.
        self._subscribers: list = []

    # -- public read access -------------------------------------------------

    @property
    def profile(self) -> FontProfile:
        return self._profile

    @property
    def default_point_size(self) -> int:
        return self._default_point_size

    # -- subscription -------------------------------------------------------

    def subscribe(self, target: object) -> None:
        """Register *target* to receive the current and all future profiles."""
        try:
            ref = weakref.ref(target)
        except TypeError:
            # Object does not support weak references; fall back to strong.
            ref = _StrongRef(target)
        # Avoid duplicate registration.
        if any(r() is target for r in self._subscribers):
            self._notify_one(target)
            return
        self._subscribers.append(ref)
        self._notify_one(target)

    def unsubscribe(self, target: object) -> None:
        self._subscribers = [r for r in self._subscribers if r() is not None and r() is not target]

    # -- mutators -----------------------------------------------------------

    def set_regular_family(self, family: str) -> None:
        family = (family or "").strip()
        if not family:
            return
        self._update(regular_family=family)

    def set_monospace_family(self, family: str) -> None:
        family = (family or "").strip()
        if not family:
            return
        self._update(monospace_family=family)

    def set_point_size(self, point_size: int) -> None:
        self._update(editor_point_size=self._clamp_pt(int(point_size)))

    def set_monospace_fields_enabled(self, enabled: bool) -> None:
        self._update(monospace_fields_enabled=bool(enabled))

    def zoom_in(self) -> None:
        self.set_point_size(self._profile.editor_point_size + 1)

    def zoom_out(self) -> None:
        self.set_point_size(self._profile.editor_point_size - 1)

    def reset_zoom(self) -> None:
        self.set_point_size(self._default_point_size)

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _clamp_pt(pt: int) -> int:
        return max(_MIN_PT, min(_MAX_PT, int(pt)))

    def _update(self, **changes) -> None:
        new_profile = replace(self._profile, **changes)
        if new_profile == self._profile:
            return
        self._profile = new_profile
        self._persist()
        self._broadcast()

    def _persist(self) -> None:
        s = self._settings
        s.setValue(self._SETTINGS_REGULAR, self._profile.regular_family)
        s.setValue(self._SETTINGS_MONOSPACE, self._profile.monospace_family)
        s.setValue(self._SETTINGS_POINT_SIZE, self._profile.editor_point_size)
        s.setValue(self._SETTINGS_MONO_FIELDS, self._profile.monospace_fields_enabled)

    def _broadcast(self) -> None:
        live: list = []
        for ref in self._subscribers:
            target = ref()
            if target is None:
                continue
            live.append(ref)
            self._notify_one(target)
        self._subscribers = live
        self.profileChanged.emit(self._profile)

    def _notify_one(self, target: object) -> None:
        if isinstance(target, FontProfileAware):
            try:
                target.apply_font_profile(self._profile)
            except RuntimeError:
                # Underlying C++ object was deleted between scheduling and now.
                pass
            return
        if isinstance(target, QWidget):
            try:
                target.setFont(self._profile.regular_font(base=target.font()))
            except RuntimeError:
                pass


class _StrongRef:
    """Tiny shim so ``self._subscribers`` is uniformly callable.

    Used as a fallback for objects that cannot be weakly referenced — rare
    in Qt land but cheap to support so the controller never raises.
    """

    __slots__ = ("_target",)

    def __init__(self, target: object) -> None:
        self._target = target

    def __call__(self) -> object | None:
        return self._target
