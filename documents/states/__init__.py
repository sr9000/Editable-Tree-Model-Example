"""Per-axis substate objects that compose a ``JsonTabData`` document.

Plan 20 Phase I decomposes the former ``JsonTabData`` god-dataclass
into four single-responsibility substates:

* :class:`documents.states.io_state.IoState` -- file_path, save_format, dirty
* :class:`documents.states.view_state.ViewState` -- ui widgets + delegates + proxy
* :class:`documents.states.editing_state.EditingState` -- model, mutations,
  history (undo stack), affix MRU, move-view caches
* :class:`documents.states.validation_state.ValidationState` -- validation
  controller, schema source/ref, issue index

Each substate is a plain Python object owned by ``JsonTabData``.  External
callers should *not* import these directly -- they reach the underlying
data through the typed ``JsonTab`` properties exposed in Phases B-F.
"""
