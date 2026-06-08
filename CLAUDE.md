# CLAUDE.md

> **Summary**: PDF Control - Desktop PDF editing application with text selection, deletion, replacement, cropping, and section imaging capabilities
>
> **Project Level**: Starter
> **Tech Stack**: PySide6 + PyMuPDF
> **Status**: Active Development
> **Created**: 2025-12-16
> **Last Modified**: 2026-01-30

---

## Project Overview

PDF Control is a desktop application that enables users to:

- Select and manipulate text in PDF files (delete, replace)
- Crop and remove sections with image conversion
- Batch find/replace operations
- Undo/redo history management
- Multi-language support (en/ko)

### Key Features

- PDF open/save with preview
- Text selection-based operations (delete, replace)
- Custom and system font support
- Batch find/replace with regex
- History panel with undo/redo
- Viewer with zoom/pan controls
- Crop/section removal with image conversion
- i18n support (English/Korean)

---

## Project Level: Starter

### Detection Criteria Met

- Single desktop application
- No backend services
- No infrastructure (terraform, k8s, docker-compose)
- No monorepo structure
- Simple dependency management (requirements.txt)

### Level-Specific Rules

- **Explanation**: Friendly, detailed comments for beginners
- **Code Comments**: Detailed explanations for complex logic
- **Error Handling**: Step-by-step user guidance
- **Documentation**: Simple, practical guides

---

## Tech Stack

### Core

- **PySide6**: Desktop UI framework (Qt for Python)
- **PyMuPDF (fitz)**: PDF manipulation library
- **Pillow**: Image processing

### Development

- **pytest**: Testing framework
- **pytest-qt**: Qt-specific testing utilities

### Build/Deployment

- **PyInstaller**: Executable packaging

---

## Project Structure

```
PDF_Control/
├── main.py                    # Application entry point
├── requirements.txt           # Python dependencies
├── config.json               # Application configuration
├── app/                      # Main application package
│   ├── ui.py                # Main window UI
│   ├── viewer.py            # PDF viewer widget
│   ├── model.py             # Document session & operations
│   ├── controller.py        # Application controller
│   ├── config.py            # Configuration management
│   ├── fonts.py             # Font management
│   ├── logger.py            # Logging utilities
│   ├── i18n.py             # Internationalization
│   ├── i18n/               # Translation files
│   │   ├── en.json
│   │   └── ko.json
│   ├── batch_replace_dialog.py
│   ├── crop_dialog.py
│   └── remove_section_dialog.py
├── tests/                    # Test suite
├── .appdata/                 # Dev-only runtime config/log output
├── build/                    # PyInstaller intermediate output
├── dist/                     # Frozen build output
└── logs/                     # Test/review scratch output
```

## Source Boundary

- Source of truth: `app/`, `tests/`, `scripts/`, `docs/`, and top-level project files
- Generated runtime/test/build output: `.appdata/`, `.pytest_cache/`, `.pytest_tmp/`, `build/`, `dist/`, `logs/`, `__pycache__/`
- Development logs/config should land in `.appdata/`
- Frozen build logs/config should land in the platform app-data directory

---

## Development Rules

### Code Quality Standards

#### DRY (Don't Repeat Yourself)

- Extract to common function on 2nd use
- Reuse existing utilities in `app/` modules

#### SRP (Single Responsibility Principle)

- One function, one responsibility
- Keep functions focused and testable

#### No Hardcoding

- Use `config.py` for configuration
- Use i18n for all user-facing strings

#### Extensibility

- Write in generalized patterns
- Design for future enhancements

### Refactoring Triggers

- Same code appears 2nd time → Extract to function
- Function exceeds 50 lines → Split into smaller functions
- if-else nests 3+ levels → Simplify logic
- Same parameters passed to multiple functions → Create config object

---

## Naming Conventions

### Python Files

- `snake_case.py` for modules (e.g., `batch_replace_dialog.py`)
- `PascalCase` for classes (e.g., `MainWindow`, `DocumentSession`)
- `snake_case` for functions/methods (e.g., `apply_operations_to_page`)

### Constants

- `UPPER_SNAKE_CASE` for constants (e.g., `DEFAULT_CONFIG`)

### Variables

- Descriptive names (e.g., `temp_doc`, `render_worker`)
- Avoid single letters except for common iterators (i, j)

---

## Testing Strategy

### Current Coverage

- Basic smoke tests
- Undo/redo functionality
- Remove section operations
- Async rendering

### Test Organization

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── test_ui.py              # UI integration tests
├── test_model.py           # Document session tests
└── test_operations.py      # Operation logic tests
```

### Testing Guidelines

- Use `pytest-qt` for UI tests
- Use fixtures for PDF creation (avoid file dependencies)
- Test preview=save equivalence
- Test i18n key completeness

---

## Known Issues & Risks

### Current Issues

_None currently tracked. Open a new item here if one surfaces._

### Resolved (2026-04-14 review)

- ~~Config default pollution~~: `_default_config()` uses `copy.deepcopy` (`app/config.py:37-39`)
- ~~Preview temp document close leak~~: `finally` block ensures close (`app/pdf_engine.py:85-113`)
- ~~RemoveSection memory guard~~: DPI auto-cap + memory budget (`app/model.py:163-264`)
- ~~Preview-Save logic divergence~~: Unified via `ApplyMode` enum (`app/operations_service.py:65-143`)

### Resolved (2026-04-15)

- ~~Long Text in Narrow Areas~~: Structured `OpWarning` surfaces shrink/overflow into status bar, history badge, and save-time guard (`app/operations_service.py:33-60`, `app/ui.py:780-822`)

### Added (2026-06-08, pdf-encryption PDCA)

- **Password protection + permissions**: New pure, mypy-strict `app/encryption.py` (`EncryptionSettings`) builds AES-256 `Document.save` kwargs (user/owner passwords + print/copy/modify/annotate permission bits) with an `is_active()` guard so an unprotected policy saves normally. Threaded through `pdf_engine.save_document_copy` → `document_session.save_document` → `controller.save_document` as an optional `encryption=` kwarg (100% backward compatible). After an encrypted save the session re-binds via `authenticate(unlock_password())`. UI: `app/encryption_dialog.py` + File → "Encrypt & Save As…" (Ctrl+Alt+S); shared save logic extracted to `file_handlers._commit_save`. Strict gate expanded to `app.encryption`. 191 tests pass.

### Added (2026-06-02, page-merge-split PDCA)

- **Document split + batch merge**: New `app/page_split.py` (pure, mypy-strict) provides `SplitMode` (SINGLE / EVERY_N / RANGES), `parse_page_ranges`, and `compute_split_groups`. `DocumentSession.split_document` writes one PDF per page-index group (read-only, source unchanged — same contract as `extract_pages`). `DocumentSession.merge_pdfs` inserts several PDFs in order; `merge_pdf` now delegates to it (backward-compatible). UI: `app/split_dialog.py` + a "Split" action in `PageManagerDialog`; merge now accepts multiple files. 177 tests pass.

### Resolved (2026-06-02, text-wrap-replace PDCA)

- ~~Long text shrunk to unreadable size / dropped~~: Replacement text that overflows one line now **word-wraps onto multiple lines** by expanding the box height within the page bound, preserving the intended font size. Font shrinking is now a fallback only for unbreakable words wider than the box or insufficient vertical room. New `text.wrapped` (info) warning surfaces in status bar + history badge. Controlled by `TEXT_WRAP_*` constants in `app/config.py`; core logic in `app/operations/applicator.py::_wrap_line_count` + `_insert_text_with_autofit`. 146 tests pass.

### Resolved (2026-06-02, r2-quality-fixes PDCA)

- ~~`get_text_length` API broken~~: PyMuPDF 1.26+ removed `Page.get_text_length`; replaced with `fitz.Font.text_length()` in `app/operations/applicator.py`. Recovered 11 failing tests.
- ~~autofit shrink warning gap~~: autofit-driven font shrink now emits `text.shrunk` (previously only the fallback path did).
- ~~mypy strict scope too narrow~~: gate expanded to `config`, `logger`, `path_helper`, `text_utils`, `text_metadata`, `fonts` (all 0 strict errors), enforced by `tests/test_mypy.py::test_strict_leaf_modules_pass_mypy`. Deferred: `document_session`, `model`, `pdf_engine` → `typing-legacy-core` cycle.

### Risks

- Packaging with PyInstaller: Relative path/data bundling not yet tested
- Memory usage: Large section removal with high DPI - mitigated via auto-cap, monitor logs

---

## PDCA Document Structure

### Current Status

- Legacy documents exist: `PROJECT_STATUS.md`, `IMPROVEMENT_PLAN.md`, `NEXT_STEPS.md`
- **Migration needed**: Reorganize into bkit-standard PDCA docs

### Target Structure

```
docs/
├── _INDEX.md                # Document index
├── 01-plan/
│   └── features/
│       └── {feature}.plan.md
├── 02-design/
│   └── features/
│       └── {feature}.design.md
├── 03-analysis/
│   └── features/
│       └── {feature}.analysis.md
└── 04-report/
    └── features/
        └── {feature}.report.md
```

---

## Language & i18n

### Supported Languages

- English (en)
- Korean (ko)

### i18n Rules

- All UI strings must use i18n keys
- Translation files: `app/i18n/en.json`, `app/i18n/ko.json`
- Validation: Check for missing keys, placeholder mismatches

---

## Logging

### Log Levels

- **DEBUG**: Detailed flow (font size calculation, operations)
- **INFO**: User actions (open, save, replace)
- **WARNING**: Non-critical issues (text scaling, preview mismatch)
- **ERROR**: Critical failures (save error, render crash)

### Log Location

- `logs/` directory
- Timestamped files for each session

---

## Version Control

### Commit Message Format

```
<type>: <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

Example:

```
feat: Add fixed font size option for text replacement

- Add checkbox in Replace dialog for fixed font size
- Prevent auto-scaling when option is enabled
- Update i18n strings for new option

Closes #12
```

---

## Next Development Phases

Based on current status and improvement plan:

1. **Phase 1: Immediate Fixes** (Priority: High)
   - Fix config default pollution (deep copy)
   - Close preview temp documents properly
   - Add memory guards for RemoveSection

2. **Phase 2: Core Refactor** (Priority: High)
   - Unify preview-save logic
   - Extract operation application to pure function
   - Add operation validation

3. **Phase 3: UX Enhancement** (Priority: Medium)
   - Add fixed font size option
   - Improve status messages
   - Enhance history panel

4. **Phase 4: Testing & i18n** (Priority: Medium)
   - Add preview=save equivalence tests
   - Create i18n validation script
   - Add long text/narrow area tests

5. **Phase 5: Packaging** (Priority: Low)
   - Create PyInstaller spec
   - Add path helpers for frozen/unfrozen
   - Separate build requirements

---

## References

### External Documentation

- [PySide6 Documentation](https://doc.qt.io/qtforpython/)
- [PyMuPDF Documentation](https://pymupdf.readthedocs.io/)

### Internal Documents

- `PROJECT_STATUS.md`: Current status (legacy, to be migrated)
- `IMPROVEMENT_PLAN.md`: Improvement roadmap (legacy, to be migrated)
- `NEXT_STEPS.md`: Next action items (legacy, to be migrated)
