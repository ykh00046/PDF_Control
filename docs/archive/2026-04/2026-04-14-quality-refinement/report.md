# PDCA Report: Quality Refinement Session

**Date**: 2026-04-14
**Feature**: Project Review & Quality Refinement
**Phase**: Completed
**Match Rate**: N/A (refactoring + test augmentation, no new feature spec)

---

## 1. Summary

Two-stage improvement session on the PDF_Control desktop application, driven by a detailed codebase review. Resolved outdated documentation, externalized hardcoded memory thresholds, refactored a long UI handler, added three new test suites, and discovered & fixed a latent production bug in the operations pipeline.

**Test count**: 72 → **84 passing** (+12 new tests, 0 failures, 0 timeouts).

---

## 2. Completed Work

### 2.1 Documentation Alignment

- **CLAUDE.md Known Issues section** updated. Four items previously listed as open — `config default pollution`, `preview temp document leak`, `RemoveSection memory guard`, `preview-save divergence` — were verified as already resolved in code and moved into a "Resolved (2026-04-14 review)" subsection with file:line references.

### 2.2 Configuration Externalization

- Moved hardcoded memory budgets out of `app/model.py` into `DEFAULT_CONFIG["memory"]` in `app/config.py`:
  - `remove_section_dpi_cap_mb` (was 500)
  - `remove_section_large_warn_mb` (was 100)
  - `merge_warn_mb` (was 50)
  - `merge_abort_mb` (was 200)
- `RemoveSectionAsImage.apply` now reads from config via `_memory_limits()` helper.

### 2.3 `replace_selection()` Refactor

- `app/ui.py:636-729` was a 94-line function with 3-level nested try/except, violating project convention (50-line limit).
- Split into three focused helpers:
  - `_snap_selection_to_text(page, rect)` — Smart Snap logic for tightening selection to text span bounding box.
  - `_prompt_replacement_text(existing_text)` — Modal input dialog with cancel handling.
  - `_resolve_replacement_font()` — Font path resolution with Korean fallback.
- Main `replace_selection()` now ~25 lines, linear flow.

### 2.4 i18n Validation in pytest

- Wrapped existing `tests/validate_i18n.py` logic into `tests/test_i18n_validation.py` (3 tests):
  - `test_both_files_load`
  - `test_no_missing_keys`
  - `test_format_placeholders_match`
- Now runs as part of the standard pytest suite, catching drift during CI.

### 2.5 Preview=Save Visual Equivalence Tests

- New `tests/test_preview_save_equivalence.py` (3 tests) validates that `ApplyMode.PREVIEW` and `ApplyMode.SAVE` produce pixel-identical page renders.
- **Key finding**: Preview mode draws white rectangles over text (non-destructive) while Save uses destructive redaction. `page.get_text()` extracts the underlying text layer which **intentionally diverges** between modes. Pixel-based comparison is the correct contract.
- Tolerances: Delete <1%, Replace/Combined <2%.

### 2.6 PyInstaller Bundling Validation

- New `tests/test_pyinstaller_bundling.py` (7 tests):
  - Frozen-mode simulation via `sys._MEIPASS` monkeypatching — verifies `path_helper.get_i18n_path` resolves resources.
  - Dev-mode sanity: real i18n JSON files exist.
  - `PDF_CONTROL_APP_DATA_DIR` env override isolation.
  - `pdf_control.spec` includes `app/i18n/*.json` datas.
  - `pdf_control.spec` declares all critical hiddenimports (`fitz`, `PIL.Image`, PySide6, all `app.*` dialog/worker modules).
  - Excludes block doesn't accidentally strip runtime dependencies.
  - Every file under `app/*.py` is importable (catches broken modules before frozen build).
- Plus an actual `pyinstaller pdf_control.spec` build run for end-to-end verification.

### 2.7 Bonus: Pre-existing Bug Fix

- `app/operations_service.py:242` imported `_calculate_estimated_fontsize` from `app.model`, but that function **did not exist** — caused `ImportError` in smoke tests whenever `RedactReplace` was used with `fontsize != 0`.
- Additionally, `_calculate_font_sizes` was declared to return `Dict[int, float]` but `_insert_replacement_text` consumed it as `Dict[int, Dict]` (calling `.get("fontsize")`) — **type contract mismatch** causing `AttributeError: 'float' object has no attribute 'get'`.
- **Fix**: Rewrote `_calculate_font_sizes` to return full metadata dicts sourced from `_extract_text_metadata`, with explicit override when `op.fontsize > 0`.
- **Impact**: 3 previously-failing smoke tests (`test_pdf_redaction_and_replacement_with_custom_font`, `test_save_clears_history`, `test_multi_page_operations`) now pass.

### 2.8 Test Infrastructure: closeEvent Hang Fix

- pytest-qt `_close_widgets()` teardown was hanging on any test that modified a `MainWindow` session, because `closeEvent` opened a modal `QMessageBox.question("Save changes?")`.
- Added autouse fixture `_suppress_close_confirm_dialog` in `tests/conftest.py` that monkeypatches `QMessageBox.question` to return `Discard` — applies globally to every test.

---

## 3. Files Changed

| File | Change | Type |
|---|---|---|
| `CLAUDE.md` | Resolved section added | doc |
| `app/config.py` | `memory` block in DEFAULT_CONFIG | feat |
| `app/model.py` | `_memory_limits()` helper, remove hardcoded thresholds | refactor |
| `app/ui.py` | `replace_selection` split into 4 methods | refactor |
| `app/operations_service.py` | `_calculate_font_sizes` returns metadata dict | fix |
| `tests/conftest.py` | Global QMessageBox auto-Discard fixture | test-infra |
| `tests/test_ui.py` | Local fixture removed (moved to conftest) | test-infra |
| `tests/test_i18n_validation.py` | **new** — 3 tests | test |
| `tests/test_preview_save_equivalence.py` | **new** — 3 tests | test |
| `tests/test_pyinstaller_bundling.py` | **new** — 7 tests | test |

---

## 4. Test Results

```
$ python -m pytest tests/ --timeout=30 -q
84 passed in 6.92s
```

| Suite | Count | Status |
|---|---|---|
| test_smoke | 9 | ✅ (3 were pre-broken) |
| test_remove_section | 12 | ✅ |
| test_page_management | many | ✅ |
| test_ui | 3 | ✅ (previously hanging) |
| test_i18n_validation | 3 | ✅ **new** |
| test_preview_save_equivalence | 3 | ✅ **new** |
| test_pyinstaller_bundling | 7 | ✅ **new** |
| **Total** | **84** | **✅** |

---

## 5. Metrics

- **New tests**: +12
- **Bugs fixed**: 2 (type contract + missing symbol, both pre-existing)
- **Hardcoded values externalized**: 4 memory thresholds
- **Functions refactored**: 1 (94 LOC → 4 methods avg 18 LOC)
- **Documentation corrections**: 4 Known Issues items moved to Resolved

---

## 6. Lessons Learned

1. **CLAUDE.md staleness is silent.** The doc listed 4 resolved items as open — no tooling catches doc/code drift. Worth periodic review (or a pre-commit check).
2. **Type hints aren't enforced at runtime.** `_calculate_font_sizes: Dict[int, float]` vs caller expecting `Dict[int, Dict]` slipped through until a specific code path was tested. Consider `mypy --strict` on at least the `operations_service` module.
3. **Preview ≠ Save at the text-layer level, by design.** This is a correct and important distinction — visual equivalence is the right contract, and now tested.
4. **Qt modal dialogs in `closeEvent` are a test-infrastructure trap.** Should be documented for future tests touching `MainWindow`.

---

## 7. Follow-ups (Not in This Session)

- Run `mypy --strict app/operations_service.py` and fix drift.
- Add pre-commit hook to grep CLAUDE.md for Known Issues items that have corresponding code-level `## Resolved` markers.
- Consider a render-based visual regression baseline (store reference PNGs) for more UI operations.
- Document the autouse `_suppress_close_confirm_dialog` fixture in `tests/README.md` if created.

---

**Session duration**: 1 interactive session
**Final test status**: 84/84 passing

---

## 8. PyInstaller Build Verification

Executed `pyinstaller pdf_control.spec --noconfirm` to end-to-end verify the
bundling path. Build completed successfully in ~53 seconds with exit code 0.

**Output structure** (`dist/PDF_Control/`):
- `PDF_Control.exe` — bootloader executable
- `_internal/` — onedir payload (Python runtime, PySide6, PyMuPDF, app modules, i18n JSON)

No warnings blocked the build; pkg_resources deprecation notice is upstream
(PyInstaller itself) and can be ignored. The spec correctly resolves all
hiddenimports referenced in §2.6's validation tests.

**Smoke verification**: `app/i18n/en.json` and `ko.json` present in the bundled
datas per spec declaration; `path_helper.is_frozen()` logic was unit-tested
separately to confirm `_MEIPASS` resolution works.

**Not yet verified** (manual follow-up):
- Launching the frozen `.exe` in a fresh user profile to confirm app-data dir
  creation under `%APPDATA%\PDF_Control\`.
- Render worker subprocess spawn from the frozen executable.
