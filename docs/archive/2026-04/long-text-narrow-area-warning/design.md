# Design: long-text-narrow-area-warning

**Status**: Design
**Date**: 2026-04-15
**Plan**: `docs/01-plan/features/long-text-narrow-area-warning.plan.md`

## Current State Analysis

### 1. Warning Source (already exists)
`app/operations_service.py` collects warnings into `ApplyResult`:
- `warnings: List[str]` — human-readable messages
- `font_size_adjustments: int` — count of resized
- `text_shrink_count: int` — count of fallback shrinks
- Hard failure case at `_insert_with_shrink:488-500` appends `"Text insertion failed after shrinking..."` — **not currently distinguished from soft shrink warnings**

### 2. Warning Drop Sites (the bug)
Two call sites **discard** `ApplyResult`:
- `app/pdf_engine.py:103` — `render_page_preview()` calls `apply_page_operations(...)` and ignores return value
- `app/pdf_engine.py:64` — `apply_document_operations()` loops and ignores each page result

### 3. UI Structure
- **Status bar**: `QMainWindow.statusBar()` used via `showMessage(tr(...))` (transient). No permanent widgets.
- **History panel**: `self.history_list_widget = QListWidget()` at `app/ui.py:87`, rebuilt fully in `_update_history_panel()` at `app/ui.py:145`. String rows only, no icons.
- **History signal**: `controller.history_changed` → `_update_history_panel` (`app/ui.py:51`)

## Design Decisions

### D1. Distinguish warning severity at source
Add a severity tag instead of free-text parsing. Replace `warnings: List[str]` with:

```python
@dataclass
class OpWarning:
    op_index: int         # index in the operations list passed to apply_operations
    severity: str         # "info" | "warn" | "error"
    code: str             # "text.shrunk" | "text.overflow" | ...
    detail: Dict[str, Any]  # fontsize_from, fontsize_to, text_len, rect
```

`ApplyResult.warnings: List[OpWarning]`. Preserve `font_size_adjustments` / `text_shrink_count` as derived counts.

**Why**: Parsing `'shrink' in w.lower()` (current code, `operations_service.py:148-149`) is fragile and coupled to English strings. i18n would break it. Structured data also lets UI decide formatting.

### D2. Propagate ApplyResult through the preview path
- `render_page_preview()` — return `ApplyResult | None` instead of `None`
- `apply_document_operations()` — return `Dict[int, ApplyResult]` (page_index → result)
- `DocumentSession` — gain `last_preview_warnings: Dict[int, List[OpWarning]]` cache keyed by `page_index`, updated when preview renders
- New signal on `DocumentSession`: `warnings_changed = Signal()` emitted after preview apply

**Why**: UI needs to react only when preview updates, not on every user click. A cache avoids re-running apply just to query warnings.

### D3. Status bar permanent warning widget
Add a `QToolButton` as a permanent widget via `statusBar().addPermanentWidget(self.warning_indicator)`:

- Hidden when no warnings
- Visible as `⚠ N` when `any(w.severity in {"warn","error"} for w in current_page_warnings)`
- Click → opens modal `WarningDetailsDialog` listing all warnings with `op_index`, i18n code label, detail fields

**Why**: Transient `showMessage` clears on next action — unsuitable for persistent state. Permanent widget survives renders.

### D4. History panel badge
Extend `_update_history_panel` to attach `QIcon` (warn/error) to `QListWidgetItem` when `last_preview_warnings[op.page_index]` contains an entry matching that op's index within its page.

- Use theme icons: `QStyle.SP_MessageBoxWarning`, `SP_MessageBoxCritical`
- Tooltip contains the i18n code label

**Mapping challenge**: `OpWarning.op_index` is the index within the per-page operations list passed to `apply_operations`, not the global history index. Solve by having the session store warnings keyed by `(page_index, intra_page_op_index)` and resolve during history rebuild.

### D5. Save-time hard-failure guard
When user triggers save and any cached warning has `severity == "error"`:
- Show `QMessageBox.warning` with `Save anyway / Cancel`
- Default button: `Cancel`
- i18n keys: `warn.save_with_errors.title`, `warn.save_with_errors.body`

This is only a check against the most recent preview. A save with no recent preview bypasses it — acceptable for v1.

## Data Flow

```
User action → Controller → render_preview
                              ↓
                     apply_page_operations → ApplyResult
                              ↓
                   session.update_warnings(page_idx, result.warnings)
                              ↓
                     warnings_changed signal
                              ↓
            ┌────────────────┼────────────────┐
            ↓                ↓                ↓
    status indicator   history panel    (future: tooltip)
```

## i18n Keys (new)

```json
"warn.indicator.label": "{n} warnings",
"warn.details.title": "Text fit warnings",
"warn.code.text.shrunk": "Text shrunk from {from}pt to {to}pt",
"warn.code.text.overflow": "Text did not fit even at minimum size",
"warn.save_with_errors.title": "Warnings detected",
"warn.save_with_errors.body": "Some text operations did not fit. Save anyway?"
```

Both `en.json` and `ko.json` required.

## File-Level Changes

| File | Change |
|------|--------|
| `app/operations_service.py` | `OpWarning` dataclass; emit structured warnings; derive counts |
| `app/pdf_engine.py` | Return `ApplyResult` from `render_page_preview` and dict from `apply_document_operations` |
| `app/model.py` | `DocumentSession.last_preview_warnings`, `update_warnings()`, `warnings_changed` signal |
| `app/controller.py` | Wire preview result → session cache |
| `app/ui.py` | Status bar permanent widget; history badges; save-time guard; i18n |
| `app/i18n/{en,ko}.json` | New keys |
| `tests/test_long_text_warning.py` | New: unit + pytest-qt |

## Test Matrix

| # | Layer | Scenario | Expected |
|---|-------|----------|----------|
| 1 | unit (service) | narrow rect + long text | `warnings` non-empty, severity=warn, code=text.shrunk |
| 2 | unit (service) | 1pt × 1pt rect | severity=error, code=text.overflow |
| 3 | unit (service) | normal replace | warnings empty |
| 4 | unit (session) | cache write/read round-trip | `last_preview_warnings` populated, signal emitted |
| 5 | pytest-qt | preview renders a shrinking op | status indicator visible with correct count |
| 6 | pytest-qt | preview with clean op | indicator hidden |
| 7 | pytest-qt | history panel shows warning icon | item has icon + tooltip |
| 8 | i18n | all new keys exist in en + ko | validator passes |

## Risks & Mitigations

- **R1. Breaking existing callers of warnings list** — `result.font_size_adjustments` / `text_shrink_count` are private to service use in tests only. Derive via `sum(1 for w in warnings if ...)` after refactor.
- **R2. Icon theme inconsistency across OS** — Use `QStyle.standardIcon()` which falls back cleanly on Windows.
- **R3. Mapping per-page `op_index` to global history position** — Store intra-page index, resolve by re-counting during history panel rebuild (O(n), n small).

## Open Questions — Resolved

1. **Save-block default**: Soft warning (save allowed with confirmation). ✓
2. **History badge support**: `QListWidgetItem.setIcon()` is natively supported — no custom delegate needed. ✓

## Implementation Order (for Do phase)

1. Refactor `OpWarning` + service warning emission (test #1, #2, #3 drive this)
2. Propagate result through `pdf_engine` + session cache (test #4)
3. Status bar indicator widget + i18n (test #5, #6)
4. History panel icon binding (test #7)
5. Save-time confirmation dialog
6. i18n validator run (test #8)
7. Full regression — must stay at 93 + new tests
