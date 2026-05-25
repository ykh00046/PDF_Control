# Design: ui.py Monolith Refactoring

> **Feature**: ui-refactor
> **Plan**: `docs/01-plan/features/ui-refactor.plan.md`
> **Status**: Design

---

## 1. Architectural Pattern

**Builder helpers + Handler mixins.**

- **Builders** (`MenuBuilder`, `ToolbarBuilder`) are stateless one-shot
  helpers: `Builder(window).build()` mutates the passed `MainWindow` by
  attaching `QAction` / widget attributes. They do not need to be kept alive.
- **Manager** (`StatusBarManager`) is a *stateful* helper kept as a member of
  `MainWindow` because the status bar needs ongoing updates
  (`refresh_warning_indicator`, `update_page_info`, etc.).
- **Mixins** (`FileHandlerMixin`, `EditHandlerMixin`, `DialogHandlerMixin`,
  `StateUpdateMixin`) supply method implementations to `MainWindow` through
  Python multiple inheritance. This is the *only* approach that preserves the
  existing `main_window.delete_selection()` call surface used by all 5 import
  sites.

### Why mixins (not delegation)?

| Concern                         | Mixin                              | Delegation `self.handlers.X()` |
|---------------------------------|------------------------------------|--------------------------------|
| Test compatibility              | ✅ `mw.delete_selection()` works   | ❌ rewrite tests required      |
| Signal `connect(self.method)`   | ✅ unchanged                       | ❌ `self.handlers.method`      |
| Access to `self.controller`, `self.viewer`, `self.config` | ✅ direct | ⚠️ `self._win.controller` (uglier) |
| `closeEvent`/`dragEnterEvent` overrides | ✅ natural Qt pattern         | ❌ must override in MainWindow |

Mixins win on every axis here.

---

## 2. File Layout

```
app/
├── ui.py                  # 200 lines - MainWindow class
├── ui_menu.py             # MenuBuilder + ShortcutBuilder
├── ui_toolbar.py          # ToolbarBuilder
├── ui_statusbar.py        # StatusBarManager
└── ui_handlers.py         # 4 mixins (file/edit/dialog/state)
```

All new files live in `app/` to stay alongside `crop_dialog.py`,
`batch_replace_dialog.py`, etc. — matching the existing convention.

---

## 3. Module APIs

### 3.1 `ui_statusbar.py`

```python
class StatusBarManager:
    def __init__(self, window: "MainWindow") -> None: ...

    # Build (called once from MainWindow.__init__)
    def build(self) -> None:
        """Creates the status bar widgets and attaches to window.statusBar()."""

    # Runtime updates (called by handlers + viewer signals)
    def refresh_warning_indicator(self) -> None: ...
    def show_warning_details(self) -> None: ...
    def update_page_info(self) -> None: ...
    def update_font_info(self) -> None: ...
```

**Owned widgets** (stored on `self`, not on window):
- `self._font_info: QLabel`
- `self._warning_indicator: QToolButton`
- `self._page_info: QLabel`

MainWindow accesses them only via the manager's public methods.

### 3.2 `ui_menu.py`

```python
class MenuBuilder:
    def __init__(self, window: "MainWindow") -> None: ...
    def build(self) -> None:
        """Builds menu bar; attaches QActions to window as window.undo_action, etc."""

class ShortcutBuilder:
    def __init__(self, window: "MainWindow") -> None: ...
    def build(self) -> None:
        """Registers Del / Ctrl+R / PageUp/Down / F1 shortcuts."""
```

**Actions attached to window** (preserving existing attribute names):
- `window.undo_action`, `window.redo_action`
- `window.zoom_in_action`, `window.zoom_out_action`, `window.fit_to_width_action`
- `window.toggle_history_action`

### 3.3 `ui_toolbar.py`

```python
class ToolbarBuilder:
    def __init__(self, window: "MainWindow") -> None: ...
    def build(self) -> None:
        """Builds edit + zoom toolbars; reuses undo/redo/zoom actions from MenuBuilder."""
```

**Pre-condition**: `MenuBuilder.build()` must run first (so `undo_action` etc. exist).
**Actions attached to window**:
- `window.delete_action`, `window.replace_action`
- `window.prev_page_action`, `window.next_page_action`
- `window.page_spinbox`

### 3.4 `ui_handlers.py`

Four mixin classes, all inherit from `object` only:

```python
class FileHandlerMixin:
    """Open, save, drag-drop, close."""
    def open_file(self) -> None: ...
    def save_file_as(self) -> bool: ...
    def closeEvent(self, event) -> None: ...
    def dragEnterEvent(self, event) -> None: ...
    def dropEvent(self, event) -> None: ...

class EditHandlerMixin:
    """Undo/redo, delete, replace selection."""
    def undo_operation(self) -> None: ...
    def redo_operation(self) -> None: ...
    def delete_selection(self) -> None: ...
    def replace_selection(self) -> None: ...
    def _snap_selection_to_text(self, page, rect): ...
    def _prompt_replacement_text(self, existing_text): ...
    def _resolve_replacement_font(self, replacement_text=""): ...
    def select_replacement_font(self) -> None: ...

class DialogHandlerMixin:
    """Open child dialogs and apply their results."""
    def open_batch_replace_dialog(self) -> None: ...
    def process_batch_replacements(self, replacements) -> None: ...
    def open_crop_dialog(self) -> None: ...
    def apply_crop(self, crop_settings) -> None: ...
    def open_remove_section_dialog(self) -> None: ...
    def apply_remove_section(self, settings) -> None: ...
    def open_page_manager_dialog(self) -> None: ...
    def _on_pages_changed(self) -> None: ...
    def view_logs(self) -> None: ...
    def show_help(self) -> None: ...

class StateUpdateMixin:
    """React to controller / viewer signals; refresh derived UI state."""
    def on_document_loaded(self, file_path: str) -> None: ...
    def on_document_closed(self) -> None: ...
    def on_operation_applied(self) -> None: ...
    def on_error_occurred(self, message: str) -> None: ...
    def handle_selection_made(self, pdf_rect) -> None: ...
    def _handle_page_changed(self, page_index: int) -> None: ...
    def _on_warnings_changed(self) -> None: ...
    def _update_history_panel(self) -> None: ...
    def _update_edit_action_states(self) -> None: ...
    def _toggle_history_panel(self, checked: bool) -> None: ...
    def _on_page_spinbox_changed(self, value: int) -> None: ...
    def _get_operation_display_name(self, op) -> str: ...
```

### 3.5 `ui.py` (refactored)

```python
from PySide6.QtWidgets import QMainWindow, ...
from app.ui_menu import MenuBuilder, ShortcutBuilder
from app.ui_toolbar import ToolbarBuilder
from app.ui_statusbar import StatusBarManager
from app.ui_handlers import (
    FileHandlerMixin, EditHandlerMixin,
    DialogHandlerMixin, StateUpdateMixin,
)

class MainWindow(
    QMainWindow,
    FileHandlerMixin,
    EditHandlerMixin,
    DialogHandlerMixin,
    StateUpdateMixin,
):
    def __init__(self):
        super().__init__()
        # init logger, config, i18n, controller, viewer, last_selected_rect
        # _setup_dock_widgets()
        self.statusbar_manager = StatusBarManager(self)
        MenuBuilder(self).build()
        ToolbarBuilder(self).build()
        self.statusbar_manager.build()
        ShortcutBuilder(self).build()
        self._apply_styles()
        self.setAcceptDrops(True)

    def _setup_dock_widgets(self): ...   # dock-only, stays
    def _apply_styles(self): ...          # stylesheet, stays
```

---

## 4. MRO / Inheritance Order

```
MainWindow
  ├── QMainWindow              ← Qt base (must be FIRST for Qt to work)
  ├── FileHandlerMixin
  ├── EditHandlerMixin
  ├── DialogHandlerMixin
  └── StateUpdateMixin
```

**Why this order**: Qt requires `QMainWindow` as the primary base for proper
meta-class behavior (`QObject` metaclass conflict avoidance). Mixins follow
and never override Qt methods *except* `closeEvent`, `dragEnterEvent`,
`dropEvent` — which are designed for override.

**Mixin discipline**:
- No `__init__` in mixins (avoids cooperative-super complexity)
- No state in mixins (all state already on MainWindow)
- No mixin-to-mixin method calls (only via `self`)
- Type-hint `self` as `"MainWindow"` under `TYPE_CHECKING` for IDE support

---

## 5. Compatibility Surface

| External caller            | Calls                                          | Preserved? |
|----------------------------|------------------------------------------------|:----------:|
| `main.py:3`                | `from app.ui import MainWindow`                | ✅          |
| `tests/test_ui.py:9`       | `MainWindow()`, `.delete_selection()` etc.     | ✅          |
| `tests/test_regressions.py`| `mw.undo_action`, `mw.replace_action` …        | ✅          |
| `tests/test_async.py`      | `MainWindow()`, signals                        | ✅          |
| `tests/test_viewer_crash.py`| `MainWindow()`                                | ✅          |

Status bar internals (`mw._warning_indicator`, `mw._status_page_info`,
`mw._status_font_info`) move *into* `StatusBarManager`. Search confirms these
are referenced only inside `ui.py` itself — no test or external code touches
them, so the move is safe.

The methods `_refresh_warning_indicator`, `_show_warning_details`,
`_update_status_bar_page_info`, `_update_status_bar_font_info` remain callable
on `MainWindow` as **thin delegates** to the manager, because the viewer
signal-connect lines reference them by name:

```python
self.viewer.render_finished.connect(self._update_status_bar_page_info)
```

Reproducing them as 1-line delegates preserves the bound-method identity that
PySide6 uses for connect/disconnect bookkeeping.

---

## 6. Implementation Order

Per Plan §8:

1. **A** — `ui_statusbar.py` (smallest blast radius, validates pattern)
2. **B** — `ui_toolbar.py`
3. **C** — `ui_menu.py` + `ShortcutBuilder`
4. **D** — `ui_handlers.py` (4 mixins in one file)
5. **E** — Rewrite `ui.py` to use all of the above
6. **F** — Run `pytest -q tests/` after each phase

---

## 7. Test Plan

| Test                                    | Why it must pass                              |
|-----------------------------------------|------------------------------------------------|
| `tests/test_smoke.py`                   | MainWindow instantiates without error          |
| `tests/test_ui.py`                      | Full UI behavioral parity                      |
| `tests/test_regressions.py`             | Action attribute names + behaviors preserved   |
| `tests/test_long_text_warning.py`       | Status bar warning indicator wiring intact     |
| `tests/test_page_management.py`         | Page manager dialog launch handler intact      |
| `tests/test_preview_save_equivalence.py`| Save flow unaffected                           |
| `tests/test_viewer_crash.py`            | Viewer/MainWindow integration intact           |
| `tests/test_mypy.py`                    | Type checking clean across new modules         |

---

## 8. Open Questions

- **None.** All architecture decisions self-consistent with existing patterns.
