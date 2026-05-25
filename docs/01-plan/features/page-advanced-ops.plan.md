# Plan: page-advanced-ops

**Status**: 🔄 In Progress
**Date**: 2026-05-25
**Owner**: PDF Control
**Priority**: Medium (사용자 가치 높음, 기존 PageManagerDialog 확장)
**Feature**: PDF 페이지 고급 작업 — 복제(Duplicate), 추출(Extract), 병합(Merge)

---

## 1. Problem

기존 `PageManagerDialog`는 회전·순서변경·삭제·빈 페이지 삽입·드래그드롭만 지원한다. 실무에서 자주 쓰이는 다음 3가지 페이지 작업이 누락되어 있어, 사용자는 다른 도구로 우회해야 한다:

1. **페이지 복제 (Duplicate)** — 같은 페이지가 여러 번 필요할 때(예: 양식 사본 만들기) 외부 도구 필요
2. **페이지 추출 (Extract)** — 선택한 페이지만 별도 PDF로 저장 불가 → 일부 페이지 공유/보관 시 불편
3. **PDF 병합 (Merge)** — 다른 PDF 파일을 현재 문서에 삽입 불가 → 챕터 합치기/표지 추가 등 불가

## 2. Goal

- 기존 `PageManagerDialog`에 위 3가지 기능을 추가하여 페이지 단위 작업을 완전체로 만든다.
- 기존 패턴(`DocumentSession` → `Controller` → `Dialog`) 100% 준수.
- 기존 회전/순서/삭제 기능에는 영향 없음 (회귀 0건).
- i18n(en/ko) 전 항목 동시 추가.
- 단위 테스트 신규 ≥ 9개 (각 기능당 ≥ 3 케이스).

## 3. Non-Goals

- OCR, 워터마크, 주석 등 다른 신규 기능 (별도 사이클).
- `PageManagerDialog` 전체 UI 재설계 (toolbar에 버튼만 추가).
- 페이지 단위 회전 외 회전 기능(예: 사용자 정의 각도) 확장.
- 클라우드 PDF/원격 파일 병합.
- 페이지 라벨/북마크 보존 (PyMuPDF 기본 동작에 위임, 별도 보존 로직 없음).

## 4. Scope

### In Scope

✅ `DocumentSession.duplicate_pages(page_indices)` — PyMuPDF `Document.copy_page` 사용
✅ `DocumentSession.extract_pages(page_indices, output_path)` — PyMuPDF `Document.select` + `Document.save` 활용
✅ `DocumentSession.merge_pdf(source_path, after_index)` — PyMuPDF `Document.insert_pdf` 사용
✅ `Controller`에 3개 메서드 wrap (try/except, logger.info, `_modified` 표시)
✅ `PageManagerDialog` toolbar에 3개 액션 + 핸들러 추가
✅ i18n 키 추가 (en/ko 각 ~12개)
✅ 단위 테스트: `tests/test_page_management.py`에 `TestDuplicatePages`, `TestExtractPages`, `TestMergePdf` 클래스 추가
✅ 빈 입력/잘못된 인덱스/존재하지 않는 파일 등 경계 케이스 처리

### Out of Scope

❌ Undo/Redo 통합 (Phase 2로 분리, 기존 회전/삭제도 미통합 상태이므로 동일 정책 유지)
❌ 드래그앤드롭 페이지 import (파일 다이얼로그만 지원)
❌ 페이지 추출 시 양식/주석 보존 옵션 (PyMuPDF 기본 동작 사용)

## 5. Acceptance Criteria

### Model 계층 (`app/model.py`)

- [ ] `DocumentSession.duplicate_pages(page_indices: List[int]) -> int` 추가
  - 빈 리스트 → ValueError
  - 잘못된 인덱스 → IndexError
  - 성공 시 복제된 페이지 수 반환, `_rebuild_after_reorder()` 호출, `self._modified = True`
- [ ] `DocumentSession.extract_pages(page_indices: List[int], output_path: str) -> None` 추가
  - 빈 리스트 → ValueError
  - 잘못된 인덱스 → IndexError
  - 출력 경로 부모 디렉토리 없으면 ValueError
  - 임시 `fitz.open()` 문서에 `insert_pdf(...select(indices))`로 복사 후 저장
  - 원본 문서 무변경 (`_modified` 변화 없음)
- [ ] `DocumentSession.merge_pdf(source_path: str, after_index: int = -1) -> int` 추가
  - 파일 미존재 → FileNotFoundError
  - 잘못된 PDF → ValueError (PyMuPDF 예외 wrap)
  - 성공 시 추가된 페이지 수 반환, `_rebuild_after_reorder()` 호출, `self._modified = True`

### Controller 계층 (`app/controller.py`)

- [ ] `Controller.duplicate_pages(page_indices: list) -> bool` — 예외 catch, logger 기록
- [ ] `Controller.extract_pages(page_indices: list, output_path: str) -> bool`
- [ ] `Controller.merge_pdf(source_path: str, after_index: int = -1) -> bool`
- [ ] 모든 메서드는 기존 `rotate_page`/`delete_pages` 패턴 동일 (try/except → bool 반환, 실패 시 logger.error)

### UI 계층 (`app/page_manager_dialog.py`)

- [ ] Toolbar separator 추가 후 3개 액션 배치:
  - `duplicate_action` — 선택된 페이지 복제, 비활성: 선택 0개
  - `extract_action` — 파일 다이얼로그(QFileDialog.getSaveFileName) → 추출 실행
  - `merge_action` — 파일 다이얼로그(QFileDialog.getOpenFileName, *.pdf 필터) → 선택 위치(마지막 선택 뒤) 뒤에 병합
- [ ] 핸들러 메서드: `_duplicate_selected()`, `_extract_selected()`, `_merge_pdf()`
- [ ] 모든 핸들러는 성공 시 `_load_thumbnails()` + `_mark_changed()` 호출
- [ ] 실패 시 `QMessageBox.warning` + i18n 메시지

### i18n (`app/i18n/en.json`, `app/i18n/ko.json`)

- [ ] 키 추가 (양쪽 동일 키, 값 번역):
  - `page_manager.duplicate`, `page_manager.duplicate.tooltip`
  - `page_manager.extract`, `page_manager.extract.tooltip`, `page_manager.extract.dialog_title`, `page_manager.extract.success`
  - `page_manager.merge`, `page_manager.merge.tooltip`, `page_manager.merge.dialog_title`, `page_manager.merge.success`
  - `page_manager.error.no_selection`, `page_manager.error.invalid_pdf`, `page_manager.error.file_not_found`

### 테스트 (`tests/test_page_management.py`)

- [ ] `TestDuplicatePages`:
  - `test_duplicate_single` — 1개 복제 후 페이지 수 +1, 내용 동일
  - `test_duplicate_multiple` — 여러 개 동시 복제
  - `test_duplicate_empty_raises` — 빈 리스트 ValueError
- [ ] `TestExtractPages`:
  - `test_extract_creates_file` — 출력 파일 생성, 페이지 수 일치
  - `test_extract_preserves_original` — 원본 문서 page_count 불변
  - `test_extract_invalid_indices` — IndexError
- [ ] `TestMergePdf`:
  - `test_merge_appends` — 페이지 수 = 원본 + 외부
  - `test_merge_at_position` — 지정 위치 뒤 삽입 확인
  - `test_merge_nonexistent_raises` — FileNotFoundError

### i18n 검증

- [ ] `python tests/validate_i18n.py` 또는 `test_i18n_validation.py` 통과 (en/ko 키 일치)

### 회귀 / 빌드

- [ ] 전체 회귀 테스트 전부 통과 (기존 + 신규)
- [ ] `app/page_manager_dialog.py` import 추가만, 기존 동작 변화 없음
- [ ] CLAUDE.md drift 테스트 통과

## 6. Affected Files

| 파일 | 변경 종류 | 예상 라인 변화 |
|------|-----------|----------------|
| `app/model.py` | 메서드 3개 추가 | +60 |
| `app/controller.py` | 메서드 3개 추가 | +30 |
| `app/page_manager_dialog.py` | 액션 3개 + 핸들러 3개 추가 | +90 |
| `app/i18n/en.json` | 키 ~12개 추가 | +14 |
| `app/i18n/ko.json` | 키 ~12개 추가 | +14 |
| `tests/test_page_management.py` | 클래스 3개(9 테스트) 추가 | +100 |
| `docs/_INDEX.md` | 인덱스 업데이트 | +2 |
| `CHANGELOG.md` | Unreleased 항목 추가 | +1 |

## 7. Risks & Mitigations

| 리스크 | 영향 | 대응 |
|--------|------|------|
| PyMuPDF `copy_page` 가 페이지 객체 식별자에 부작용 일으킬 수 있음 | 중 | 복제 후 즉시 `_rebuild_after_reorder()` 호출, 단위 테스트로 보호 |
| `insert_pdf` 시 외부 PDF 크기가 매우 클 경우 메모리 압박 | 중 | 우선 기본 동작 유지, 별도 페이지 제한 옵션은 다음 사이클 |
| `extract_pages`에서 사용자가 원본 경로 덮어쓰기 | 높 | 출력 경로가 현재 세션 경로와 동일하면 차단 + 경고 다이얼로그 |
| i18n 키 누락 시 UI 미렌더 | 낮 | `test_i18n_validation` CI 적용 |

## 8. Timeline

- **Plan**: ~30분 (지금 단계, 완료)
- **Design**: ~30분
- **Do**: ~90분 (model 30 + controller 15 + UI 30 + i18n 5 + test 10)
- **Check/Iterate**: ~30분
- **QA**: ~15분
- **Report**: ~15분

**총 예상**: ~3.5시간

## 9. References

- 기존 `PageManagerDialog` — `app/page_manager_dialog.py`
- 기존 page ops 모델 — `app/model.py:507-590`
- 기존 Controller wrap — `app/controller.py:113-160`
- 단위 테스트 패턴 — `tests/test_page_management.py:7-40`
- PyMuPDF 문서 — `Document.copy_page`, `Document.select`, `Document.insert_pdf`

---

## Version History

| Version | Date       | Changes       | Author |
| ------- | ---------- | ------------- | ------ |
| 1.0     | 2026-05-25 | Initial plan  | Claude (bkit) |
