# Report: long-text-narrow-area-warning

**Status**: Completed
**Date**: 2026-04-15
**Phase**: PDCA Report
**Match Rate**: 95%

## Goal

Surface Preview-stage text-fit failures to the user instead of letting text silently disappear when `RedactReplace` hits the 8pt autofit floor. This was the last open item in CLAUDE.md Known Issues.

## Implementation Summary

End-to-end wiring of structured fit warnings from the operations service through the render-worker subprocess boundary into a session cache, a status-bar indicator, a history-panel badge, and a save-time confirmation dialog. Replaced the prior fragile English-string parsing (`'shrink' in w.lower()`) with an `OpWarning` dataclass so the UI stays i18n-safe.

## Key Design Decisions (D1–D5)

- **D1** Structured `OpWarning(op_index, severity, code, detail)` replaces free-text warnings
- **D2** `ApplyResult` propagates through `render_page_preview` → render_worker JSON → viewer → `DocumentSession.last_preview_warnings` cache + `warnings_changed` signal
- **D3** Status-bar `QToolButton` permanent widget (hidden when no warnings; `⚠ N` / `✖ N` depending on severity)
- **D4** History panel `QListWidgetItem.setIcon()` with `(page_idx, intra_page_redaction_idx)` mapping
- **D5** Save-time `QMessageBox.warning` with default Cancel when `has_blocking_warnings()`

## Files Changed

| File | Change |
|------|--------|
| `app/operations_service.py` | `OpWarning` dataclass; `ApplyResult.warnings: List[OpWarning]`; derived count properties; structured emission in `_insert_with_shrink` |
| `app/pdf_engine.py` | `render_page_preview` returns `ApplyResult \| None` |
| `app/render_worker.py` | Warnings serialized into response JSON |
| `app/viewer.py` | Pushes response warnings into `session.update_warnings` |
| `app/model.py` | `last_preview_warnings` cache, `warnings_changed` signal, `update_warnings()`, `has_blocking_warnings()` |
| `app/ui.py` | Status-bar indicator, details modal, history badges, save-time guard, signal wiring on document load |
| `app/i18n/en.json`, `app/i18n/ko.json` | +10 `warn.*` keys each |
| `tests/test_long_text_warning.py` (new) | 7 tests: 3 service unit, 1 session+signal, 1 derived-count, 1 i18n (parametrized ×2) |

## Test Results

- **Regression**: 93 → **100 passing** (+7) in 6.12s
- **mypy strict** on `app/operations_service.py`: `Success: no issues found in 1 source file`
- **Gap analysis**: 95% match rate (`docs/03-analysis/long-text-narrow-area-warning.analysis.md`)

## Key Findings

1. **Pre-existing bug fixed in passing**: `render_page_preview` silently dropped `ApplyResult`. Warnings already existed in the service layer for months but never reached the UI. The root cause was a missing return, not missing logic.
2. **Subprocess boundary forces serialization discipline**: Render-worker JSON round-trip (dataclass → dict → dict) means `last_preview_warnings` stores dicts, not `OpWarning` instances. This is fine because consumers (UI) read by key, but worth knowing if future code expects dataclass methods.
3. **`(page_index, intra_page_redaction_idx)` mapping works**: The design's R3 mitigation (re-counting during history rebuild) is O(n) and matches the applicator's enumeration exactly, so badges never drift.
4. **i18n-safe by construction**: Moving from string-substring parsing to a `code` field means Korean locale no longer breaks derived counts — previously `font_size_adjustments` was English-only.

## Acceptance Criteria

- [x] Preview `ApplyResult.warnings` collected and surfaced in UI
- [x] Status bar `N warnings` indicator with click-to-detail
- [x] History panel warning icon for shrink/overflow
- [x] Save-time confirmation on hard overflow (default Cancel)
- [x] i18n keys in both en/ko
- [x] Unit tests for collection path + i18n completeness (partial: QWidget-level UI tests deferred — see follow-up)
- [x] Full regression stays green (93 → 100)

## Follow-Up (Non-Blocking)

**G1 — pytest-qt UI tests for indicator/badge visibility transitions** (Test Matrix #5/#6/#7).
Currently covered via the session-signal unit test; adding three pytest-qt tests against `MainWindow` with a stub session would close the last gap. Recommended as a short post-archive task. Not a blocker — underlying signal flow is unit-tested.

## Next Phase

`/pdca archive long-text-narrow-area-warning`
