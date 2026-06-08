# Design: text-export (as-built v1.1)

> **Feature**: PDF 텍스트 내보내기 (txt / md)
> **Project**: PDF Control (Starter / PySide6 + PyMuPDF)
> **Date**: 2026-06-02
> **Status**: ✅ Approved (as-built)
> **PDCA Phase**: Design

> **변경 메모(v1.1)**: 구현 단계에서 사용자 요구사항("페이지 또는 문서 전체")을 정확히
> 충족하는 **scope 방식(전체 문서 / 현재 페이지)**으로 수렴했다. 초안(v1.0)의 임의
> 페이지-범위(`1,3,5-7`) 입력은 본 사이클 범위에서 제외하고 **향후 확장**으로 이관했다.
> 진입점도 기존 도구류(crop/remove/page-manager)와의 일관성을 위해 **Tools 메뉴**에 둔다.

---

## 1. 아키텍처 개요

```
Tools 메뉴(Export Text…, Ctrl+Shift+T)
        │
        ▼
DialogHandlerMixin.open_text_export_dialog()        (문서 가드)
        │
        ▼
TextExportDialog ──export_confirmed({scope, fmt})──▶ apply_text_export(settings)
   · scope: all / current                              │ scope→page_indices 해석
   · fmt  : txt / md                                    │ QFileDialog(저장) + 확장자 보정
                                                        ▼
                                          EditorController.export_text(path, indices, fmt)
                                                        │ (read-only, emit 없음)
                                                        ▼
                                          DocumentSession.export_text(...) ─delegate─▶
                                                                       app/text_export.py
                                                                         · extract_text
                                                                         · export_text_to_file
                                                                              │ fitz get_text
                                                                              ▼  UTF-8 파일
```

설계 원칙: **순수 로직(`text_export`) ↔ Qt(dialog/handler) 완전 분리**. 추출 로직은 Qt
의존이 없어 결정적 단위 테스트가 가능하다(crop/remove 다이얼로그 관례와 동일하게,
저장 다이얼로그와 파일 쓰기는 호출자 handler가 담당).

---

## 2. 모듈 상세 설계 (as-built)

### 2.1 `app/text_export.py` (신규, 순수 함수)

```python
TXT = "txt"; MD = "md"; SUPPORTED_FORMATS = (TXT, MD)

def resolve_indices(page_indices: Optional[Sequence[int]], page_count: int) -> List[int]:
    """None이면 전체. 범위 초과 → IndexError. 정렬·중복제거된 0-based 반환."""

def build_text(doc, page_indices: Sequence[int], fmt: str) -> str:
    """txt: 페이지 텍스트를 '\n\n'으로 연결 / md: '## Page {n}' 헤더 부여."""

def extract_text(doc, page_indices=None, fmt=TXT) -> str:
    """fmt 검증(ValueError) → resolve_indices → build_text. 부작용 없음."""

def export_text_to_file(doc, output_path, *, page_indices=None, fmt=TXT,
                        source_path=None) -> int:
    """경로/디렉터리/원본덮어쓰기 검증 → extract_text → UTF-8 기록.
    반환값: 기록한 문자 수(len(content))."""
```

**검증 규칙**
- `fmt not in SUPPORTED_FORMATS` → `ValueError("unsupported format: …")`
- `not output_path` → `ValueError("output_path must not be empty")`
- 부모 디렉터리 부재 → `ValueError("output directory does not exist: …")`
- `source_path`와 동일 절대경로 → `ValueError("Cannot overwrite source document")`
- 인덱스 범위 초과 → `IndexError("page index out of range: …")`
- 파일 기록: `open(path, "w", encoding="utf-8", newline="\n")`

### 2.2 `DocumentSession` (document_session.py, 추가)

```python
def extract_text(self, page_indices=None, fmt="txt") -> str:
    indices = resolve_indices(page_indices, self.doc.page_count)
    return build_text(self.doc, indices, fmt)

def export_text(self, output_path, page_indices=None, fmt="txt") -> int:
    return export_text_to_file(self.doc, output_path,
                               page_indices=page_indices, fmt=fmt,
                               source_path=self.file_path)
```
원본 무변경 → `modified`/history 영향 없음. `export_text`는 기록한 문자 수를 반환한다.

### 2.3 `EditorController.export_text` (controller.py, 추가)

`extract_pages` 패턴 미러 (read-only이므로 `operation_applied` emit 생략):

```python
def export_text(self, output_path, page_indices=None, fmt="txt") -> bool:
    if not self._session:
        return False
    try:
        self._session.export_text(output_path, page_indices, fmt)
        return True
    except Exception as e:
        self.logger.error(f"Failed to export text: {e}")
        self.error_occurred.emit(str(e))
        return False
```

### 2.4 `app/text_export_dialog.py` (신규)

```python
class TextExportDialog(QDialog):
    export_confirmed = Signal(dict)  # {"scope": "all"|"current", "fmt": "txt"|"md"}
```
- Scope: 라디오 2개(문서 전체 / 현재 페이지만), 기본 전체.
- Format: QComboBox(txt/md), data로 `"txt"`/`"md"` 보유.
- 버튼: 내보내기(OK) / 취소. `_on_accept`에서 `get_settings()` emit 후 close.

### 2.5 `DialogHandlerMixin` (handlers/dialog_handlers.py, 추가)

```python
def open_text_export_dialog(self):
    if not self.controller.session:
        self.statusBar().showMessage(tr("status.no_document_export")); return
    from app.text_export_dialog import TextExportDialog
    dialog = TextExportDialog(self)
    dialog.export_confirmed.connect(self.apply_text_export)
    dialog.exec()

def apply_text_export(self, settings: dict):
    fmt = settings.get("fmt", "txt")
    page_indices = [self.viewer.current_page_index] if settings.get("scope") == "current" else None
    file_filter, ext = (("Markdown Files (*.md)", ".md") if fmt == "md"
                        else ("Text Files (*.txt)", ".txt"))
    base = self.controller.session.file_path
    suggested = (base.rsplit(".", 1)[0] + ext) if base else "untitled" + ext
    output_path, _ = QFileDialog.getSaveFileName(self, tr("text_export.dialog_title"),
                                                 suggested, file_filter)
    if not output_path:
        self.statusBar().showMessage(tr("status.ready")); return
    if not output_path.lower().endswith(ext):
        output_path += ext
    if self.controller.export_text(output_path, page_indices, fmt):
        self.statusBar().showMessage(tr("text_export.success", output_path))
    else:
        QMessageBox.critical(self, tr("dialog.error"), tr("error.export_failed", output_path))
```
저장 파일명은 원본 경로 기반으로 자동 제안한다(UX 보강).

### 2.6 `MenuBuilder._build_tools_menu` (ui_menu.py, 추가)

page-manager 항목 뒤에 추가:
```python
export_text_action = QAction(tr("menu.tools.export_text"), win)
export_text_action.setShortcut("Ctrl+Shift+T")
export_text_action.triggered.connect(win.open_text_export_dialog)
tools_menu.addAction(export_text_action)
```

---

## 3. i18n 키 (en/ko 동시, 14개, prefix `text_export.*`)

`menu.tools.export_text`, `text_export.title`, `text_export.scope.label/all/current`,
`text_export.format.label/txt/md`, `text_export.button.export/cancel`,
`text_export.dialog_title`, `text_export.success`, `status.no_document_export`,
`error.export_failed` (+ 기존 `status.ready`, `dialog.error` 재사용).
플레이스홀더 `{0}` 일관 유지, `tests/test_i18n_validation.py`로 검증.

---

## 4. 테스트 설계 (`tests/test_text_export.py`, 14개)

| 클래스 | 케이스 | AC |
|--------|--------|----|
| TestExtractText | 전체 txt 모든 페이지 / 현재 페이지만 / md 헤더 / 원본무변경 / 미지원 fmt(ValueError) / 범위초과(IndexError) | AC1,AC2,AC4,AC5,AC8 |
| TestExportText | txt 파일 기록·문자수반환 / md 파일 / 빈 경로 / 디렉터리 부재 / 원본덮어쓰기 차단 / 문자수=파일길이 | AC5,AC6,AC7 |
| TestEngine | 중복 인덱스 dedup·정렬 / txt에 md 헤더 없음 | 견고성 |

픽스처: 3페이지 PDF(`Hello page N`).

---

## 5. 결정 & 트레이드오프 (as-built)

| 결정 | 이유 |
|------|------|
| scope = 전체/현재 (범위 미입력) | 사용자 요구("페이지 또는 문서 전체")를 정확히 충족, 단순·견고 |
| 진입점 Tools 메뉴(Ctrl+Shift+T) | crop/remove/page-manager와 동일 그룹, 학습곡선 0 |
| 순수 모듈 분리(text_export) | Qt 비의존 → 결정적 단위 테스트 |
| read-only(emit/undo 미적용) | extract_pages와 동일 일관성, 원본 무변경 |
| export_text 반환=문자 수 | 호출부에서 "쓰여진 분량" 검증이 자연스러움(테스트 계약) |
| md는 `## Page N`만 | 단순·예측 가능 |

### 향후 확장 (Out of Scope, 본 사이클 제외)
- 임의 페이지 범위 입력(`1,3,5-7`)
- 표/레이아웃 보존(HTML/JSON), 메타데이터 포함
- OCR 연동(스캔 PDF)

---

## Related Documents

- Plan: [text-export.plan.md](../../01-plan/features/text-export.plan.md)
- Analysis: [text-export.analysis.md](../../03-analysis/features/text-export.analysis.md)
- Report: [text-export.report.md](../../04-report/features/text-export.report.md)

## Version History

| Version | Date       | Changes                          | Author        |
| ------- | ---------- | -------------------------------- | ------------- |
| 1.0     | 2026-06-02 | Initial design (range 포함)      | Claude (bkit) |
| 1.1     | 2026-06-02 | As-built 정합화 (scope 방식 수렴) | Claude (bkit) |
