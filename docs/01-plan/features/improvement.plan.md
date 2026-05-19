# Improvement Roadmap - Plan

> **Summary**: Comprehensive improvement plan for PDF Control project based on current state analysis
>
> **Author**: Claude (bkit)
> **Created**: 2026-01-30
> **Last Modified**: 2026-01-30
> **Status**: 🔄 In Progress

---

## 1. Overview & Purpose

### Objective

Transform PDF Control from "beta quality" (70% production-ready) to "production-ready" (95%+ ready) through systematic improvements in code quality, UX, testing, and packaging.

### Goals

1. **Eliminate Critical Bugs**: Fix config pollution, resource leaks, preview-save divergence
2. **Enhance UX**: Add user feedback for edge cases, improve history panel
3. **Increase Test Coverage**: From ~30% to 70%+
4. **Enable Distribution**: Create working PyInstaller builds
5. **Establish Quality Process**: Ongoing PDCA cycle for future features

---

## 2. Scope

### In Scope

✅ Code refactoring (preview-save unification, config management)
✅ UX enhancements (fixed font option, status messages, warnings)
✅ Testing improvements (edge cases, equivalence tests, i18n validation)
✅ Packaging setup (PyInstaller spec, path helpers)
✅ Documentation (migrate legacy docs, update README)

### Out of Scope

❌ New major features (focus on quality, not expansion)
❌ Platform support beyond Windows (future consideration)
❌ Performance optimization (acceptable for current use cases)
❌ UI redesign (current UI is functional)

---

## 3. Improvement Phases

## Phase 1: Immediate Fixes (Priority: 🔴 Critical)

**Timeline**: 1-2 days
**Effort**: 4-6 hours

### Objectives

- Fix bugs that can cause data corruption or confusing behavior
- Stabilize foundation before larger refactoring

### Tasks

#### 1.1 Config Default Pollution Fix

**File**: `app/config.py`
**Issue**: Mutable `DEFAULT_CONFIG` dict can be polluted during runtime
**Solution**:

```python
import copy

def get_default_config():
    """Return deep copy to prevent pollution."""
    return copy.deepcopy(DEFAULT_CONFIG)
```

**Impact**: Prevents test pollution, ensures clean defaults
**Effort**: 30 min

#### 1.2 Preview Temp Document Cleanup

**File**: `app/viewer.py::RenderWorker.run()`
**Issue**: `temp_doc` not closed after rendering
**Solution**:

```python
try:
    temp_doc = fitz.open(temp_path)
    # ... render ...
finally:
    if temp_doc:
        temp_doc.close()
```

**Impact**: Prevents file handle and memory leaks
**Effort**: 30 min

#### 1.3 Test Fixture Cleanup

**File**: `tests/test_ui.py`
**Issue**: Tests depend on external `sample.pdf` file
**Solution**: Create fixture that generates temp PDF programmatically

```python
@pytest.fixture
def sample_pdf(tmp_path):
    pdf_path = tmp_path / "test.pdf"
    # Generate simple PDF with PyMuPDF
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Test text")
    doc.save(pdf_path)
    doc.close()
    return pdf_path
```

**Impact**: Makes tests portable and reliable
**Effort**: 1 hour

#### 1.4 RemoveSection Memory Guard

**File**: `app/model.py::RemoveSectionOp`
**Issue**: No memory estimation before large image conversion
**Solution**:

```python
def estimate_memory_mb(self, page):
    """Estimate memory needed for image conversion."""
    rect = page.rect
    dpi = self.dpi or 150
    width_px = int(rect.width * dpi / 72)
    height_px = int(rect.height * dpi / 72)
    # RGB + alpha = 4 bytes per pixel
    mb = (width_px * height_px * 4) / (1024 * 1024)
    return mb

# Before conversion:
if self.estimate_memory_mb(page) > 500:  # 500MB threshold
    logger.warning("Large memory usage expected, capping DPI")
    self.dpi = min(self.dpi or 150, 150)
```

**Impact**: Prevents app crashes on large pages
**Effort**: 1-2 hours

### Deliverables

- [ ] Config deepcopy implemented and tested
- [ ] Temp doc cleanup added with try-finally
- [ ] Test fixtures refactored to remove file dependencies
- [ ] Memory guard added for RemoveSection

### Success Criteria

- All tests pass without external files
- No resource leak warnings in logs
- Large page removal (e.g., A0 size) doesn't crash

---

## Phase 2: Core Refactoring (Priority: 🔴 High)

**Timeline**: 1 week
**Effort**: 12-16 hours

### Objectives

- Unify preview and save logic to eliminate divergence
- Make code more testable and maintainable

### Tasks

#### 2.1 Extract Operation Applicator Service

**Files**: `app/model.py`, `app/viewer.py`
**Current Problem**:

- `DocumentSession.apply_operations_to_page()` handles save
- `RenderWorker.run()` duplicates logic for preview
- Divergence causes preview ≠ save

**Solution**: Create `app/operations_service.py`

```python
class OperationApplicator:
    """Pure function service for applying operations to pages."""

    def __init__(self, font_manager, logger, config):
        self.font_manager = font_manager
        self.logger = logger
        self.config = config

    def apply_operations(self, page, operations):
        """Apply list of operations to a page.

        Used by both save (DocumentSession) and preview (RenderWorker).
        """
        for op in operations:
            if isinstance(op, DeleteTextOp):
                self._apply_delete(page, op)
            elif isinstance(op, ReplaceTextOp):
                self._apply_replace(page, op)
            # ...

    def _apply_replace(self, page, op):
        """Common text replacement logic."""
        # Extract from current code
        # Use width-based font sizing (binary search)
        # Left-align, expand right/bottom
        pass
```

**Refactor Impact**:

- `DocumentSession.apply_operations_to_page()` → calls `applicator.apply_operations()`
- `RenderWorker.run()` → calls same `applicator.apply_operations()`
- Single source of truth, guaranteed preview = save

**Effort**: 6-8 hours
**Risk**: Medium (large refactor, needs thorough testing)

#### 2.2 Add Operation Validation Layer

**File**: `app/model.py`
**Solution**: Add `validate()` method to all Operation classes

```python
class ReplaceTextOp(Operation):
    def validate(self):
        """Validate operation before execution."""
        if not self.new_text:
            raise ValueError("Replacement text cannot be empty")
        if not self.rect:
            raise ValueError("Selection rect cannot be None")
        # ...
```

**Impact**: Catch errors early, better error messages
**Effort**: 2-3 hours

#### 2.3 Inject Dependencies (Remove Singletons)

**Files**: `app/logger.py`, `app/config.py`, `app/fonts.py`
**Current Problem**: Singletons make testing hard (can't isolate)
**Solution**: Create wrapper classes that allow injection

```python
# app/context.py
class AppContext:
    """Dependency container for testing."""
    def __init__(self, logger=None, config=None, font_manager=None):
        self.logger = logger or Logger()
        self.config = config or ConfigManager()
        self.font_manager = font_manager or FontManager()

# In tests:
context = AppContext(logger=MockLogger())
session = DocumentSession(context=context)
```

**Impact**: Easier unit testing, better separation of concerns
**Effort**: 3-4 hours

### Deliverables

- [ ] `OperationApplicator` service created and tested
- [ ] `DocumentSession` and `RenderWorker` refactored to use service
- [ ] Operation validation layer added
- [ ] Dependency injection implemented

### Success Criteria

- Preview and save produce identical results (verified by test)
- All existing tests still pass
- New unit tests for `OperationApplicator` added

---

## Phase 3: UX Enhancements (Priority: 🟡 Medium)

**Timeline**: 4-5 days
**Effort**: 8-12 hours

### Tasks

#### 3.1 Fixed Font Size Option

**Files**: `app/batch_replace_dialog.py`, `app/ui.py` (replace dialog)
**Feature**: Add checkbox "Use fixed font size" with spinbox (8-12pt)
**Impact**: Users can avoid auto-scaling for consistent appearance
**Effort**: 3-4 hours

**Design**:

```
Replace Dialog:
┌────────────────────────────┐
│ New text: [____________]   │
│ Font: [NanumGothic ▼]      │
│ ☑ Use fixed font size      │
│   Size: [10] pt            │
│              [Replace]     │
└────────────────────────────┘
```

#### 3.2 Status Bar Warnings

**File**: `app/ui.py`
**Feature**: Show warnings in status bar when:

- Text auto-scaled below 10pt
- Text failed to fit even at 8pt
- Operation affected multiple pages

**Example**: `⚠️ Text auto-scaled to 9pt to fit narrow area`
**Effort**: 2 hours

#### 3.3 History Panel Metadata

**File**: `app/ui.py`
**Feature**: Show more info in history items:

- Timestamp
- Font size used (if replaced)
- "Scaled" badge if auto-scaling occurred
- Page number

**Effort**: 2-3 hours

#### 3.4 Crop/Remove Preview

**Files**: `app/crop_dialog.py`, `app/remove_section_dialog.py`
**Feature**: Show estimated result before confirming:

- New page height in mm
- Estimated file size change
- Warning if rotation detected

**Effort**: 2-3 hours

### Deliverables

- [ ] Fixed font size option implemented in both dialogs
- [ ] Status bar warnings for scaling/failure
- [ ] History panel shows timestamp + metadata
- [ ] Crop/Remove dialogs show preview info

### Success Criteria

- Users can replace text with consistent font size
- Users are warned before text disappears
- History provides full context for debugging

---

## Phase 4: Testing & i18n (Priority: 🟡 Medium)

**Timeline**: 3-4 days
**Effort**: 8-10 hours

### Tasks

#### 4.1 i18n Validation Script

**File**: `scripts/validate_i18n.py`
**Features**:

- Check all language files have same keys
- Check placeholder counts match (`{0}`, `{1}`)
- Check for empty values
- Report missing/extra keys

**Integration**: Add to pytest as `test_i18n_validity.py`
**Effort**: 2-3 hours

#### 4.2 Preview-Save Equivalence Tests

**File**: `tests/test_equivalence.py`
**Features**:

```python
def test_preview_matches_save(sample_pdf):
    """Verify preview rendering matches saved output."""
    # 1. Apply operations
    # 2. Generate preview image
    # 3. Save to temp file
    # 4. Re-open and render saved file
    # 5. Compare image hashes or text extraction
    assert preview_hash == saved_hash
```

**Effort**: 3-4 hours

#### 4.3 Edge Case Tests

**File**: `tests/test_edge_cases.py`
**Scenarios**:

- Very long text in narrow rect
- Text with special characters (emoji, CJK)
- Empty replacement text
- Replace on rotated page
- Multiple operations on same text

**Effort**: 3-4 hours

### Deliverables

- [ ] i18n validation script with tests
- [ ] Preview-save equivalence test suite
- [ ] Edge case test coverage

### Success Criteria

- i18n validation passes for en/ko
- All preview-save tests pass
- Test coverage reaches 70%+

---

## Phase 5: Packaging (Priority: 🟢 Low)

**Timeline**: 1 week
**Effort**: 8-12 hours

### Tasks

#### 5.1 Path Helper Implementation

**File**: `app/path_helpers.py`

```python
import sys
import os

def get_app_dir():
    """Get application directory (frozen or dev)."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

def get_data_path(relative_path):
    """Get path to data file (i18n, icons, etc.)."""
    return os.path.join(get_app_dir(), relative_path)
```

**Effort**: 1 hour

#### 5.2 PyInstaller Spec Creation

**File**: `PDF_Control.spec`
**Features**:

- Bundle i18n files from `app/i18n/`
- Exclude test files
- Include PySide6 plugins
- Set UTF-8 encoding

**Effort**: 3-4 hours (with testing)

#### 5.3 Build Requirements Separation

**File**: `requirements-build.txt`

```
pyinstaller==6.3.0
# Frozen dependencies
PySide6==6.6.1
PyMuPDF==1.23.9
Pillow==10.1.0
```

**Effort**: 30 min

#### 5.4 Build Testing

**Tasks**:

- Test on clean Windows VM
- Verify i18n files loaded
- Verify fonts work
- Test all features in frozen build

**Effort**: 4-6 hours

### Deliverables

- [ ] Path helpers implemented and used throughout app
- [ ] PyInstaller spec created and tested
- [ ] Build requirements separated
- [ ] Frozen exe tested on clean system

### Success Criteria

- `PDF_Control.exe` runs on Windows without Python installed
- All features work in frozen build
- i18n switching works correctly

---

## 4. Migration Plan for Legacy Documents

### Current Legacy Documents

1. `PROJECT_STATUS.md` → Covered by `current-state.analysis.md`
2. `IMPROVEMENT_PLAN.md` → Covered by this document
3. `NEXT_STEPS.md` → Will create `next-steps.plan.md`

### Migration Strategy

1. **Keep Legacy Docs**: Don't delete immediately (reference value)
2. **Add Deprecation Notice**: At top of each legacy doc:
   ```markdown
   > **⚠️ DEPRECATED**: This document has been migrated to the new PDCA structure.
   > See: `docs/_INDEX.md` for current documentation.
   ```
3. **Update README**: Point to `docs/_INDEX.md` as entry point
4. **Archive Later**: After 1-2 months, move to `docs/archive/` folder

---

## 5. Roadmap Timeline

### Week 1 (Current)

- [x] **Day 1**: bkit setup, PDCA structure, analysis
- [ ] **Day 2-3**: Phase 1 (Immediate Fixes)

### Week 2

- [ ] **Day 1-3**: Phase 2 (Core Refactoring)
- [ ] **Day 4-5**: Phase 3 (UX Enhancements) - start

### Week 3

- [ ] **Day 1-2**: Phase 3 (UX Enhancements) - complete
- [ ] **Day 3-5**: Phase 4 (Testing & i18n)

### Week 4

- [ ] **Day 1-3**: Phase 5 (Packaging)
- [ ] **Day 4-5**: Integration testing, documentation

### Optional Week 5-6

- [ ] Advanced features (from `NEXT_STEPS.md` backlog)
- [ ] Performance optimization
- [ ] Additional platform testing

---

## 6. Effort Summary

| Phase                    | Tasks  | Hours     | Priority    |
| ------------------------ | ------ | --------- | ----------- |
| Phase 1: Immediate Fixes | 4      | 4-6       | 🔴 Critical |
| Phase 2: Core Refactor   | 3      | 12-16     | 🔴 High     |
| Phase 3: UX Enhancements | 4      | 8-12      | 🟡 Medium   |
| Phase 4: Testing & i18n  | 3      | 8-10      | 🟡 Medium   |
| Phase 5: Packaging       | 4      | 8-12      | 🟢 Low      |
| **Total**                | **18** | **40-56** | -           |

**Estimated Calendar Time**: 3-4 weeks (part-time) or 1-2 weeks (full-time)

---

## 7. Risk Management

### Technical Risks

#### R-1: Preview-Save Refactor Breaks Existing Functionality

**Probability**: Medium
**Impact**: High
**Mitigation**:

- Comprehensive test suite before refactoring
- Incremental refactor (extract, then refactor, then remove old)
- Keep old code commented out until fully verified

#### R-2: PyInstaller Hidden Import Issues

**Probability**: High (common with Qt)
**Impact**: Medium
**Mitigation**:

- Test early and often
- Use `--debug` flag to identify missing imports
- Consult PyInstaller + PySide6 community

#### R-3: Scope Creep During Implementation

**Probability**: Medium
**Impact**: Medium
**Mitigation**:

- Strict adherence to phase goals
- Document "nice-to-have" items in backlog, don't implement immediately

---

## 8. Success Metrics

### Code Quality

- [ ] DRY violations reduced to 0 critical (preview-save unified)
- [ ] All functions <50 lines (or well-justified exceptions)
- [ ] No hardcoded values (all in config or constants)
- [ ] Lint warnings <10 (pylint or flake8)

### Testing

- [ ] Test coverage >70%
- [ ] All edge case tests pass
- [ ] Preview-save equivalence verified
- [ ] i18n validation automated

### UX

- [ ] All edge cases show user feedback
- [ ] Status bar actively used
- [ ] History panel shows full metadata
- [ ] User testing passes (if available)

### Packaging

- [ ] Frozen exe builds successfully
- [ ] Exe runs on clean Windows VM
- [ ] Exe file size <100MB
- [ ] i18n, fonts work in frozen build

---

## 9. Post-Improvement Plans

### Backlog (Low Priority)

From `NEXT_STEPS.md`:

1. Span/line overlay selection UI (web editor feel)
2. Replacement templates/favorites
3. Operation summary export (log all changes)
4. Multi-page batch operations
5. Plugin system for custom operations

### Platform Expansion (Future)

- macOS support (font management, testing)
- Linux support (font management, testing)
- Web version (PyScript or WASM?)

### Performance (If Needed)

- Lazy rendering (only visible pages)
- Operation batching (reduce redraws)
- Caching improvements

---

## 10. Related Documents

- **CLAUDE.md**: [../../../CLAUDE.md](../../../CLAUDE.md)
- **Index**: [../../\_INDEX.md](../../_INDEX.md)
- **Analysis**: [../../03-analysis/features/current-state.analysis.md](../../03-analysis/features/current-state.analysis.md)
- **Project Status Plan**: [project-status.plan.md](project-status.plan.md)

---

## Version History

| Version | Date       | Changes                     | Author        |
| ------- | ---------- | --------------------------- | ------------- |
| 1.0     | 2026-01-30 | Initial improvement roadmap | Claude (bkit) |

---

## Next Actions

1. Review this plan with user
2. Get approval on phase priorities
3. Create detailed design documents for Phase 2 (core refactor)
4. Begin Phase 1 implementation
