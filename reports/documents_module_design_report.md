# Design Evaluation Report: The `documents` Module

**Overall Score:** 3 / 10 (Poorly Designed / Duct-Taped Monolith)

This report provides a verbose, in-depth evaluation of the `documents` module within the `Editable-Tree-Model-Example` project. The evaluation focuses on circular dependencies, static typing violations, responsibility separation (Single Responsibility Principle - SRP), and leaking abstractions.

---

## 1. Circular Dependencies (Semantic & Structural)

While the module manages to avoid strict Python `ImportError` cycles at runtime, it suffers from severe semantic circular dependencies. The architecture presents a web of objects that are intimately aware of each other's internals.

### The `tab_protocols.py` Anti-Pattern
To avoid literal circular imports between the monolithic `JsonTab` class and its extracted action files (like `tab_commands.py` and `tab_tree_actions.py`), the developers introduced `tab_protocols.py`. However, instead of designing true independent interfaces, they created "fake" protocols that mirror the God-object's highly specific methods.
*   Protocols such as `TabCommandsProtocol` and `TabBootstrapProtocol` require the implementer to expose private functions like `_capture_move_view_state`, `_proxy_to_source`, and `_index_from_path`.
*   This creates a semantic loop: The `JsonTab` depends on the commands module for its logic, but the commands module dictates the exact internal signature of the `JsonTab` God-object.

### Controller/Facade Cycles
The `JsonTabDataFacade` acts as a proxy, forwarding properties down to underlying controllers. For instance, `self.file_path` is forwarded to `self.io.file_path`. However, those same underlying controllers (e.g., in `tab_history.py` and `tab_appearance.py`) maintain cyclic back-references to the root `tab` or its internal `data_store` to manipulate state. They rely heavily on `self._tab.data_store.view` to function, creating a tight two-way coupling.

---

## 2. Static Types Violations and Type Safety

Type hinting in this module gives a false sense of security. Static typing is regularly bypassed, severely undermining the utility of Python's type system.

### God References and Missing Annotations
In several peripheral files, variables points back to the `JsonTab` God-object but lack proper type annotations:
*   In `tab_history.py` (`def __init__(self, tab)`) and `tab_status.py` (`def on_current_changed(tab, current, ...)`), the `tab` instance is passed around completely dynamically. This relies strictly on implicit duck-typing, throwing type safety out the window and making refactoring perilous.

### Widespread Abuse of `Any`
Within `tab_protocols.py`, which is supposed to define the type boundaries, crucial properties are masked as `Any`:
*   The `data_store: Any` property appears in almost every protocol. This is catastrophic because `data_store` holds the core application state (models, views, delegates, proxies). By typing it as `Any`, any static analyzer (like MyPy) is blinded to the operations performed on the state bag across boundaries.
*   Methods like `push_move_rows(self, sources: list, ...)` fail to declare the internal generic types (`list[QModelIndex]`).

---

## 3. Responsibility Separation (SRP Violations)

The architecture exhibits the "Code Chunking" anti-pattern. Instead of structurally isolating domains into independent robust classes, a massive class was simply chopped into multiple files.

### The Global Mutable State Bag
`JsonTabData` (augmented by `JsonTabDataFacade`) functions as a dumping ground for disparate mutable states. It houses everything from the UI instances (`ui`, `view`, `search_edit`) to models (`model`, `proxy`) and specific rendering instructions (`name_delegate`, `value_delegate`). Modules requesting structural changes end up interacting with UI presentation logic because everything is stuffed into `data_store`.

### The God Object Router
At over 400 lines, `tab.py`'s `JsonTab` remains a quintessential God Object. It exists almost entirely as a giant routing board, exposing over 60 delegated methods, including `apply_filter`, `zoom_in`, `push_remove_rows`, and `set_read_only`. A class that manages undo buffers, UI zooming, file I/O statuses, and JSON data type conversions simultaneously does not adhere to the Single Responsibility Principle.

---

## 4. Leaking Abstractions

The boundaries between UI presentation, application tracking, and the core domain are practically non-existent.

### The Testing Layer: Orchestrating the Matrix of Tests
A review of the test suite (via grep over `tests/`) highlights exactly how tightly coupled testing is to the `JsonTab` internal `data_store` implementation. Tests do not evaluate outputs purely; they mimic end-user interactions by scripting deep UI properties.

While tests *are allowed* to break architectural boundaries to establish thorough regression checks, their deep hooks into the `tab.data_store` object mean that a naive ground-up redesign would result in a terrifying cascade of 1000+ broken tests simultaneously.

To make refactoring achievable, the test paths must be acknowledged. Tests generally fall into the following logical clusters based on their core dependencies:

1. **Core Data Structure & I/O Tests**
   (*e.g., `test_tree_correctness.py`, `test_io_*.py`, `test_jsontream.py`, `test_file_io_phase4.py`*)
   These tests validate serialization, chunking, and JSON compliance. They are the closest to the domain.
2. **Undo/Redo History & Macro Tests**
   (*e.g., `test_undo_*.py`, `test_typed_undo_commands.py`, `test_tab_history_controller.py`, `test_phase_5_1_carryover.py`*)
   These rely precisely on `tab.data_store.undo_stack` command counts, boundary pushes, and macro collapsing logic.
3. **Structural Mutations & Actions**
   (*e.g., `test_drag_drop_*.py`, `test_keyboard_multimove*.py`, `test_context_menu_*.py`, `test_anchor_move.py`*)
   These tests simulate end-user tree reorganization, often calling manual Qt keyboard events to test sorting, case-switching, and node moves.
4. **Validation Logic & Presentation**
   (*e.g., `test_validation_*.py`, `test_schema_*.py`*)
   These inspect UI state for severity roles, tooltip metadata, and the `tab.data_store.issue_index` state logic upon model changes.
5. **Delegates, Editors, & Embellishments**
   (*e.g., `test_type_editing.py`, `test_number_affix*.py`, `test_secret_*.py`, `test_datetime_*.py`*)
   These strictly evaluate visual styling, `QLineEdit`/`QComboBox` popups, and formatting logic.
6. **Application Lifecycle & Persistence**
   (*e.g., `test_tab_lifecycle.py`, `test_phase_5_4_persisted_view_state.py`, `test_smoke_mainwindow.py`*)
   High-level behaviors managing window operations, settings persistence, and tab pools.

### The Omnipresent Data Store Leaking Throughout the App
Grep analysis across the entire application boundary (ignoring tests) reveals that `tab.data_store` is pervasively leaked and mutated by files far removed from the `documents` internal logic, creating an incredibly tight coupling between application layers.
*   **Window Management (`app/main_window.py`, `app/main_window_actions.py`)** explicitly checks and mutates things like `tab.data_store.is_read_only`, `tab.data_store.is_dirty`, and `tab.data_store.undo_stack.clear()`.
*   **Menu and App Actions (`tree_actions/context_menu.py`, `tree_actions/structure.py`, `tree_actions/paste.py`)** heavily depend on it, invoking macros (`tab.data_store.mutations.begin_macro`) and manipulating the UI view (`tab.data_store.search_edit.text()`).
*   **Application State Modules (`state/view_state.py`)** reach past the Facade entirely, extracting `tab.data_store.model.columnCount()` and manipulating `tab.data_store._user_sized_columns.update()`.
*   **Undo Architecture (`undo/commands.py`, `undo/diff.py`)** explicitly modifies presentation modes via `self._tab.data_store.view.setCurrentIndex()`, breaking typical boundary limitations where an undo command only alters data.

This indicates that `JsonTab` does not function as an isolated document component, but acts as a global mutable singleton interface for the rest of the application ecosystem.

### Qt Leaking into Business Logic
The `tab_commands.py` file dictates complex domain logic (like sorting JSON keys, switching field cases, or renaming attributes). However, its signatures are thoroughly contaminated with Qt's MVC abstractions. Business/Command logic continuously expects and mutates `QModelIndex`, `QPersistentModelIndex`, and even evaluates `Qt.ItemDataRole`s. The domain logic cannot be tested or run without spinning up a full Qt UI application.

### Internal State Contamination
Commands in `tab_commands.py` explicitly jump the boundary and mutate internal caching mechanisms directly. For example, `push_move_rows_anchor` modifies private dictionaries and lists inside the global state directly:
```python
tab.data_store._move_view_state_by_cmd_id[id(cmd)] = move_view_state
tab.data_store._last_move_placed = cmd.placed_paths
```
A command object mutating internal cache trackers of its instigator reveals a total breakdown of encapsulation.

### Private Member Exposure
Methods intended strictly for internal management—marked with underscores like `_apply_move_view_state`, `_proxy_to_source`, and `_index_from_path`—are codified into public protocols (`tab_protocols.py`) to be called from other distinct files. This completely invalidates the concept of internal encapsulation.

---

## Conclusion & Recommendations

The `documents` module structure is the resulting side-effect of fracturing a massive God-object class into smaller text files without performing actual architectural decomposition. 

**Steps to Remediate:**
1. **Remove `tab_protocols.py`:** Stop masking the cyclical design. Instead, utilize actual Dependency Injection where a command is given explicit data structures (not the UI elements) rather than passing the `tab` backward.
2. **Untangle Domain from UI:** Decouple commands from `QModelIndex`. Move logic onto pure Python structures and use Qt's signals/slots to react and update the views accordingly.
3. **Decompose `JsonTabData`:** Break the payload into distinct conceptual data structures: a purely textual/tree mutation pipeline, a separate viewport controller, and an I/O payload controller.
4. **Discrete Test-Driven Refactoring Path:** Refactor sequentially matching the test clusters outlined above to maintain isolated test stability:
   * **Phase 1:** Decouple **Core Data & I/O**. Ensure JSON parsing and tree assertions only apply against isolated model structures, not tab UI views.
   * **Phase 2:** Refactor the **Undo/Redo** boundary. Redesign commands to emit logical Signals rather than explicitly forcing UI viewport cursor updates (`setCurrentIndex`), satisfying history tests before addressing UI dependencies.
   * **Phase 3:** Extract **Tree Mutations** (Drag/Drop/Move). Reroute the `tree_actions` commands through the unified pure domain model, leaving tests untouched except for adapting the caller signatures.
   * **Phase 4:** Stabilize **UI/Validation Views**. Connect view layers and validation docks purely via Signals propagating from the new detached tab controllers.
5. **Command Independence:** Ensure `undo/commands.py` does not reference UI instances like `tab.data_store.view`. Selection restoration should be handled via a Signal returning the mutation metrics, handled purely by the View Controller.
6. **Isolate Feature Layers:** The `main_window` should talk to an abstract `Document` interface exposing signals and events, entirely ignorant of underlying `search_edit` inputs or specific validation dictionaries inside `data_store`.
