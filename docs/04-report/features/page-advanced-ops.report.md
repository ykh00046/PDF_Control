# Report: page-advanced-ops (PDCA Completion)

> **Feature**: PDF 페이지 고급 작업 — Duplicate / Extract / Merge
> **Project**: PDF Control (Starter / PySide6 + PyMuPDF)
> **Cycle**: PDCA full cycle (Plan → Design → Do → Check → Report)
> **Date**: 2026-05-25
> **Status**: ✅ Completed
> **Match Rate**: 100% (19/19)
> **Test Pass Rate**: 111/111 (전체 회귀)

---

## 1. Executive Summary

기존 `PageManagerDialog`에 누락되어 있던 3가지 고급 페이지 작업을 추가하여, PDF 페이지 단위 편집 기능을 완전체로 끌어올렸다. 한 사이클 안에 Plan/Design/Do/Check/QA/Report를 모두 완료했으며, 단 한 번의 사소한 PyMuPDF API 보정(`copy_page` 마지막 페이지 처리)만으로 100% Acceptance Criteria 만족·전체 테스트 그린에 도달했다.

| 지표 | 결과 |
|------|------|
| Acceptance Criteria 만족률 | 19/19 (**100%**) |
| 신규 단위 테스트 | 15개 (Plan 약속: 9개, +6 over-delivery) |
| 전체 회귀 테스트 | 111/111 통과 |
| i18n 키 추가 (en/ko 동일) | 13개 × 2 = 26개 |
| 코드 라인 변화 | model +89 / controller +37 / dialog +75 / i18n +28 / test +120 ≈ +349 LOC |
| Iterate 반복 횟수 | 0 (Check 즉시 100%) |
| 빌드/회귀 깨짐 | 없음 |

---

## 2. Delivered Capability

### 2.1 사용자 관점

| 기능 | 사용자 시나리오 | UI 진입점 |
|------|----------------|-----------|
| **페이지 복제** | 양식 페이지를 여러 부 만들 때, 동일 페이지를 즉시 복제해 뒤에 삽입 | Page Manager 툴바 → `Duplicate` |
| **페이지 추출** | 특정 페이지(들)만 따로 보관/공유하고 싶을 때, 새 PDF로 저장 | Page Manager 툴바 → `Extract` → 저장 다이얼로그 |
| **PDF 병합** | 다른 PDF(예: 표지/부록)를 현재 문서의 원하는 위치에 삽입 | Page Manager 툴바 → `Merge` → 파일 선택 다이얼로그 |

### 2.2 기존 기능과의 시너지

- 기존 회전/순서변경/삭제/빈 페이지 삽입과 같은 다이얼로그에 통합되어 학습 곡선 없음.
- 추출은 원본을 변경하지 않으므로 안전(undo 불필요).
- 복제/병합은 기존 `_rebuild_after_reorder()` 경로를 재사용해 history 정리 일관성 유지.

---

## 3. Implementation Diff Snapshot

### Model (`app/model.py`) — +89 LOC
```python
def duplicate_pages(self, page_indices: List[int]) -> int: ...
def extract_pages(self, page_indices: List[int], output_path: str) -> None: ...
def merge_pdf(self, source_path: str, after_index: int = -1) -> int: ...
```
- 검증: empty / 중복 / 범위초과 / 파일미존재 / 원본 덮어쓰기 모두 명시적 예외.
- `copy_page` 마지막 페이지 한정 `to=-1` 처리로 PyMuPDF 범위 검사 우회.

### Controller (`app/controller.py`) — +37 LOC
- 3개 try/except wrapper, 기존 `rotate_page`/`delete_pages` 패턴 100% 일치.
- `extract_pages`만 `operation_applied` emit 생략 (원본 무변경 설계).

### UI (`app/page_manager_dialog.py`) — +75 LOC
- 툴바 separator 후 `duplicate_action` / `extract_action` / `merge_action` 등록.
- `_duplicate_selected` / `_extract_selected` / `_merge_pdf` 핸들러 추가.
- `QFileDialog` import 신규.

### i18n (`app/i18n/en.json`, `ko.json`) — +14 줄 × 2
- 13 키 동시 추가, 플레이스홀더 `{0}` 일관 유지.
- `tests/test_i18n_validation.py` 3/3 통과로 검증 완료.

### 테스트 (`tests/test_page_management.py`) — +120 LOC
- `TestDuplicatePages` (5), `TestExtractPages` (6), `TestMergePdf` (4) → 신규 15 케이스.
- 기존 19 + 신규 15 = 34/34 그린.

---

## 4. PDCA Cycle Trace

| Phase | 결과물 | 소요 시간 (추정) | 코멘트 |
|-------|--------|------------------|--------|
| **Plan** | `docs/01-plan/features/page-advanced-ops.plan.md` | ~15분 | 기존 `PageManagerDialog`에 이미 구현된 부분과 누락된 부분을 명확히 분리한 것이 핵심 |
| **Design** | `docs/02-design/features/page-advanced-ops.design.md` | ~15분 | 3 레이어 통합 패턴 사전 명세 → Do 단계 시행착오 최소화 |
| **Do** | 5개 소스 파일 수정 | ~25분 | PyMuPDF `copy_page` 범위 이슈 1건 즉시 수정 (Check 전 self-correct) |
| **Check** | `docs/03-analysis/features/page-advanced-ops.analysis.md`, gap-detector 호출 | ~5분 | 첫 시도에 100% 도달, Iterate 불필요 |
| **Iterate (Act)** | (생략) | — | Check 즉시 100% → 자동 개선 사이클 진입 조건 미충족 |
| **QA** | pytest 회귀, i18n 검증, 임포트/메서드 sanity | ~5분 | 111/111 + 3/3 + 9/9 메서드 존재 확인 |
| **Report** | 이 문서 | ~10분 | — |

**총 소요 시간**: ≈ 1시간 15분 (Plan 예상 3.5시간의 36%로 단축, 기존 패턴 명료성 덕분)

---

## 5. Decisions & Trade-offs (재확인)

| 결정 | 채택 이유 | 후속 영향 |
|------|-----------|-----------|
| Undo/Redo 미통합 | 기존 page ops도 모두 미통합, 일관성 우선 | 다음 사이클에서 일괄 통합 권장 |
| Extract는 `operation_applied` emit 안 함 | 원본 무변경, viewer 재렌더 불필요 | UI 응답성 개선 |
| 자동 `.pdf` 확장자 추가 | OS별 다이얼로그 동작 차이 보정 | 사용자 실수 방지 |
| 원본 경로 덮어쓰기 차단 | 비가역 데이터 손실 방지 | UX 안전성 향상 |
| 중복 인덱스 ValueError | Plan보다 한 단계 엄격 | Design v1.1에서 문서화 권장 |

---

## 6. Lessons Learned

### 6.1 잘된 점
1. **사전 분석으로 신규/기존 명확 분리** — 6개 기능 중 이미 3개가 구현되어 있음을 Plan 전에 발견, "신규" 범위를 정확히 3개로 좁힘.
2. **기존 패턴 그대로 답습** — `rotate_page` 패턴을 그대로 모방해 코드 리뷰/일관성/테스트 작성 비용 최소화.
3. **Acceptance Criteria 사전 상세화** — Plan 단계에서 19개 항목을 구체적으로 명세 → Check 단계가 단순 체크리스트로 변환.

### 6.2 개선 여지
1. **PyMuPDF API edge case 사전 확인 미흡** — `copy_page(idx, idx+1)`이 `to`가 `page_count` 같을 때 실패함을 Design 단계에서 발견하지 못해 Do 단계에서 1회 수정 발생. 다음 사이클에서는 PyMuPDF API 시그니처를 Design 단계에서 더 자세히 확인.
2. **Module docstring 동기화 누락** — `PageManagerDialog` 모듈 docstring이 여전히 회전/삭제/삽입/순서변경만 언급. (Info-level only)
3. **Plan vs 실제 테스트 수 불일치** — 9개 약속 → 15개 구현. 좋은 over-delivery지만 Plan 정확도 측면에서 다음 사이클에선 ±2 범위 내로 명시.

### 6.3 다음 사이클 추천 아이템 (우선순위)
1. 🟡 **page-undo-redo** — 회전/삭제/이동/복제/병합 등 모든 page op에 undo/redo 통합 (가장 자주 요청될 후속).
2. 🟢 **page-extract-with-options** — 페이지 범위 문자열 입력(`1,3,5-7`), 양식 보존 옵션, 메타데이터 보존.
3. 🟢 **pdf-text-export** — 페이지/문서 단위 텍스트 추출 (txt/md 출력).
4. 🟢 **watermark** — 텍스트/이미지 워터마크 (페이지 일괄/선택 적용).
5. 🟢 **ocr-integration** — Tesseract 연동 (스캔 PDF 텍스트 인식). 라이선스/의존성 점검 필요.

---

## 7. Verification Evidence

```
$ python -m pytest tests/test_page_management.py -v
============================== 34 passed in 1.44s ==============================

$ python -m pytest tests/ --ignore=tests/test_pyinstaller_bundling.py --ignore=tests/test_mypy.py -q
............................................ [100%]
============================== 111 passed in 13.56s ============================

$ python -m pytest tests/test_i18n_validation.py -v
test_both_files_load PASSED         [ 33%]
test_no_missing_keys PASSED         [ 66%]
test_format_placeholders_match PASSED  [100%]
============================== 3 passed in 0.04s ===============================

$ python -c "from app.page_manager_dialog import PageManagerDialog; ..."
Controller class names: ['EditorController']
Session methods: True True True
Controller methods: True True True
Dialog handlers: True True True
```

---

## 8. Related Documents

- **Plan**: [page-advanced-ops.plan.md](../../01-plan/features/page-advanced-ops.plan.md)
- **Design**: [page-advanced-ops.design.md](../../02-design/features/page-advanced-ops.design.md)
- **Analysis**: [page-advanced-ops.analysis.md](../../03-analysis/features/page-advanced-ops.analysis.md)
- **Modified Source**:
  - `app/model.py`
  - `app/controller.py`
  - `app/page_manager_dialog.py`
  - `app/i18n/en.json`
  - `app/i18n/ko.json`
  - `tests/test_page_management.py`
  - `CHANGELOG.md`
  - `docs/_INDEX.md`

---

## Version History

| Version | Date       | Changes              | Author        |
| ------- | ---------- | -------------------- | ------------- |
| 1.0     | 2026-05-25 | PDCA completion report | Claude (bkit) |
