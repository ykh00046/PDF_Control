# Archive Index — 2026-04

## Archived Features

### 2026-04-15: long-text-narrow-area-warning

- **Path**: `long-text-narrow-area-warning/` (plan.md, design.md, analysis.md, report.md)
- **Goal**: Surface text-fit shrink/overflow warnings from Preview into status bar, history badge, and save-time guard
- **Match Rate**: 95% (design-to-implementation fidelity, all 11 File-Level changes in place)
- **Test delta**: 93 → 100 passing (+7)
- **Key finding**: Pre-existing bug — `render_page_preview` silently dropped `ApplyResult` for months; warnings existed in service layer but never reached UI
- **Closes**: Last open item in CLAUDE.md Known Issues ("Long Text in Narrow Areas")
- **Follow-up**: 3 pytest-qt UI tests (Test Matrix #5/#6/#7) deferred, non-blocking

### 2026-04-14: claude-md-drift-guard

- **Path**: `claude-md-drift-guard/` (plan.md, report.md)
- **Goal**: Pre-commit check blocking CLAUDE.md drift against `docs/_resolved.yml` registry
- **Deliverables**: `scripts/check_claude_md_drift.py`, `docs/_resolved.yml`, 8 unit tests
- **Test delta**: 84 → 92 passing (+8)

### 2026-04-14: mypy-strict-operations

- **Path**: `mypy-strict-operations/` (plan.md, report.md)
- **Goal**: Scoped mypy `--strict` on `app/operations_service.py` to block type-contract drift
- **Deliverables**: `mypy.ini` (scoped via `follow_imports=silent`), `TextMetadata` TypedDict, `tests/test_mypy.py`
- **Result**: 16 mypy errors → 0; full regression 93/93 passing

### 2026-04-14: Quality Refinement Session

- **Path**: `2026-04-14-quality-refinement/report.md`
- **Type**: Retroactive quality refinement (no plan/design/analysis — not a forward feature)
- **Test delta**: 72 → 84 passing (+12)
- **Build verification**: PyInstaller `pdf_control.spec` built successfully (exit 0, ~53s)

#### Key Findings

1. **Documentation drift** — CLAUDE.md Known Issues listed 4 already-fixed items
   (config default pollution, preview temp close, RemoveSection memory guard,
   preview-save divergence). Moved to a "Resolved" subsection with file:line
   references. No tooling currently catches this drift.

2. **Production bug in `_calculate_font_sizes`** (`app/operations_service.py`) —
   declared return type `Dict[int, float]` but caller `_insert_replacement_text`
   consumed it as `Dict[int, Dict]`, calling `.get("fontsize")`. Additionally
   imported non-existent `_calculate_estimated_fontsize` from `app.model`.
   Broke 3 smoke tests whenever `RedactReplace` used `fontsize != 0`.
   **Fix**: rewrote to return metadata dicts from `_extract_text_metadata`.

3. **Preview ≠ Save at text-layer level by design** — Preview draws white
   rectangles (non-destructive) while Save uses destructive redaction.
   `page.get_text()` extracts the preserved text layer in Preview mode.
   Visual (pixel-based) equivalence is the correct contract — now tested.

4. **Qt modal dialog in `closeEvent` is a test-infra trap** — pytest-qt
   `_close_widgets()` teardown hangs on any modified `MainWindow`. Fixed
   via autouse `QMessageBox.question` auto-Discard fixture in `conftest.py`.

#### Deliverables

- 3 new test suites (+12 tests): i18n validation, preview=save pixel parity,
  PyInstaller bundling validation.
- 1 refactor: `replace_selection()` 94 LOC → 4 methods.
- 4 hardcoded memory thresholds externalized to `config.DEFAULT_CONFIG["memory"]`.
- 2 pre-existing bugs fixed.
