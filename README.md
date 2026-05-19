# PDF Control

> **Desktop PDF editing application with text selection, deletion, replacement, and advanced manipulation capabilities**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-6.0+-green.svg)](https://doc.qt.io/qtforpython/)
[![PyMuPDF](https://img.shields.io/badge/PyMuPDF-1.23+-orange.svg)](https://pymupdf.readthedocs.io/)
[![License](https://img.shields.io/badge/License-TBD-lightgrey.svg)](#-license)

---

## ✨ Features

### Core Functionality

- 📄 **PDF Open/Save** - Load and save PDF files with full fidelity
- ✂️ **Text Selection & Deletion** - Select and remove text from PDFs
- 🔄 **Text Replacement** - Replace selected text with custom content
- 🔍 **Batch Find/Replace** - Search and replace across entire documents
- ↩️ **Undo/Redo** - Full operation history with unlimited undo/redo
- 📋 **History Panel** - Visual timeline of all operations
- 🖼️ **Section Removal** - Convert sections to images and remove from PDF
- ✂️ **Crop Pages** - Crop PDF pages with visual selection
- 🔍 **Zoom & Pan Viewer** - Smooth PDF viewing with zoom controls
- 🌍 **Multi-language** - English and Korean localization

### Advanced Features

- 🎨 **Custom & System Fonts** - Use any installed font for replacements
- 📏 **Smart Font Sizing** - Automatic font size adjustment to fit areas
- 📊 **Detailed Logging** - Comprehensive operation logs for debugging
- ⚙️ **Configurable Settings** - Persistent user preferences

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Windows OS (font management is Windows-specific)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd PDF_Control

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### First Run

1. Launch the application: `python main.py`
2. Open a PDF: **File → Open** (or `Ctrl+O`)
3. Select text by clicking and dragging
4. Choose an action:
   - **Edit → Delete Text** to remove selected text
   - **Edit → Replace Text** to replace with new content
   - **Edit → Batch Replace** for find/replace operations
5. Save your changes: **File → Save As** (or `Ctrl+S`)

---

## 📖 Documentation

### 📚 Main Documentation

- **[CLAUDE.md](CLAUDE.md)** - Project configuration, rules, and conventions
- **[docs/\_INDEX.md](docs/_INDEX.md)** - Complete documentation index

### 📋 PDCA Documents (bkit Standard)

#### Analysis

- [Current State Analysis](docs/03-analysis/features/current-state.analysis.md) - Comprehensive project status

#### Planning

- [Project Status Plan](docs/01-plan/features/project-status.plan.md) - Analysis planning framework
- [Improvement Roadmap](docs/01-plan/features/improvement.plan.md) - Systematic improvement plan
- [Next Steps](docs/01-plan/features/next-steps.plan.md) - Actionable next steps

#### Legacy Documents (Deprecated)

> ⚠️ These documents are being migrated to the new PDCA structure. See `docs/_INDEX.md` for current documentation.

- ~~`PROJECT_STATUS.md`~~ → [current-state.analysis.md](docs/03-analysis/features/current-state.analysis.md)
- ~~`IMPROVEMENT_PLAN.md`~~ → [improvement.plan.md](docs/01-plan/features/improvement.plan.md)
- ~~`NEXT_STEPS.md`~~ → [next-steps.plan.md](docs/01-plan/features/next-steps.plan.md)

---

## 🏗️ Project Structure

```
PDF_Control/
├── main.py                      # Application entry point
├── requirements.txt             # Python dependencies
├── config.json                  # Application configuration
├── CLAUDE.md                    # Project configuration (bkit)
├── README.md                    # This file
│
├── app/                         # Main application package
│   ├── ui.py                   # Main window UI
│   ├── viewer.py               # PDF viewer widget
│   ├── model.py                # Document session & operations
│   ├── controller.py           # Application controller
│   ├── config.py               # Configuration management
│   ├── fonts.py                # Font management (Windows)
│   ├── logger.py               # Logging utilities
│   ├── i18n.py                 # Internationalization
│   ├── i18n/                   # Translation files
│   │   ├── en.json            # English
│   │   └── ko.json            # Korean
│   ├── batch_replace_dialog.py
│   ├── crop_dialog.py
│   └── remove_section_dialog.py
│
├── tests/                       # Test suite
│   ├── conftest.py             # Shared fixtures
│   ├── test_ui.py              # UI integration tests
│   ├── test_model.py           # Document session tests
│   └── test_operations.py      # Operation logic tests
│
├── docs/                        # PDCA documentation (bkit)
│   ├── _INDEX.md               # Document index
│   ├── 01-plan/                # Planning phase
│   ├── 02-design/              # Design phase
│   ├── 03-analysis/            # Analysis phase
│   └── 04-report/              # Report phase
│
├── .appdata/                    # Dev-only runtime config/log output
├── build/                       # PyInstaller intermediate output
├── dist/                        # Frozen build output
└── logs/                        # Test/review scratch output (generated)
```

---

## Repository Boundaries

- Product source: `app/`, `tests/`, `scripts/`, `docs/`, and top-level project files
- Dev runtime output: `.appdata/`
- Frozen runtime output: `%APPDATA%\\PDF_Control\\` on Windows
- Generated artifacts: `build/`, `dist/`, `logs/`, `.pytest_cache/`, `.pytest_tmp/`, `__pycache__/`

See [docs/04-report/source-boundary.report.md](docs/04-report/source-boundary.report.md) for the reviewed boundary rules.

---

## 🧪 Development

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_ui.py -v

# With coverage report
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html  # View coverage report
```

### Code Quality

```bash
# Lint check
flake8 app/ --max-line-length=120

# Type checking gate for the strict operations pipeline
python -m mypy app/operations_service.py
```

### i18n Validation

```bash
# Validate translation files
python tests/validate_i18n.py
```

---

## 🔧 Technology Stack

### Core

- **[PySide6](https://doc.qt.io/qtforpython/)** - Qt for Python desktop framework
- **[PyMuPDF](https://pymupdf.readthedocs.io/)** - PDF manipulation library (fitz)
- **[Pillow](https://pillow.readthedocs.io/)** - Image processing

### Development

- **[pytest](https://pytest.org/)** - Testing framework
- **[pytest-qt](https://pytest-qt.readthedocs.io/)** - Qt-specific testing

### Build

- **[PyInstaller](https://pyinstaller.org/)** - Windows onedir packaging

---

## 📊 Project Status

### Current Version: **Beta** (v0.9)

**Maturity Level**: ~70% production-ready

### ✅ Completed Features

- All core functionality implemented
- Multi-language support (en/ko)
- Basic test coverage (~30%)
- Operation history with undo/redo
- Logging infrastructure

### 🚧 In Progress

- PDCA documentation migration (🔄 Active)
- Code quality improvements
- Test coverage expansion (target: 70%+)

### 📋 Roadmap to v1.0 (4-6 weeks)

1. **Phase 1: Immediate Fixes** (Week 1)
   - Config default pollution fix
   - Resource leak fixes
   - Test fixture improvements

2. **Phase 2: Core Refactoring** (Week 1-2)
   - Unify preview-save logic
   - Extract operation applicator service
   - Dependency injection for testability

3. **Phase 3: UX Enhancements** (Week 2-3)
   - Fixed font size option
   - Status bar warnings for edge cases
   - Enhanced history panel

4. **Phase 4: Testing & i18n** (Week 3)
   - Increase test coverage to 70%+
   - i18n validation automation
   - Preview-save equivalence tests

5. **Phase 5: Packaging** (Week 4)
   - Onedir packaging for subprocess render worker
   - Frozen build validation
   - Distribution preparation

**See**: [Improvement Roadmap](docs/01-plan/features/improvement.plan.md) for details

---

## 🐛 Known Issues

### Critical

- **Long text in narrow areas** may fail to fit even at minimum font size (8pt)
  - **Workaround**: Widen selection area or use shorter text
  - **Fix planned**: Phase 3 (fixed font size option + user warnings)

### Medium

- **Preview-save divergence**: Preview and save use slightly different code paths
  - **Impact**: Rare cases where preview doesn't match saved result
  - **Fix planned**: Phase 2 (core refactoring)

### Low

- **Memory usage**: Large section removal with high DPI can consume excessive memory
  - **Fix planned**: Phase 1 (memory guard implementation)

**See**: [Current State Analysis](docs/03-analysis/features/current-state.analysis.md) for complete list

---

## 🤝 Contributing

This project follows **AI-Native Development** using the **bkit** methodology:

### Development Workflow

1. **Plan** → Create plan document in `docs/01-plan/features/`
2. **Design** → Create design document in `docs/02-design/features/`
3. **Implement** → Code following `CLAUDE.md` conventions
4. **Analyze** → Gap analysis in `docs/03-analysis/features/`
5. **Report** → Completion report in `docs/04-report/features/`

### Coding Standards

- Follow `CLAUDE.md` conventions
- DRY principle (extract on 2nd use)
- SRP (single responsibility per function)
- No hardcoded values (use config)
- All UI strings through i18n

**See**: [CLAUDE.md](CLAUDE.md) for complete development rules

---

## 📄 License

Repository licensing has not been finalized yet.

Before external distribution, confirm:

- the repository's own license file and notice text
- the distribution model for the PyMuPDF dependency
- whether closed-source distribution requires a commercial licensing path

See [docs/RELEASE.md](docs/RELEASE.md) for the release checklist and distribution gates.

---

## 🙏 Acknowledgments

- **PySide6 Team** - Qt for Python framework
- **PyMuPDF Team** - Excellent PDF manipulation library
- **bkit Community** - AI-Native development methodology

---

## 📞 Support

### Documentation

- Start here: [docs/\_INDEX.md](docs/_INDEX.md)
- Configuration: [CLAUDE.md](CLAUDE.md)
- Analysis: [Current State Analysis](docs/03-analysis/features/current-state.analysis.md)

### Issues

- Report bugs via GitHub Issues (if repository is public)
- Include relevant log files from `.appdata/logs/` in development or `%APPDATA%\\PDF_Control\\logs` in frozen builds
- Describe steps to reproduce

### Development

- Follow PDCA workflow documented in `docs/`
- Consult `CLAUDE.md` for coding standards
- Run tests before submitting changes

---

## 🗺️ Changelog

### [Unreleased]

- Added bkit PDCA documentation structure
- Created comprehensive project analysis
- Established improvement roadmap
- Added subprocess-based preview rendering and a Windows onedir packaging path

**See**: [CHANGELOG.md](CHANGELOG.md) for the current release log.

### [0.9.0] - 2025-12-16

- Text replacement with smart font sizing
- UX improvements (status bar, history panel)
- Config deep copy fix
- RemoveSection memory guard
- Test fixture cleanup

### [0.8.0] - Earlier

- Initial feature complete version
- All core functionality implemented
- Basic test coverage

**See**: `CHANGELOG.md` (to be created) for complete version history

---

**Last Updated**: 2026-01-30
**Project Level**: Starter (bkit)
**Status**: Active Development 🚧
