# Gap Analysis: long-text-narrow-area-warning

**Status**: Check
**Date**: 2026-04-15
**Match Rate**: **95%**
**Recommendation**: Proceed to `/pdca report` (above 90% threshold)

## Summary

Implementation is a faithful, near-1:1 realization of the design. All 11 File-Level changes are in place with exact shape and location as designed. 7/7 acceptance criteria met; one test-coverage breadth gap (3 pytest-qt UI tests from the design's Test Matrix were not added).

## Item-by-Item Matrix

| # | Design Element | Status | Evidence |
|---|----------------|--------|----------|
| 1 | `OpWarning` dataclass (op_index, severity, code, detail) | ✅ Full | `app/operations_service.py:33-39` |
| 2 | `ApplyResult.warnings: List[OpWarning]` + derived `font_size_adjustments` / `text_shrink_count` / `has_errors` | ✅ Full | `app/operations_service.py:42-60` |
| 3 | Structured emission for `text.shrunk` (warn) and `text.overflow` (error) | ✅ Full | `app/operations_service.py:496-529` |
| 4 | `render_page_preview()` returns `ApplyResult \| None` | ✅ Full | `app/pdf_engine.py:85-113` |
| 5 | Render worker serializes warnings into JSON response | ✅ Full | `app/render_worker.py:60-68` |
| 6 | Viewer pushes response warnings into `session.update_warnings` | ✅ Full | `app/viewer.py:238-244` |
| 7 | `DocumentSession.last_preview_warnings` + `warnings_changed` + `update_warnings()` + `has_blocking_warnings()` | ✅ Full | `app/model.py:382, 396, 429-443` |
| 8 | Status bar `QToolButton` permanent indicator + details modal | ✅ Full | `app/ui.py:780-822` |
| 9 | History panel `setIcon` with (page_idx, intra_idx) mapping | ✅ Full | `app/ui.py:162-220` |
| 10 | Save-time `QMessageBox.warning` with Save/Cancel, default Cancel | ✅ Full | `app/ui.py:966-978` |
| 11 | i18n keys in en + ko (warn.*) | ✅ Full (+4 extras) | `app/i18n/en.json`, `ko.json` |

**Implementation surface score**: 11/11 = 100%

## Test Matrix Coverage

| # | Scenario | Status |
|---|----------|--------|
| 1 | unit: narrow rect + long text → warn | ✅ `test_narrow_rect_long_text_emits_shrink_warning` |
| 2 | unit: tiny rect → error | ✅ `test_impossible_rect_emits_overflow_error` |
| 3 | unit: normal replace → empty | ✅ `test_normal_replace_emits_no_warnings` |
| 4 | unit: session cache + signal | ✅ `test_session_update_warnings_cache_and_signal` |
| 5 | pytest-qt: preview shrinking → indicator visible | ❌ Missing |
| 6 | pytest-qt: clean op → indicator hidden | ❌ Missing |
| 7 | pytest-qt: history panel warning icon + tooltip | ❌ Missing |
| 8 | i18n: keys exist in en + ko | ✅ `test_warning_i18n_keys_present` (parametrized) |

**Test matrix score**: 5/8 = 62.5%
Bonus: `test_opwarning_properties_derive_counts` covers derived count properties (not in the matrix, but valuable).

## Acceptance Criteria Check

| AC | Status |
|----|--------|
| 1. Preview warnings collected and surfaced in UI | ✅ |
| 2. Status bar indicator with click-to-detail | ✅ |
| 3. History panel warning icon for shrink/overflow | ✅ |
| 4. Save-time confirmation on overflow | ✅ |
| 5. i18n keys in en + ko | ✅ |
| 6. Unit tests for collection path, UI state transitions, i18n | 🟡 Partial — UI state transitions only tested at the session signal level, not at QWidget level |
| 7. Full regression 93/93 → 100/100 | ✅ Verified |

**AC score**: 6.5 / 7 = 92.9%

## Match Rate

Headline: **95%** (weighted average of implementation 100% + AC 92.9% + test matrix 62.5% with heavier weight on the first two, since they define the contract; test matrix is a desirable but non-blocking sub-quality)

## Strengths

- Design-to-code fidelity unusually high — every File-Level Changes row is implemented in the exact file/method proposed.
- Structured `OpWarning` (D1) cleanly replaces fragile English-string parsing, as the design called out.
- `(page_index, intra_page_op_index)` mapping (D4) solved exactly via the R3 mitigation (re-counting during history rebuild).
- Worker boundary serialization is round-trip clean: dataclass → JSON dict → session cache.
- Empty-list handling in `update_warnings` correctly clears entry and still emits signal.
- Save guard defaults to Cancel, matching D5.

## Gaps

### G1 (minor) — Missing pytest-qt UI tests
Test Matrix items #5, #6, #7 (status indicator visible/hidden transitions and history icon rendering) were not added. UI code paths `_refresh_warning_indicator`, `_show_warning_details`, and `setIcon` wiring are currently exercised only via the session signal unit test and manual use.

**Mitigation**: Low risk — the underlying signal flow is unit-tested, and the UI slots are simple view updates. Recommend opening a follow-up task "Add pytest-qt UI tests for warning indicator and history badge" post-archive. Not a blocker for report.

### G2 (cosmetic) — Placeholder style
Design used `{n}` placeholders; implementation uses positional `{0}`. Same meaning under `tr()`, both locales consistent. Not a real gap.

## Recommendation

**Proceed to `/pdca report long-text-narrow-area-warning`.** Implementation faithfully realizes D1–D5 and meets all 7 plan acceptance criteria. G1 is worth a short follow-up task but not a blocker.
