# Plan: ui.py Monolith Refactoring

> **Feature**: ui-refactor
> **Created**: 2026-05-23
> **Owner**: PDCA / refactor sprint
> **Status**: Plan

---

## 1. Problem Statement

`app/ui.py` has grown to **1,126 lines / 51 KB**, holding the entire `MainWindow`
class. It mixes five concerns:

1. Menu construction
2. Toolbar construction
3. Status bar + warning indicator management
4. Keyboard shortcuts
5. Event handlers (file ops, edit ops, dialog launch, drag/drop, state updates)

This violates the **SRP** rule in `CLAUDE.md` ("One function, one responsibility")
and the **50-line function threshold** ("Function exceeds 50 lines → Split").
The file is now hostile to:

- Reading (no class member can be located without scrolling 800+ lines)
- Testing (no way to unit-test menu wiring without a full QMainWindow)
- Reuse (other windows cannot share the toolbar/statusbar patterns)
- Future i18n/theming work (style block, menu strings, etc. all collide)

---

## 2. Goal

Split `MainWindow` into **5 cooperating files**, each with a single concern,
**without changing the external API**. Tests, `main.py`, and any user-facing
behavior must remain bit-identical.

---

## 3. Out of Scope

- No behavioral changes (no new features, no bug fixes beyond mechanical safety)
- No changes to `Dialog` classes, `Controller`, `Viewer`, `Model`, `i18n`
- No new dependencies
- No test changes beyond what's required to keep them green

---

## 4. Reference Pattern

The existing Dialog modules — `batch_replace_dialog.py`, `crop_dialog.py`,
`page_manager_dialog.py`, `remove_section_dialog.py` — follow this pattern:

- One file per concern, named `<noun>_dialog.py` / `<noun>.py`
- A single class that owns its widget tree
- `Signal` instances for upward communication with the parent window
- `_setup_ui()` private method for layout construction
- Uses `tr()` (i18n) and `get_logger()` directly

We will follow the **same module-per-concern shape** but adapt it for
**MainWindow-owned components**: instead of returning a `QDialog`, helpers will
take `MainWindow` and either build widgets onto it or expose handler methods
via Python mixin inheritance (so existing call sites and tests continue to work
unchanged).

---

## 5. Target Module Breakdown

| New file              | Lines (est.) | Responsibility                                          |
|-----------------------|-------------:|---------------------------------------------------------|
| `app/ui.py`           |   ~200       | `MainWindow.__init__`, dock setup, style, orchestration |
| `app/ui_menu.py`      |   ~140       | `MenuBuilder` + `ShortcutBuilder`                       |
| `app/ui_toolbar.py`   |    ~70       | `ToolbarBuilder`                                        |
| `app/ui_statusbar.py` |   ~110       | `StatusBarManager` (build + refresh + show warnings)    |
| `app/ui_handlers.py`  |   ~500       | Event handler mixins (file, edit, dialog, state)        |
| **TOTAL**             | **~1,020**   | (target: ≤ original 1,126, ideally less from de-dup)    |

---

## 6. Success Criteria

| # | Criterion                                                              | Verification                       |
|---|------------------------------------------------------------------------|------------------------------------|
| 1 | `app/ui.py` ≤ 250 lines                                                | `wc -l app/ui.py`                  |
| 2 | All existing tests pass with **zero changes**                          | `pytest -q tests/`                 |
| 3 | `from app.ui import MainWindow` continues to work                       | grep + smoke import                |
| 4 | `main_window.delete_selection()`, `.open_file()`, etc. still callable  | tests/test_ui.py runs as-is        |
| 5 | All `QAction` attributes (`self.undo_action`, etc.) still on MainWindow | tests/test_regressions.py runs    |
| 6 | mypy clean                                                              | `pytest tests/test_mypy.py`        |
| 7 | i18n strings untouched                                                 | `tests/validate_i18n.py`           |
| 8 | No new public functions in `app/__init__.py` exports                   | diff check                         |

**Gap target**: ≥ 90 % match between design and implementation.

---

## 7. Risks & Mitigations

| Risk                                          | Likelihood | Mitigation                                        |
|-----------------------------------------------|:----------:|---------------------------------------------------|
| Mixin MRO surprises                           | Low        | Keep mixins stateless; only inherit from `object` |
| Signal disconnect after action rewire         | Low        | Reuse same `QAction` instances; don't recreate    |
| Test brittleness on private method paths      | Medium     | Keep private method names identical on MainWindow |
| PyInstaller bundling misses new files         | Low        | Auto-discovered by `app/` package import          |
| Circular import (handler → ui → handler)      | Medium     | Mixins import `typing.TYPE_CHECKING` only         |

---

## 8. Approach: 4 Phases

1. **Phase A — Status bar** (smallest, lowest risk; proves pattern)
2. **Phase B — Toolbar** (small, depends on shared `QAction` instances)
3. **Phase C — Menu + shortcuts**
4. **Phase D — Event handler mixins** (biggest, validate by tests after each)

After each phase: run `pytest -q tests/test_smoke.py tests/test_ui.py`
to catch regressions early.

---

## 9. Definition of Done

- [ ] All 4 new files created
- [ ] `app/ui.py` ≤ 250 lines
- [ ] All tests green (`pytest tests/`)
- [ ] mypy clean
- [ ] Design document at `docs/02-design/features/ui-refactor.design.md`
- [ ] Gap analysis ≥ 90 %
- [ ] Completion report at `docs/04-report/features/ui-refactor.report.md`
