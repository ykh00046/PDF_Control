# Gap Analysis: ui.py Monolith Refactoring

> **Feature**: ui-refactor
> **Date**: 2026-05-23
> **Design ref**: `docs/02-design/features/ui-refactor.design.md`
> **Implementation ref**: `app/ui.py`, `app/ui_menu.py`, `app/ui_toolbar.py`, `app/ui_statusbar.py`, `app/ui_handlers.py`

---

## 1. Design vs Implementation Match

| Design item                                | Implemented?           | Notes |
|--------------------------------------------|------------------------|-------|
| `ui.py` — slim orchestrator                | ✅                     | 197 lines (target ≤ 250) |
| `ui_menu.py` — MenuBuilder + ShortcutBuilder | ✅                   | Both classes present, exact API |
| `ui_toolbar.py` — ToolbarBuilder           | ✅                     | Single class, exact API |
| `ui_statusbar.py` — StatusBarManager       | ✅                     | All 5 public methods present |
| `ui_handlers.py` — 4 mixin classes         | ✅                     | File / Edit / Dialog / StateUpdate |
| MainWindow MRO: Qt first                   | ✅                     | Confirmed via `MainWindow.__mro__` |
| All `QAction` attributes preserved         | ✅                     | undo/redo/zoom/delete/replace/page nav |
| All handler method names preserved         | ✅                     | 39/39 method preservation check passed |
| `closeEvent`, `dragEnterEvent`, `dropEvent` work | ✅              | Explicit MainWindow delegates to FileHandlerMixin |
| Status bar private methods preserved as delegates | ✅            | `_refresh_warning_indicator`, etc. |
| No `__init__` in mixins                    | ✅                     | All four mixins are stateless |
| `TYPE_CHECKING`-only `MainWindow` import   | ✅                     | No circular imports |

---

## 2. Success Criteria (from Plan §6)

| # | Criterion                                       | Target  | Actual  | Status |
|---|-------------------------------------------------|--------:|--------:|:------:|
| 1 | `app/ui.py` line count                          | ≤ 250   | **197** | ✅     |
| 2 | All existing tests pass with zero test changes  | 100 %   | **104/104** | ✅ |
| 3 | `from app.ui import MainWindow` works           | yes     | yes     | ✅     |
| 4 | `main_window.delete_selection()` etc. callable  | yes     | yes     | ✅     |
| 5 | `QAction` attrs (`mw.undo_action`, …) on window | yes     | yes     | ✅     |
| 6 | mypy clean                                      | yes     | yes (`test_mypy.py` green) | ✅ |
| 7 | i18n strings untouched                          | yes     | yes (`test_i18n_validation.py` green) | ✅ |
| 8 | No new public exports in `app/__init__.py`      | yes     | yes (unchanged) | ✅ |

---

## 3. Code-Level Inventory

### 3.1 New files

| File                     | Lines | Bytes | Class(es)                                                  |
|--------------------------|------:|------:|------------------------------------------------------------|
| `app/ui_menu.py`         |  172  | 6,603 | `MenuBuilder`, `ShortcutBuilder`                           |
| `app/ui_toolbar.py`      |   76  | 2,804 | `ToolbarBuilder`                                            |
| `app/ui_statusbar.py`    |  155  | 6,088 | `StatusBarManager`                                          |
| `app/ui_handlers.py`     |  894  | 37,175| `FileHandlerMixin`, `EditHandlerMixin`, `DialogHandlerMixin`, `StateUpdateMixin` |

### 3.2 `ui.py` before vs after

|                     | Before        | After         | Δ         |
|---------------------|--------------:|--------------:|----------:|
| Lines               | 1,126         | 197           | **−82.5 %** |
| Bytes               | 51,810        | 8,145         | **−84.3 %** |
| Methods on class    | 32            | 7 (plus mixin inheritance) | −78 % |
| Direct concerns     | 5 (menu / toolbar / statusbar / shortcuts / events) | 1 (orchestration) | 4 fewer |

### 3.3 Aggregate

| Metric                                | Value |
|---------------------------------------|------:|
| Total lines across the 5 UI files     | 1,494 |
| Net delta vs original 1,126 lines     | +368 (+32.7 %) |
| Increase rationale                    | Module docstrings (5), `from __future__` lines (5), `TYPE_CHECKING` blocks (4), explicit Qt-event delegates (3), explicit type hints, blank-line separators between classes |

The aggregate-line increase is expected and intentional: the cost of
modularization is preamble (docstrings, imports, type fences) plus the
explicit delegation glue. The benefit is that no single file exceeds 894
lines and `ui.py` itself is now 197 lines — exactly the readability win the
plan targeted.

---

## 4. Test-Run Evidence

```
$ pytest tests/ -p no:cacheprovider
─────────────────────────────────────────────────────
tests/test_async.py .                                1
tests/test_claude_md_drift.py ........               8
tests/test_i18n_validation.py ...                    3
tests/test_long_text_warning.py .......              7
tests/test_mypy.py .                                 1
tests/test_page_management.py ...................   19
tests/test_preview_save_equivalence.py ...           3
tests/test_pyinstaller_bundling.py .......           7
tests/test_regressions.py ...................       19
tests/test_remove_section.py .....                   5
tests/test_smoke.py ....                             4
tests/test_text_utils.py .......................    23
tests/test_ui.py ...                                 3
tests/test_viewer_crash.py .                         1
─────────────────────────────────────────────────────
104 passed in ~10 s
```

---

## 5. Issues Encountered & Resolved

### Issue 1: Test monkey-patch path

**Symptom**: `test_replace_selection_does_not_log_sensitive_text` failed with
`AttributeError: module 'app.ui' has no attribute 'QInputDialog'`.

**Root cause**: Test does `patch("app.ui.QInputDialog.getText", …)`, but
`QInputDialog` was moved to `app/ui_handlers.py` during extraction.

**Fix**: Re-exported `QInputDialog` from `app/ui.py` (one-line import with
`# noqa: F401` and explanatory comment). Because Python classes are
singletons, patching `app.ui.QInputDialog.getText` also patches the same
attribute viewed via `app.ui_handlers.QInputDialog`, so the patch retains
its effect on the production code path.

**Cost**: 1 line of source change. **Tests**: 0 changed.

### Issue 2: MRO / Qt event override risk

**Symptom (avoided)**: `closeEvent`, `dragEnterEvent`, `dropEvent` exist on
`QMainWindow` as base implementations. With `class MainWindow(QMainWindow, FileHandlerMixin)`,
Python MRO finds `QMainWindow.closeEvent` *before* `FileHandlerMixin.closeEvent`
— so the mixin override would be silently shadowed.

**Resolution**: Three explicit one-line delegators on `MainWindow` that call
`FileHandlerMixin.closeEvent(self, event)` etc. Documented in the design and
in the file with a comment block.

**Verification**: `tests/test_viewer_crash.py` (which exercises closeEvent
indirectly via the Qt close lifecycle) and `test_regressions.py` both pass.

---

## 6. Match Rate

Using the rubric from `bkit-rules`:

- **Structural match** (file layout, class names, method names): **10 / 10**
- **Behavioral match** (test pass rate): **10 / 10**
- **API match** (external import + call surface preserved): **10 / 10**
- **Design adherence** (mixin pattern, no state in mixins, MRO discipline): **10 / 10**
- **Documentation match** (plan/design/analysis docs present and aligned): **10 / 10**

**Overall Match Rate: 100 %** — well above the 90 % bar.

Proceed directly to Report phase (no `pdca-iterate` needed).
