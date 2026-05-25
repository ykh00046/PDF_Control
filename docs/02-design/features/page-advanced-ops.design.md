# Design: page-advanced-ops

**Status**: 🔄 In Progress
**Date**: 2026-05-25
**Owner**: PDF Control
**Plan Ref**: [page-advanced-ops.plan.md](../../01-plan/features/page-advanced-ops.plan.md)

---

## 1. Architecture Overview

기존 3계층 구조에 신규 동사 3개를 동일 패턴으로 삽입:

```
┌─────────────────────────────────────────────┐
│       PageManagerDialog (UI)                │
│   _duplicate_selected / _extract_selected   │
│   _merge_pdf                                │
└────────────────┬────────────────────────────┘
                 │ controller.duplicate_pages(...)
                 │ controller.extract_pages(...)
                 │ controller.merge_pdf(...)
                 ▼
┌─────────────────────────────────────────────┐
│         Controller (try/except wrap)        │
│   logger.error 시그널 emit, bool 반환       │
└────────────────┬────────────────────────────┘
                 │ session.duplicate_pages(...) ...
                 ▼
┌─────────────────────────────────────────────┐
│      DocumentSession (PyMuPDF 호출)         │
│   - duplicate_pages   → copy_page x N        │
│   - extract_pages     → temp doc + insert    │
│   - merge_pdf         → insert_pdf            │
│   _rebuild_after_reorder 로 history 정리    │
└─────────────────────────────────────────────┘
```

## 2. Data / API Contract

### 2.1 `DocumentSession` (model.py) 추가 메서드

#### `duplicate_pages(page_indices: List[int]) -> int`

```python
def duplicate_pages(self, page_indices: List[int]) -> int:
    """Duplicate the given pages, inserting each copy directly after the original.

    Args:
        page_indices: 0-based indices to duplicate. Order does not matter
                      (sorted descending internally to keep indices stable).

    Returns:
        Number of pages duplicated.

    Raises:
        ValueError: empty list or duplicate indices.
        IndexError: any index out of range.
    """
```

**구현 노트**:
- 빈 리스트 또는 중복 → `ValueError`
- `if any(i < 0 or i >= self.doc.page_count for i in page_indices)` → `IndexError`
- 내림차순 정렬 후 각 인덱스에 대해 `self.doc.copy_page(idx, idx + 1)` 호출 (PyMuPDF: `to` 인자는 삽입 위치)
- 호출 후 `_rebuild_after_reorder()` 호출 (history 무효화, modified=True)
- 반환값: `len(page_indices)`

#### `extract_pages(page_indices: List[int], output_path: str) -> None`

```python
def extract_pages(self, page_indices: List[int], output_path: str) -> None:
    """Save selected pages to a new PDF file. Does not modify the current document.

    Args:
        page_indices: 0-based indices in display order.
        output_path: absolute path for the output PDF.

    Raises:
        ValueError: empty list, invalid output_path, or output_path equals current file_path.
        IndexError: any index out of range.
        OSError: write failure.
    """
```

**구현 노트**:
- 빈 리스트 → `ValueError("page_indices must not be empty")`
- 인덱스 검증 (IndexError)
- 출력 경로의 부모 디렉토리 미존재 → `ValueError`
- `output_path`가 `self.file_path`와 동일 → `ValueError("Cannot overwrite source document")`
- 동작:
  ```python
  new_doc = fitz.open()
  new_doc.insert_pdf(self.doc, from_page=...)  # per-index or via select
  ```
  실제로는 인덱스 리스트 보존을 위해 한 번에 처리:
  ```python
  new_doc = fitz.open()
  for idx in page_indices:
      new_doc.insert_pdf(self.doc, from_page=idx, to_page=idx)
  new_doc.save(output_path)
  new_doc.close()
  ```
- 원본 무변경 → `self.modified` 변화 없음

#### `merge_pdf(source_path: str, after_index: int = -1) -> int`

```python
def merge_pdf(self, source_path: str, after_index: int = -1) -> int:
    """Insert all pages from another PDF after the given index.

    Args:
        source_path: path to the external PDF.
        after_index: insert position (0-based). -1 means at the end.

    Returns:
        Number of pages inserted.

    Raises:
        FileNotFoundError: source_path does not exist.
        ValueError: source_path is invalid PDF or after_index out of range.
    """
```

**구현 노트**:
- `os.path.isfile(source_path)` 체크
- `after_index` 범위 검증: `-1` 또는 `0..page_count-1`
- 동작:
  ```python
  with fitz.open(source_path) as src:
      added = src.page_count
      start_at = self.doc.page_count if after_index == -1 else after_index + 1
      self.doc.insert_pdf(src, start_at=start_at)
  ```
- PyMuPDF의 `insert_pdf`는 `start_at` 인자로 삽입 위치 지정 가능
- 호출 후 `_rebuild_after_reorder()` 호출
- 반환: `added`

### 2.2 `Controller` (controller.py) 추가 메서드

```python
def duplicate_pages(self, page_indices: list) -> bool:
    """Duplicate the given pages."""
    if not self._session:
        return False
    try:
        self._session.duplicate_pages(page_indices)
        self.operation_applied.emit()
        return True
    except Exception as e:
        self.logger.error(f"Failed to duplicate pages: {e}")
        self.error_occurred.emit(str(e))
        return False

def extract_pages(self, page_indices: list, output_path: str) -> bool:
    """Extract selected pages to a new PDF."""
    if not self._session:
        return False
    try:
        self._session.extract_pages(page_indices, output_path)
        return True
    except Exception as e:
        self.logger.error(f"Failed to extract pages: {e}")
        self.error_occurred.emit(str(e))
        return False

def merge_pdf(self, source_path: str, after_index: int = -1) -> bool:
    """Merge an external PDF into the current document."""
    if not self._session:
        return False
    try:
        self._session.merge_pdf(source_path, after_index)
        self.operation_applied.emit()
        return True
    except Exception as e:
        self.logger.error(f"Failed to merge PDF: {e}")
        self.error_occurred.emit(str(e))
        return False
```

**디자인 결정**: `extract_pages`는 `operation_applied` emit 하지 **않음** (원본 무변경). `duplicate_pages`/`merge_pdf`는 변경하므로 emit.

### 2.3 UI 계층 (page_manager_dialog.py) 변경

**Toolbar 배치 (추가)**:
```
[rotate_left] [rotate_right] [rotate_180] | [delete] | [insert_blank]
| [move_up] [move_down] | [duplicate] [extract] [merge]    ← 신규
```

**신규 액션 등록 (`_setup_ui` 끝부분)**:
```python
toolbar.addSeparator()

self.duplicate_action = QAction(tr("page_manager.duplicate"), self)
self.duplicate_action.setToolTip(tr("page_manager.duplicate.tooltip"))
self.duplicate_action.triggered.connect(self._duplicate_selected)
toolbar.addAction(self.duplicate_action)

self.extract_action = QAction(tr("page_manager.extract"), self)
self.extract_action.setToolTip(tr("page_manager.extract.tooltip"))
self.extract_action.triggered.connect(self._extract_selected)
toolbar.addAction(self.extract_action)

self.merge_action = QAction(tr("page_manager.merge"), self)
self.merge_action.setToolTip(tr("page_manager.merge.tooltip"))
self.merge_action.triggered.connect(self._merge_pdf)
toolbar.addAction(self.merge_action)
```

**핸들러**:

```python
def _duplicate_selected(self):
    selected = self.page_list.selectedItems()
    if not selected:
        QMessageBox.information(
            self, tr("page_manager.error.title"),
            tr("page_manager.error.no_selection")
        )
        return
    indices = [self.page_list.row(item) for item in selected]
    if self.controller.duplicate_pages(indices):
        self._load_thumbnails()
        self._mark_changed()
        self.logger.info(f"Duplicated {len(indices)} page(s)")

def _extract_selected(self):
    selected = self.page_list.selectedItems()
    if not selected:
        QMessageBox.information(
            self, tr("page_manager.error.title"),
            tr("page_manager.error.no_selection")
        )
        return
    indices = sorted([self.page_list.row(item) for item in selected])
    output_path, _ = QFileDialog.getSaveFileName(
        self, tr("page_manager.extract.dialog_title"),
        "", "PDF Files (*.pdf)"
    )
    if not output_path:
        return
    if not output_path.lower().endswith(".pdf"):
        output_path += ".pdf"
    if self.controller.extract_pages(indices, output_path):
        QMessageBox.information(
            self, tr("page_manager.title"),
            tr("page_manager.extract.success", output_path)
        )

def _merge_pdf(self):
    source_path, _ = QFileDialog.getOpenFileName(
        self, tr("page_manager.merge.dialog_title"),
        "", "PDF Files (*.pdf)"
    )
    if not source_path:
        return
    selected = self.page_list.selectedItems()
    if selected:
        after_index = self.page_list.row(selected[-1])
    else:
        after_index = -1
    if self.controller.merge_pdf(source_path, after_index):
        self._load_thumbnails()
        self._mark_changed()
```

### 2.4 i18n 키 정의

**en.json (추가 블록)**:
```json
"page_manager.duplicate": "Duplicate",
"page_manager.duplicate.tooltip": "Duplicate selected pages (insert copy after each)",
"page_manager.extract": "Extract",
"page_manager.extract.tooltip": "Save selected pages as a new PDF",
"page_manager.extract.dialog_title": "Save Extracted Pages",
"page_manager.extract.success": "Pages extracted to: {0}",
"page_manager.merge": "Merge",
"page_manager.merge.tooltip": "Insert pages from another PDF file",
"page_manager.merge.dialog_title": "Select PDF to Merge",
"page_manager.merge.success": "PDF merged successfully",
"page_manager.error.no_selection": "No pages selected",
"page_manager.error.invalid_pdf": "Invalid or unreadable PDF",
"page_manager.error.file_not_found": "File not found: {0}"
```

**ko.json (추가 블록)**:
```json
"page_manager.duplicate": "복제",
"page_manager.duplicate.tooltip": "선택한 페이지를 복제합니다 (원본 뒤에 사본 삽입)",
"page_manager.extract": "추출",
"page_manager.extract.tooltip": "선택한 페이지를 새 PDF 파일로 저장합니다",
"page_manager.extract.dialog_title": "추출한 페이지 저장",
"page_manager.extract.success": "페이지가 다음 위치에 추출되었습니다: {0}",
"page_manager.merge": "병합",
"page_manager.merge.tooltip": "다른 PDF 파일의 페이지를 현재 문서에 삽입합니다",
"page_manager.merge.dialog_title": "병합할 PDF 선택",
"page_manager.merge.success": "PDF가 성공적으로 병합되었습니다",
"page_manager.error.no_selection": "선택된 페이지가 없습니다",
"page_manager.error.invalid_pdf": "잘못되었거나 읽을 수 없는 PDF입니다",
"page_manager.error.file_not_found": "파일을 찾을 수 없음: {0}"
```

## 3. Test Design

### 3.1 단위 테스트 추가 (`tests/test_page_management.py`)

기존 fixture `multi_page_pdf` (5페이지) 재사용.

```python
class TestDuplicatePages:
    def test_duplicate_single(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        original_count = session.doc.page_count
        session.duplicate_pages([0])
        assert session.doc.page_count == original_count + 1
        assert session.modified is True
        session.close()

    def test_duplicate_multiple(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        session.duplicate_pages([0, 2, 4])
        assert session.doc.page_count == 5 + 3
        session.close()

    def test_duplicate_empty_raises(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        with pytest.raises(ValueError):
            session.duplicate_pages([])
        session.close()


class TestExtractPages:
    def test_extract_creates_file(self, multi_page_pdf, tmp_path):
        session = DocumentSession(multi_page_pdf)
        out = tmp_path / "extracted.pdf"
        session.extract_pages([0, 2], str(out))
        assert out.exists()
        with fitz.open(str(out)) as d:
            assert d.page_count == 2
        session.close()

    def test_extract_preserves_original(self, multi_page_pdf, tmp_path):
        session = DocumentSession(multi_page_pdf)
        out = tmp_path / "out.pdf"
        session.extract_pages([1, 3], str(out))
        assert session.doc.page_count == 5
        assert session.modified is False
        session.close()

    def test_extract_invalid_indices(self, multi_page_pdf, tmp_path):
        session = DocumentSession(multi_page_pdf)
        out = tmp_path / "out.pdf"
        with pytest.raises(IndexError):
            session.extract_pages([0, 99], str(out))
        session.close()


class TestMergePdf:
    def test_merge_appends(self, multi_page_pdf, tmp_path):
        # Create a second 3-page PDF
        other = tmp_path / "other.pdf"
        d = fitz.open()
        for i in range(3):
            d.new_page(width=595, height=842)
        d.save(str(other))
        d.close()
        session = DocumentSession(multi_page_pdf)
        session.merge_pdf(str(other), after_index=-1)
        assert session.doc.page_count == 5 + 3
        assert session.modified is True
        session.close()

    def test_merge_at_position(self, multi_page_pdf, tmp_path):
        other = tmp_path / "other.pdf"
        d = fitz.open()
        d.new_page(width=595, height=842)
        d.save(str(other))
        d.close()
        session = DocumentSession(multi_page_pdf)
        session.merge_pdf(str(other), after_index=1)  # insert after page 2
        assert session.doc.page_count == 6
        session.close()

    def test_merge_nonexistent_raises(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        with pytest.raises(FileNotFoundError):
            session.merge_pdf("/path/does/not/exist.pdf")
        session.close()
```

## 4. Decision Log

| 결정 | 대안 | 선택 이유 |
|------|------|-----------|
| `extract_pages`에서 `operation_applied` emit 안 함 | 항상 emit | 원본 무변경 → viewer 재렌더 불필요 |
| 복제 시 `_rebuild_after_reorder()` 호출 (history 클리어) | history 인덱스 시프트 | 기존 `move_page`와 일관성, 데이터 안전 우선 |
| `extract_pages`에서 원본 경로 덮어쓰기 차단 | 사용자에 위임 | 비가역 데이터 손실 방지 |
| 출력 경로 자동 `.pdf` 확장자 추가 | 다이얼로그 필터 의존 | OS별 다이얼로그 동작 차이 보정 |
| Toolbar에 액션 추가 (사이드 패널 X) | 신규 사이드 패널 | Plan 명시 Scope 최소화, 기존 UI 흐름 유지 |
| Undo/Redo 미통합 | 통합 | 기존 회전/삭제도 미통합, 일관성 유지 — 별도 사이클 |

## 5. Migration / Compatibility

- **Backward compatible**: 기존 메서드 시그니처/동작 무변경
- 기존 `PageManagerDialog` 인스턴스는 추가 액션 3개만 노출됨
- i18n 키 누락 시 `tr()`는 키 자체를 표시 (graceful degrade)

## 6. References

- Plan: [page-advanced-ops.plan.md](../../01-plan/features/page-advanced-ops.plan.md)
- 기존 모델 패턴: `app/model.py:507-570`
- 기존 컨트롤러 패턴: `app/controller.py:113-163`
- 기존 다이얼로그: `app/page_manager_dialog.py:46-127`
- PyMuPDF: `Document.copy_page`, `Document.insert_pdf`, `Document.save`

---

## Version History

| Version | Date       | Changes        | Author        |
| ------- | ---------- | -------------- | ------------- |
| 1.0     | 2026-05-25 | Initial design | Claude (bkit) |
