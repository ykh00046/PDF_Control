# Next Steps - Action Items

> **Summary**: Concrete, actionable next steps for PDF Control project improvement
>
> **Author**: Claude (bkit)
> **Created**: 2026-01-30
> **Last Modified**: 2026-01-30
> **Status**: ✅ Approved

---

## Immediate Actions (This Week)

### ✅ Completed

- [x] Set up bkit-standard PDCA structure (`docs/` folders)
- [x] Create `CLAUDE.md` project configuration
- [x] Create `_INDEX.md` document tracking
- [x] Complete current state analysis
- [x] Create improvement roadmap

### 🔄 In Progress

- [ ] **Review documents with user** (YOU ARE HERE)
  - Get feedback on analysis findings
  - Confirm improvement priorities
  - Approve roadmap timeline

### ⏭️ Next (After Approval)

---

## Phase 1: Immediate Fixes (Days 1-2)

### Day 1 Morning: Config & Resource Fixes

#### Task 1.1: Fix Config Default Pollution

**File**: `app/config.py`
**Time**: 30 min
**Steps**:

1. Open `app/config.py`
2. Add import: `import copy`
3. Create function:
   ```python
   def get_default_config():
       """Return deep copy to prevent pollution."""
       return copy.deepcopy(DEFAULT_CONFIG)
   ```
4. Replace all `DEFAULT_CONFIG` usages with `get_default_config()`
5. Run tests to verify no breakage

**Verification**:

```bash
pytest tests/test_config.py -v
```

#### Task 1.2: Fix Preview Temp Document Cleanup

**File**: `app/viewer.py`
**Time**: 30 min
**Steps**:

1. Open `app/viewer.py`
2. Find `RenderWorker.run()` method
3. Wrap `temp_doc` usage in try-finally:
   ```python
   temp_doc = None
   try:
       temp_doc = fitz.open(temp_path)
       # existing render logic
   finally:
       if temp_doc:
           temp_doc.close()
   ```
4. Test with multiple rapid preview operations

**Verification**: Check logs for no file handle warnings

---

### Day 1 Afternoon: Test Fixture Refactoring

#### Task 1.3: Create PDF Test Fixtures

**File**: `tests/conftest.py`
**Time**: 1-2 hours
**Steps**:

1. Create or open `tests/conftest.py`
2. Add fixture:

   ```python
   import pytest
   import fitz

   @pytest.fixture
   def simple_pdf(tmp_path):
       """Generate simple test PDF."""
       pdf_path = tmp_path / "test_simple.pdf"
       doc = fitz.open()
       page = doc.new_page(width=595, height=842)  # A4
       page.insert_text((50, 50), "Test text for selection")
       page.insert_text((50, 100), "Second line of text")
       doc.save(pdf_path)
       doc.close()
       return pdf_path

   @pytest.fixture
   def complex_pdf(tmp_path):
       """Generate PDF with multiple text styles."""
       pdf_path = tmp_path / "test_complex.pdf"
       doc = fitz.open()
       page = doc.new_page()
       # Add various text with different fonts, sizes
       page.insert_text((50, 50), "Regular text")
       page.insert_text((50, 100), "Bold text", fontsize=14)
       doc.save(pdf_path)
       doc.close()
       return pdf_path
   ```

3. Update `tests/test_ui.py` to use fixtures instead of `sample.pdf`
4. Run tests to ensure all pass

**Verification**:

```bash
pytest tests/ -v
```

---

### Day 2: Memory Guard Implementation

#### Task 1.4: Add RemoveSection Memory Guard

**File**: `app/model.py`
**Time**: 2-3 hours
**Steps**:

1. Open `app/model.py`
2. Find `RemoveSectionOp` class
3. Add memory estimation method:
   ```python
   def estimate_memory_mb(self, page):
       """Estimate memory for image conversion."""
       rect = page.rect
       dpi = self.dpi or 150
       width_px = int(rect.width * dpi / 72)
       height_px = int(rect.height * dpi / 72)
       # RGBA = 4 bytes per pixel
       mb = (width_px * height_px * 4) / (1024 * 1024)
       return mb
   ```
4. Add check before conversion:
   ```python
   estimated_mb = self.estimate_memory_mb(page)
   if estimated_mb > 500:  # 500MB threshold
       logger.warning(f"Large memory usage: {estimated_mb:.1f}MB, capping DPI")
       self.dpi = min(self.dpi or 150, 100)  # Cap at 100 DPI
   ```
5. Add test for large page handling

**Verification**: Test with A0-sized page, verify DPI is capped

---

### Phase 1 Deliverables Checklist

- [ ] Config deepcopy implemented
- [ ] Temp doc cleanup added
- [ ] Test fixtures created and tests refactored
- [ ] Memory guard added and tested
- [ ] All existing tests still pass
- [ ] Phase 1 completion report written

---

## Phase 2: Core Refactoring (Week 1-2)

### Prerequisite: Design Document

**Before starting implementation**, create:

- `docs/02-design/features/unified-operations.design.md`

Contents should include:

- Architecture diagram (before/after)
- Class structure for `OperationApplicator`
- Data flow diagram
- Migration plan for existing code
- Test plan

### Implementation Tasks

#### Task 2.1: Create OperationApplicator Service

**File**: `app/operations_service.py` (new)
**Time**: 4-6 hours
**Steps**:

1. Create new file `app/operations_service.py`
2. Extract text replacement logic from `DocumentSession.apply_operations_to_page()`
3. Extract same logic from `viewer.py::RenderWorker.run()`
4. Create unified `OperationApplicator` class
5. Add comprehensive docstrings
6. Unit test the service independently

**Verification**:

```bash
pytest tests/test_operations_service.py -v
```

#### Task 2.2: Refactor DocumentSession

**File**: `app/model.py`
**Time**: 2-3 hours
**Steps**:

1. Import `OperationApplicator`
2. Replace `apply_operations_to_page()` logic with service call
3. Remove duplicated font sizing logic
4. Update tests

#### Task 2.3: Refactor RenderWorker

**File**: `app/viewer.py`
**Time**: 2-3 hours
**Steps**:

1. Import `OperationApplicator`
2. Replace preview generation logic with service call
3. Ensure same code path as save
4. Update async tests

---

## Phase 3: UX Enhancements (Week 2-3)

### Task 3.1: Fixed Font Size Option

**Files**: `app/batch_replace_dialog.py`, `app/ui.py`
**Time**: 3-4 hours

**UI Components to Add**:

```python
# In replace dialog
self.fixed_size_checkbox = QCheckBox("Use fixed font size")
self.font_size_spinbox = QSpinBox()
self.font_size_spinbox.setRange(8, 24)
self.font_size_spinbox.setValue(10)
self.font_size_spinbox.setEnabled(False)  # Disabled by default

# Connect signals
self.fixed_size_checkbox.toggled.connect(
    self.font_size_spinbox.setEnabled
)
```

**Operation Changes**:

- Add `fixed_font_size` parameter to `ReplaceTextOp`
- Skip auto-scaling if `fixed_font_size` is set
- Update i18n strings for new option

### Task 3.2: Status Bar Warnings

**File**: `app/ui.py`
**Time**: 2 hours

**Add to MainWindow**:

```python
def show_scaling_warning(self, original_size, final_size):
    """Show warning when text is auto-scaled."""
    if final_size < 10:
        msg = self.i18n.get("warning_text_scaled", (original_size, final_size))
        self.statusBar().showMessage(msg, 5000)  # 5 seconds
        self.logger.warning(f"Text scaled from {original_size}pt to {final_size}pt")
```

**Update i18n**:

```json
// en.json
"warning_text_scaled": "⚠️ Text auto-scaled from {0}pt to {1}pt to fit area"

// ko.json
"warning_text_scaled": "⚠️ 텍스트가 영역에 맞게 {0}pt에서 {1}pt로 자동 축소되었습니다"
```

---

## Phase 4: Testing & i18n (Week 3)

### Task 4.1: Create i18n Validation Script

**File**: `scripts/validate_i18n.py` (new)
**Time**: 2-3 hours

**Script should check**:

1. All language files have same keys
2. Placeholder counts match (`{0}`, `{1}`)
3. No empty values
4. No missing translations

**Integration**:

```python
# tests/test_i18n.py
import subprocess

def test_i18n_validation():
    """Run i18n validation script."""
    result = subprocess.run(
        ["python", "scripts/validate_i18n.py"],
        capture_output=True
    )
    assert result.returncode == 0, result.stderr.decode()
```

### Task 4.2: Preview-Save Equivalence Test

**File**: `tests/test_equivalence.py` (new)
**Time**: 3-4 hours

**Test structure**:

```python
def test_replace_text_equivalence(simple_pdf, tmp_path):
    """Verify preview matches saved output."""
    # 1. Load PDF
    # 2. Create ReplaceTextOp
    # 3. Generate preview image
    # 4. Save to temp file with same operation
    # 5. Re-render saved file
    # 6. Compare image hashes or extracted text
    assert preview_image == saved_image
```

---

## Phase 5: Packaging (Week 4)

### Task 5.1: Create PyInstaller Spec

**File**: `PDF_Control.spec` (new)
**Time**: 1 hour

**Minimal spec**:

```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('app/i18n/*.json', 'app/i18n'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tests'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PDF_Control',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Windowed app
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
```

### Task 5.2: Build and Test

**Commands**:

```bash
# Install PyInstaller
pip install pyinstaller

# Build
pyinstaller PDF_Control.spec

# Test
dist\PDF_Control.exe
```

**Test checklist**:

- [ ] App launches without errors
- [ ] Can open PDF files
- [ ] Text deletion works
- [ ] Text replacement works
- [ ] Language switching works (en ↔ ko)
- [ ] Undo/redo works
- [ ] Save PDF works

---

## Quick Reference Commands

### Run Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_ui.py -v

# With coverage
pytest tests/ --cov=app --cov-report=html
```

### Check Code Quality

```bash
# Lint
flake8 app/ --max-line-length=120

# Type check (if using type hints)
mypy app/
```

### i18n Validation

```bash
python scripts/validate_i18n.py
```

### Build Executable

```bash
pyinstaller PDF_Control.spec
```

---

## Decision Log

### Decisions Needed from User

1. **Priority Confirmation**: Should we focus on quality (Phase 1-4) or packaging (Phase 5) first?
   - Recommendation: Quality first (Phase 1-4), then packaging

2. **Fixed Font Size Default**: What should be the default size for fixed font option?
   - Recommendation: 10pt (readable, commonly used)

3. **Memory Threshold**: What's acceptable memory usage for RemoveSection?
   - Recommendation: 500MB cap, with user warning

4. **Platform Support**: Should we test on macOS/Linux now or later?
   - Recommendation: Later (after Windows stabilization)

5. **Release Timeline**: Target date for v1.0 release?
   - Recommendation: 4 weeks from now (allows thorough testing)

---

## Progress Tracking

Use `_INDEX.md` to track document status:

- Update status (🔄 → ✅) as phases complete
- Create design documents before each phase
- Create analysis documents after each phase
- Create report document when project reaches v1.0

---

## Related Documents

- **CLAUDE.md**: [../../../CLAUDE.md](../../../CLAUDE.md)
- **Index**: [../../\_INDEX.md](../../_INDEX.md)
- **Analysis**: [../../03-analysis/features/current-state.analysis.md](../../03-analysis/features/current-state.analysis.md)
- **Improvement Plan**: [improvement.plan.md](improvement.plan.md)
- **Project Status Plan**: [project-status.plan.md](project-status.plan.md)

---

## Version History

| Version | Date       | Changes                     | Author        |
| ------- | ---------- | --------------------------- | ------------- |
| 1.0     | 2026-01-30 | Initial next steps document | Claude (bkit) |

---

## Current Status

**YOU ARE HERE**: 📍 Waiting for user review and approval

**Next Action**: Review all created documents with user, get feedback, begin Phase 1
