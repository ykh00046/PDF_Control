# Page Merge / Split - Design

> **Summary**: 분할(Split) 순수 로직 + 세션 메서드, 다중 병합(Batch Merge), SplitDialog UI의 구현 설계
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-02
> **Status**: ✅ Complete
> **Plan**: [page-merge-split.plan.md](../../01-plan/features/page-merge-split.plan.md)

---

## 1. 아키텍처 개요

```
SplitDialog ─┐
             ├─> Controller.split_document ──> DocumentSession.split_document ──┐
PageManager ─┘                                                                  │
   (Split/Merge actions)                                          app.page_split (순수)
             ├─> Controller.merge_pdfs ──────> DocumentSession.merge_pdfs       │
                                                  └─ merge_pdf (위임, 하위호환)  │
                                                                                 ▼
                                              compute_split_groups / parse_page_ranges
```

- **순수 코어** `app/page_split.py`: I/O 없는 그룹 계산·범위 파싱. mypy strict 대상.
- **세션** `DocumentSession`: 코어가 만든 그룹으로 실제 파일 쓰기/병합(I/O). `extract_pages`와 동일한 검증 계약 재사용.
- **UI** `SplitDialog` + `PageManagerDialog`: 사용자 입력 수집·결과 안내.

---

## 2. `app/page_split.py` (신규, 순수)

```python
from enum import Enum
from typing import List

class SplitMode(str, Enum):
    SINGLE = "single"      # 페이지마다 1파일
    EVERY_N = "every_n"    # N페이지씩
    RANGES = "ranges"      # 사용자 범위 스펙

def parse_page_ranges(spec: str, page_count: int) -> List[List[int]]:
    """ "1-3, 5, 7-9" (1-based) → [[0,1,2],[4],[6,7,8]] (0-based).

    규칙:
    - 쉼표로 그룹 구분, 각 그룹은 단일("5") 또는 범위("7-9").
    - 1-based 입력, 양끝 포함. 공백 허용.
    - 거부(ValueError): 빈 스펙, 숫자 외 토큰, 0 이하, page_count 초과,
      범위 역순(예 "5-3"), 빈 그룹("1,,3").
    - 중복/겹침은 허용(사용자 의도일 수 있음) — 그룹은 입력 순서 보존.
    """

def compute_split_groups(
    page_count: int,
    mode: SplitMode,
    every_n: int | None = None,
    ranges_spec: str | None = None,
) -> List[List[int]]:
    """모드별 0-based 인덱스 그룹 리스트를 반환.

    - SINGLE  -> [[0],[1],...,[n-1]]
    - EVERY_N -> [[0..n-1 chunks of every_n]]  (every_n>=1 필수)
    - RANGES  -> parse_page_ranges(ranges_spec, page_count)
    page_count<=0 또는 모드별 필수 인자 누락 시 ValueError.
    """
```

### 파서 알고리즘

1. `spec.strip()` 비었으면 ValueError.
2. `,`로 분할, 각 토큰 `strip()`. 빈 토큰 ValueError.
3. 토큰에 `-` 있으면 `start-end`로 분해(정확히 2조각, 정수), 없으면 단일.
4. 1-based 검증: `1 <= v <= page_count`, 범위는 `start <= end`.
5. 0-based로 변환해 그룹 추가.

---

## 3. `DocumentSession` 신규 메서드

### 3.1 `split_document`

```python
def split_document(
    self, output_dir: str, groups: List[List[int]], base_name: str | None = None
) -> List[str]:
    """groups의 각 인덱스 묶음을 개별 PDF로 output_dir에 저장. 원본 불변.

    파일명: f"{base}_{i+1:03d}.pdf" (base 기본값 = 원본 파일명 stem 또는 'split').
    Returns: 생성된 파일 경로 리스트.
    Raises:
      ValueError: groups 비었음/빈 그룹 포함/output_dir 미존재/base_name 비정상,
      IndexError: 인덱스 범위 초과.
    """
```

- 검증: `extract_pages`와 동일 패턴(디렉터리 존재, 인덱스 범위). 추가로 각 그룹 비어있지 않음.
- 쓰기: 그룹마다 `new_doc=fitz.open()` → `insert_pdf(self.doc, from_page=idx, to_page=idx)` 반복 → `save` → `finally: close`.
- 원본경로 충돌 방지: 생성 경로가 `self.file_path`와 같으면 ValueError.
- `modified`/history 미변경 (읽기 전용).

### 3.2 `merge_pdfs` (+ `merge_pdf` 위임)

```python
def merge_pdfs(self, source_paths: List[str], after_index: int = -1) -> int:
    """여러 PDF를 선택 순서대로 after_index 뒤에 연속 삽입. 삽입 페이지 총수 반환."""
    # 검증: 빈 리스트 거부, 각 파일 존재/유효, after_index 범위.
    # start_at = page_count if -1 else after_index+1
    # 파일마다: open -> insert_pdf(src, start_at=cursor) -> cursor += src.page_count -> close(finally)
    # 끝에 _rebuild_after_reorder() 1회.

def merge_pdf(self, source_path: str, after_index: int = -1) -> int:
    return self.merge_pdfs([source_path], after_index)
```

> 기존 `merge_pdf`의 단일 검증·로그는 `merge_pdfs`로 흡수. 반환 계약(삽입 페이지 수) 동일 → 기존 테스트/호출부 영향 없음.

---

## 4. `Controller` 위임

`extract_pages`/`merge_pdf`와 동일한 try/except + `error_occurred.emit` 패턴:

```python
def split_document(self, output_dir, groups, base_name=None) -> list:
    if not self._session: return []
    try:
        return self._session.split_document(output_dir, groups, base_name)
    except Exception as e:
        self.logger.error(...); self.error_occurred.emit(str(e)); return []

def merge_pdfs(self, source_paths, after_index=-1) -> bool:
    # merge_pdf와 동일 패턴, operation_applied.emit()
```

> split은 파일 경로 리스트를 돌려줘야 UI가 결과를 안내하므로 `list` 반환(실패 시 빈 리스트).

---

## 5. UI

### 5.1 `app/split_dialog.py` (신규)

`QDialog`로 모드 선택(QRadioButton 3개) + 파라미터:
- SINGLE: 파라미터 없음
- EVERY_N: `QSpinBox`(1..page_count)
- RANGES: `QLineEdit`(placeholder `"1-3, 5, 7-9"`)
- 출력 폴더: `QLineEdit` + "찾아보기"(`QFileDialog.getExistingDirectory`)

`accept()` 시 입력을 검증 가능한 형태(mode/every_n/ranges_spec/output_dir)로 노출하는 getter 제공. 실제 분할은 호출측(PageManagerDialog)에서 `compute_split_groups`→`controller.split_document`.

### 5.2 `PageManagerDialog` 변경

- 툴바에 `split_action` 추가 → `_split_document()`:
  1. 문서 없거나 0페이지면 안내.
  2. `SplitDialog` 실행. 취소면 종료.
  3. `compute_split_groups(page_count, mode, every_n, ranges_spec)` (ValueError → 경고).
  4. `controller.split_document(out_dir, groups, base)` → 성공 시 생성 파일 수 안내.
  5. 분할은 원본 불변이므로 `_mark_changed()` **호출 안 함**.
- `_merge_pdf` → 다중 선택으로 확장: `getOpenFileNames`, `controller.merge_pdfs(paths, after_index)`.

---

## 6. i18n 키 (en/ko)

```
page_manager.split / .split.tooltip
split.title, split.mode.single, split.mode.every_n, split.mode.ranges,
split.every_n.label, split.ranges.label, split.ranges.placeholder,
split.output_dir.label, split.browse, split.ok, split.cancel,
split.output_dir.required, split.success (생성 {0}개),
split.error.invalid_ranges, split.error.no_output_dir,
page_manager.merge.success_multi (병합 {0}개 파일)
```

---

## 7. 테스트 설계

### `tests/test_page_split.py` (순수 + 통합)
- 파서: `"1-3,5,7-9"` 정상, 공백 허용, 역순 `"5-3"` ValueError, 초과 `"1-99"` ValueError, 0 `"0-2"` ValueError, 빈 `""`/`"1,,2"` ValueError, 단일 `"3"`.
- 그룹: SINGLE(n그룹), EVERY_N(2,3 등 묶음·나머지), RANGES 위임.
- `split_document`: SINGLE→파일 n개 각 1p, EVERY_N(2)→ceil(n/2)개, RANGES→그룹수개·페이지구성 일치, 원본 page_count 불변, 잘못된 out_dir/빈 그룹 예외, 원본 덮어쓰기 거부.
- `merge_pdfs`: 2개 파일 순서 병합 후 page_count 합산·순서 확인, 빈 리스트 ValueError, `merge_pdf` 단일 위임 동작.

### `tests/test_i18n_validation.py` / 기존 키 테스트
- 신규 키 en/ko 양쪽 존재(기존 검증 스크립트가 자동 커버).

---

## 8. 영향 범위 / 회귀

- `merge_pdf` 시그니처·반환 불변(위임) → 기존 `test_page_management` 병합 테스트 영향 없음.
- 신규 파일/메서드 위주, 기존 경로 비침습 → 146 테스트 그대로 통과 예상.
- `page_split.py`는 순수·타입완비 → mypy strict 게이트에 추가 가능.
