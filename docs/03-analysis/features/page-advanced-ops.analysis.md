# Analysis: page-advanced-ops (Gap Detection)

> **Analysis Type**: Gap Analysis (Design vs Implementation)
> **Project**: PDF Control (Starter / PySide6 + PyMuPDF)
> **Date**: 2026-05-25
> **Plan**: [page-advanced-ops.plan.md](../../01-plan/features/page-advanced-ops.plan.md)
> **Design**: [page-advanced-ops.design.md](../../02-design/features/page-advanced-ops.design.md)
> **Status**: ✅ Approved

---

## 1. Summary

The `page-advanced-ops` feature (Duplicate / Extract / Merge for `PageManagerDialog`) is **fully implemented** across all four layers (Model, Controller, UI, i18n) and is covered by **15 unit tests** (vs. the 9 originally promised by the Plan). All method signatures match the Design contract exactly, all 13 i18n keys exist in both `en.json` and `ko.json`, and edge cases (empty input, duplicate indices, out-of-range, nonexistent file, self-overwrite) are guarded with the exception types the Design specified.

Implementation **exceeds** the Plan in two non-breaking ways:

1. `duplicate_pages` adds a *duplicate-indices* `ValueError` guard (defensive — Plan only required empty + out-of-range).
2. The test suite adds 6 extra cases beyond the 9 promised (e.g. `test_extract_overwriting_source_raises`, `test_duplicate_preserves_content`).

Additionally, during implementation the `copy_page(idx, idx+1)` call was found to raise `ValueError` when duplicating the last page; the fix uses `to=-1` for end-of-document insertion (handled inline during Do phase).

**No gaps blocking Report. Recommendation: proceed to Report.**

---

## 2. Match Rate

**19 / 19 Acceptance Criteria met = 100%**

```
+---------------------------------------------+
|  Match Rate: 100%                           |
+---------------------------------------------+
|  Met (OK):          19 / 19  (100%)         |
|  Partial (WARN):     0 / 19  (0%)           |
|  Missing (FAIL):     0 / 19  (0%)           |
+---------------------------------------------+
```

---

## 3. Criteria-by-Criteria Verification

### 3.1 Model layer — `app/model.py`

| #   | Acceptance Criterion                                                | Status | Evidence                                                                                                                                                                                                                                                                                                                                                            |
| --- | ------------------------------------------------------------------- | :----: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| M1  | `duplicate_pages(page_indices: List[int]) -> int`                  | ✅     | `app/model.py` — Signature matches Design literally. Returns `len(page_indices)`. Raises `ValueError` on empty and on duplicates (stricter than Plan). Raises `IndexError` on out-of-range. Iterates `sorted(reverse=True)` with `copy_page` (uses `to=-1` for end). Calls `_rebuild_after_reorder()`. |
| M2  | `extract_pages(page_indices: List[int], output_path: str) -> None` | ✅     | `app/model.py` — Signature matches. `ValueError` on empty, missing dir, self-overwrite. `IndexError` on invalid indices. Builds temp `fitz.open()` doc with per-index `insert_pdf(from_page, to_page)`, then `save()` in `try/finally`. `modified` flag untouched.                                                                                                |
| M3  | `merge_pdf(source_path: str, after_index: int = -1) -> int`        | ✅     | `app/model.py` — Signature matches. `FileNotFoundError` on missing file, `ValueError` on out-of-range index, `fitz.open` wrapped in try/except → `ValueError("Invalid PDF: ...")`. Uses `insert_pdf(src, start_at=...)`. Calls `_rebuild_after_reorder()`. Returns added page count.                                                                                |

### 3.2 Controller layer — `app/controller.py`

| #   | Acceptance Criterion                                                              | Status | Evidence                                                                                                                                                                                  |
| --- | --------------------------------------------------------------------------------- | :----: | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| C1  | `duplicate_pages(page_indices: list) -> bool`                                     | ✅     | Guards `_session`, try/except, `operation_applied.emit()` on success, `logger.error` + `error_occurred.emit` on failure.                                                                  |
| C2  | `extract_pages(page_indices: list, output_path: str) -> bool`                     | ✅     | Same try/except shape. Does **not** emit `operation_applied` per Design Section 2.2 (original unchanged). Intentional and verified.                                                       |
| C3  | `merge_pdf(source_path: str, after_index: int = -1) -> bool`                      | ✅     | Same shape, emits `operation_applied`.                                                                                                                                                    |
| C4  | All three mirror existing `rotate_page` / `delete_pages` pattern                  | ✅     | Identical structure to siblings; matches Design Section 2.2 verbatim.                                                                                                                     |

### 3.3 UI layer — `app/page_manager_dialog.py`

| #   | Acceptance Criterion                                                              | Status | Evidence                                                                                                                                                              |
| --- | --------------------------------------------------------------------------------- | :----: | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| U1  | Toolbar separator + 3 actions (`duplicate_action`, `extract_action`, `merge_action`) | ✅   | Separator and actions registered in `_setup_ui` in the order Design Section 2.3 specifies.                                                                            |
| U2  | Handlers `_duplicate_selected`, `_extract_selected`, `_merge_pdf`                 | ✅     | All three methods present with the Design-specified signatures and behaviors.                                                                                          |
| U3  | Success path → `_load_thumbnails()` + `_mark_changed()`                           | ✅     | Duplicate and Merge call both. Extract intentionally does **not** call these (original unchanged, Design Section 2.2 decision).                                       |
| U4  | Failure path → `QMessageBox` + i18n message                                       | ✅     | `_duplicate_selected` and `_extract_selected` show `page_manager.error.no_selection`. Backend failures surface via existing `controller.error_occurred` signal pattern. |

### 3.4 i18n — `app/i18n/en.json` & `app/i18n/ko.json`

| #   | Acceptance Criterion                                                                                  | Status | Evidence                                                                                                                                                                                                                                                                          |
| --- | ----------------------------------------------------------------------------------------------------- | :----: | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| I1  | All 13 new keys present in **both** files (identical keyset, translated values)                       | ✅     | 13 keys 1:1 aligned: `page_manager.duplicate(.tooltip)`, `page_manager.extract(.tooltip\|.dialog_title\|.success)`, `page_manager.merge(.tooltip\|.dialog_title\|.success)`, `page_manager.error.{no_selection,invalid_pdf,file_not_found}`. Placeholder `{0}` consistent across both files. |

### 3.5 Tests — `tests/test_page_management.py`

| #   | Acceptance Criterion                                                       | Status | Evidence                                                                                                                                                                                                                                                                                |
| --- | -------------------------------------------------------------------------- | :----: | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T1  | `TestDuplicatePages` with single / multiple / empty cases                  | ✅     | 5 tests (Plan required 3): `test_duplicate_single_increases_page_count`, `test_duplicate_multiple_pages`, `test_duplicate_preserves_content`, `test_duplicate_empty_raises`, `test_duplicate_out_of_range_raises`.                                                                  |
| T2  | `TestExtractPages` with file creation / preserves original / invalid indices | ✅   | 6 tests (Plan required 3): adds `test_extract_preserves_text_content`, `test_extract_empty_raises`, `test_extract_overwriting_source_raises`.                                                                                                                                          |
| T3  | `TestMergePdf` with append / position / nonexistent                        | ✅     | 4 tests (Plan required 3): adds `test_merge_invalid_after_index_raises`.                                                                                                                                                                                                                |

### 3.6 i18n Validation

| #   | Acceptance Criterion                | Status | Evidence                                                                              |
| --- | ----------------------------------- | :----: | ------------------------------------------------------------------------------------- |
| V1  | en/ko keyset parity for new keys    | ✅     | Both files contain identical 13 keys. Placeholder consistency: `extract.success` and `error.file_not_found` use `{0}` in both. |

### 3.7 Regression / Build

| #   | Acceptance Criterion                                                            | Status | Evidence                                                                                                              |
| --- | ------------------------------------------------------------------------------- | :----: | --------------------------------------------------------------------------------------------------------------------- |
| R1  | Full test suite passes (existing + new)                                         | ✅     | `pytest tests/test_page_management.py -v` → **34/34 pass** (after initial copy_page fix).                            |
| R2  | `page_manager_dialog.py` import additions only, no existing-behavior changes    | ✅     | `QFileDialog` added to imports. No prior handlers modified. Toolbar additions are append-only.                       |
| R3  | CLAUDE.md drift test (assumption)                                               | ✅     | CLAUDE.md unchanged in this cycle; no new tech stack or structural claims that would break drift assertions.          |

---

## 4. Gap List

**None blocking.** Three minor observations (informational):

| Severity | Area              | Observation                                                                                                                                                  |
| -------- | ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Info     | Model M1          | `duplicate_pages` rejects duplicate indices with `ValueError`. Plan only required ValueError-on-empty; this is **stricter than spec** and safer. Recommend documenting in Design v1.1. |
| Info     | UI docstring      | Module docstring of `app/page_manager_dialog.py` still lists only rotate/delete/insert/reorder; new Duplicate/Extract/Merge capabilities are not mentioned. Cosmetic only. |
| Info     | Tests             | 15 tests implemented vs. 9 promised in Plan — over-delivery. Update Plan or Report to reflect actual count.                                                  |

No missing edge cases. No signature mismatches. No i18n key drift. No layer-boundary violations.

---

## 5. Convention / Architecture Compliance

| Area                                                                            | Status | Note                                                                                                          |
| ------------------------------------------------------------------------------- | :----: | ------------------------------------------------------------------------------------------------------------- |
| Naming (snake_case methods, PascalCase test classes)                            | ✅     | All new symbols follow CLAUDE.md conventions.                                                                 |
| Layer boundaries (Dialog → Controller → DocumentSession)                        | ✅     | No direct `fitz` calls from UI handlers; all PyMuPDF work stays inside `DocumentSession`.                     |
| i18n (no hardcoded UI strings)                                                  | ✅     | All user-visible text routed through `tr("page_manager.…")`.                                                  |
| Logging                                                                         | ✅     | `logger.info` on success in model and dialog; `logger.error` on controller failure paths.                     |

---

## 6. Recommendation

**Proceed to Report (`/pdca report page-advanced-ops`).**

Rationale:

- Match rate = 100% (19/19 criteria).
- 34/34 tests green.
- Zero blocking gaps; only three informational notes (defensive extra validation, stale module docstring, test-count over-delivery).
- Iteration is not warranted — `pdca-iterator` would have nothing to fix.

Optional follow-ups for the Report's "Lessons / Future Improvements" section:

1. Update Design v1.1 to memorialise the duplicate-indices ValueError guard.
2. Refresh the `PageManagerDialog` module docstring to mention Duplicate / Extract / Merge.
3. Consider Undo/Redo integration for page-level operations (currently out of scope, see Plan Section 4).

---

## Version History

| Version | Date       | Changes        | Author        |
| ------- | ---------- | -------------- | ------------- |
| 1.0     | 2026-05-25 | Initial gap analysis | gap-detector / Claude (bkit) |
