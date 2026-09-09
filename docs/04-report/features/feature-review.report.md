# feature-review Completion Report

> **Status**: Complete
> **Project**: PDF Control
> **Completion Date**: 2026-09-09
> **PDCA Cycle**: feature-review

## 1. Executive Summary

교체(natural-replace) 검토와 같은 방법 — 실제 문서에 기능을 적용하고 렌더/픽셀을
실측 — 으로 삭제·자르기·영역 제거·워터마크·페이지 관리·텍스트 내보내기·회전 페이지
편집을 전수 검토했다. 버그 2건(자르기 전면 실패, 회전 페이지 워터마크 오배치)과
자연스러움 2건(삭제 시 밑줄/음영 끊김, 빈 페이지 A4 고정)을 고쳤다.
474 tests pass (신규 13), ruff 0.

## 2. Findings → Fixes

| # | 기능 | 발견 | 조치 |
|---|---|---|---|
| 1 | 자르기 | `set_mediabox` 뒤 `set_cropbox(같은 rect)` → 모든 문서에서 "CropBox not in MediaBox" 예외. 여백을 회전 전 좌표에 적용해 회전 페이지에서 엉뚱한 변이 잘림 | mediabox만 설정; `visible_to_mediabox_margins(rotation, …)`로 표시 기준 여백 매핑 |
| 2 | 워터마크 | 회전 페이지에서 텍스트·이미지 모두 오배치·각도 어긋남(`TextWriter`/`insert_image`는 회전 전 좌표계) | 피벗/rect `derotation_matrix` 변환, 텍스트 각도 `+page.rotation`, 이미지 `rotate+page.rotation` |
| 3 | 삭제/교체(저장) | 채우기 사각형이 밑줄·셀 음영을 덮어 끊김 | 저장 리댁션 `fill=False`(글리프만 제거, 벡터 보존); 미리보기는 배경색 샘플 유지 |
| 4 | 빈 페이지 삽입 | 항상 A4 | 이웃 페이지 표시 크기 기본, 명시 크기는 그대로 |
| 5 | 일괄 찾기 | (앞 사이클) `Rect.expanded` 크래시 | 수정됨 |

정상 확인: 영역 제거(높이 축소·이미지 1개·29KB), 텍스트 내보내기(2단 순서·MD 헤더),
페이지 추출의 회전 보존, 회전 페이지 삭제/교체 좌표, 이웃 글자·표 테두리 보존.

## 3. Key Implementation Notes

- **PyMuPDF 좌표계 두 종류**: `search_for`/`get_text`/`insert_text`/redact annot은
  *회전 후*(page.rect) 좌표, `TextWriter.write_text`·`insert_image`·`mediabox`는
  *회전 전* 좌표. 회전 페이지를 다루는 코드는 어느 쪽인지 반드시 실측.
- **테스트 방법**: 회전 페이지 결과를 "같은 표시 크기의 비회전 페이지" 결과와 픽셀
  중심으로 비교(±2.5pt). 이미지 방향은 좌우 비대칭 픽스맵으로 검증.
- **`fill or WHITE` 함정**: `False`는 falsy라 흰색이 되어 버림 → `None` 검사로 분기.
- 미리보기(덮기)와 저장(제거)의 밑줄 표시 차이는 의도된 작은 불일치.

## 4. Deferred

- 미리보기에서도 밑줄을 살리려면 글리프 마스크 기반 덮기가 필요(비용 대비 보류).
- 영역 제거 시 페이지 테두리 같은 장식 벡터가 잘려 보이는 것은 사양(래스터화).
