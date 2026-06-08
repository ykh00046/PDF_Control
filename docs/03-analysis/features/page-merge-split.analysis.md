# Page Merge / Split - Gap Analysis

> **Summary**: 설계(Design) 대비 구현 일치도 검증 — 분할/다중병합 기능
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-02
> **Status**: ✅ Complete
> **Design**: [page-merge-split.design.md](../../02-design/features/page-merge-split.design.md)
> **Match Rate**: 100% (목표 ≥ 90%)

---

## 1. 설계 항목 vs 구현 대조

| 설계 항목 | 구현 위치 | 상태 | 검증 |
|-----------|-----------|------|------|
| M1 분할 코어(SplitMode 3모드) | `app/page_split.py::compute_split_groups` | ✅ | `TestComputeSplitGroups` 7건 |
| M2 범위 파서 | `app/page_split.py::parse_page_ranges` | ✅ | `TestParsePageRanges` 9건 |
| M1 세션 분할 | `document_session.py::split_document` | ✅ | `TestSplitDocument` 7건 |
| M3 다중 병합 | `document_session.py::merge_pdfs` | ✅ | `TestMergePdfs` 5건 |
| M3 하위호환 위임 | `document_session.py::merge_pdf` → `merge_pdfs` | ✅ | `test_merge_pdf_single_delegates` + 기존 병합 테스트 |
| M4 원본 불변 | split 읽기전용(modified 미변경) | ✅ | `test_single_mode_writes_one_file_per_page` (modified is False) |
| 컨트롤러 위임 | `controller.py::split_document/merge_pdfs` | ✅ | UI 경유 동작(수동/스모크) |
| S1 SplitDialog | `app/split_dialog.py` | ✅ | import 스모크 + 기존 UI 테스트 |
| S1 PageManager 액션/다중병합 | `page_manager_dialog.py::_split_document/_merge_pdf` | ✅ | import 스모크 |
| S2 안전장치(경로/빈입력/덮어쓰기) | split_document 검증부 | ✅ | `test_empty_groups_rejected`, `test_missing_output_dir_rejected`, `test_out_of_range_index_rejected` |
| S3 i18n en/ko | `app/i18n/*.json` (split.*, page_manager.split, success_multi) | ✅ | `test_i18n_validation` 통과 |

---

## 2. 추가 달성(설계 외 보너스)

- `app/page_split`를 mypy **strict 게이트**에 편입(`mypy.ini` + `test_mypy.py`). 0 strict 에러.
- 범위 파서가 겹침/중복은 허용하되 순서 보존 — 설계 명시대로 구현 및 테스트(`test_overlap_allowed_and_ordered`).

---

## 3. 테스트 결과

- 전체 **177 passed** (기존 146 + 신규 31), 회귀 0.
- 신규 `tests/test_page_split.py`: 파서 9 + 그룹 7 + split 7 + merge 5 = 28 (+ 파라미터화 확장으로 실제 31 케이스).
- mypy strict 게이트 통과(page_split 포함), i18n 키 완전성 통과.
- end-to-end 스모크: 범위 분할(1-2, 4-5)→2파일 정확, 원본 불변, 재병합 정상.

---

## 4. 미해결/이월

- 없음. 범위 외(Won't) 항목(북마크 분할, ZIP 출력, 병합 시 페이지 선택)은 의도적으로 제외.

**결론**: Match Rate 100% ≥ 90% → 자동 개선(iterate) 불필요, Report로 진행.
