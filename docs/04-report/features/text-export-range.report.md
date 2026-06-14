# Text Export Range - Completion Report

> **Summary**: 텍스트 내보내기의 "페이지 범위" 옵션 완성 — UI는 있으나 백엔드가 끊겨 현재 페이지만 내보내지던 기능을 연결. 누락된 i18n 키도 복구. 기존 `parse_page_ranges` 재사용. 매치율 100%, **287 passed**
>
> **Author**: Claude (bkit)
> **Completed**: 2026-06-14
> **Cycle**: text-export-range
> **Match Rate**: 100%

---

## 1. 무엇이 끊겨 있었나

`TextExportDialog`는 "페이지 범위" 라디오 + 입력란을 이미 갖고 있었지만 `get_settings()`가 `scope`를 `"all"`/`"current"`로만 반환하고 `range_edit` 값을 읽지 않았다 — 사용자가 "3-7" 범위를 골라 입력해도 `"current"`로 떨어져 **현재 페이지만 조용히 내보내졌다**. 게다가 다이얼로그가 `tr()`로 참조하는 `text_export.scope.range`·`text_export.range.placeholder` i18n 키 자체가 **en/ko 양쪽에 없었다**(패리티 검사는 동수만 봐서 미검출). save-integrity와 같은 "UI는 있는데 백엔드 미연결" 패턴.

## 2. 수정

백엔드는 이미 완비돼 있었다 — `resolve_indices`가 page_indices를 정렬·중복제거하고, `parse_page_ranges`(page-merge-split 사이클)가 `"3-7, 10"`을 0-based 그룹으로 파싱하며, `controller.export_text`가 page_indices를 전달한다. **연결만** 했다:

- `get_settings()`: 3-scope(`all`/`current`/`range`) + range 문자열 반환.
- `apply_text_export`: `scope == "range"` 분기 — `parse_page_ranges`(재사용, 신규 파서 금지)로 파싱 → 평탄화 → page_indices. `ValueError`(빈/잘못된/범위초과)는 경고 메시지 후 중단(크래시 0).
- 누락 i18n 키 3종(`scope.range`, `range.placeholder`, 신규 `range.invalid`) en/ko 복구.

## 3. 검증

- 전체 **287 passed** (281 + 신규 6: range "1-2"/"1,3" 정확 export, 잘못된/빈 range ValueError, 다이얼로그 3-scope get_settings).
- 기존 경로 불변·파서 재사용·잘못된 range 안전 중단·i18n 양쪽 복구·flatten+정렬 — 갭 분석 5개 플래그 전부 안전.
- i18n 296/296.

## 4. 다음 (로드맵)

- 이미지 워터마크(`WatermarkImage`), pyproject/ruff. 풀 async-save는 보류.
- 이번에 발견했듯 i18n 패리티 검사가 "코드에서 tr()로 참조하나 양쪽에 없는 키"를 못 잡음 — 향후 validate_i18n에 tr() 참조 키 검증 추가가 후보(별도).
