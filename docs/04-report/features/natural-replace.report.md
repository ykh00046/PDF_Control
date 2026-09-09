# natural-replace Completion Report

> **Status**: Complete
> **Project**: PDF Control
> **Completion Date**: 2026-09-09
> **PDCA Cycle**: natural-replace

## 1. Executive Summary

교체 텍스트가 원문과 구별되지 않도록 삽입 파이프라인을 재설계했다. 베이스라인 오차
1.38pt → 0, 표 숫자 정렬 유지, 배경색 자동 매칭, 줄 내 여유 공간 활용, 문단 줄간격 보존,
축소 시 이웃 겹침 제거. 새 교체 대화상자로 정렬·크기·줄바꿈을 선택할 수 있다.
454 tests pass (신규 20), ruff 0, mypy strict(operations/text_metadata) 0.

## 2. Deliverables

| Deliverable | Location | Status |
|---|---|:---:|
| 페이지 프로브 | `app/page_probe.py` (신규) — `sample_background_color`, `line_free_space`, `glyph_follows`, `baseline_pitch`, `is_numeric_text` | Complete |
| 메타데이터 확장 | `app/text_metadata.py`, `app/operations/types.py` — `line_pitch`, `limit_left/right`, `source_text`, `glyph_after`; words/drawings 캐시 인자 | Complete |
| 삽입 재설계 | `app/operations/applicator.py` — `TextLayout`, `_compute_text_layout`(맞춤→확장→줄바꿈→축소), `_wrap_lines`, 줄별 `insert_text`, `_background_fills`, `_auto_align` | Complete |
| 리댁션 fill | `app/operations/redact.py` — `apply(page, fill=)`, `ALIGN_*` 상수, `align=ALIGN_AUTO` 기본 | Complete |
| 설정 | `app/config.py` — `TEXT_EXTEND_MAX_RATIO`, `TEXT_EXTEND_MIN_FONT_FACTOR`, `TEXT_WORD_GAP_FACTOR` | Complete |
| 교체 대화상자 | `app/replace_dialog.py` (신규), `handlers/edit_handlers.py` 연결, i18n 10키 | Complete |
| Tests | `tests/test_natural_replace.py` 20종 + 기존 wrap/warning/fidelity 테스트 무수정 통과 | Complete |
| 실측 | `logs/review/replace/sheet.png`(before) → `sheet2.png`/`sheet3.png`(after) | Complete |

## 3. Key Implementation Notes

- **insert_textbox를 버린 이유**: 첫 줄 베이스라인이 페이지에 남아 있는 폰트 리소스의
  메트릭을 따르므로 사전 보정이 불가능(실문서 −1.38pt). `insert_text(point)`는 모든 폰트에서
  오차 0(Base-14, Arial, Malgun, Times 실측).
- **확장 한도 설계**: 빈 페이지(테스트)에서는 이웃이 없어 "무한 확장"이 되므로
  `max(원폭×1.5, 8×크기)` 상한을 둬 기존 wrap-first 테스트 의미를 보존. 실문서에서는
  이웃 글리프/괘선이 먼저 제한한다.
- **숫자 정렬 규칙**: "Invoice 12345 due"처럼 뒤에 글리프가 이어지면 문장이므로 왼쪽,
  표 셀·줄 끝이면 오른쪽. 자동 정렬이 고른 쪽에 공간이 없으면("Ref: 77"→"78901") 반대쪽으로.
- **배경 샘플링 비용**: op마다 렌더하지 않고 72dpi 페이지 픽스맵 1회를 공유. 링에 섞인
  글리프 픽셀은 소수라 최빈색이 배경이 된다.
- **같은 폰트·크기·베이스라인이면 span이 합쳐진다** — "Ref: 78901"이 하나의 span으로
  추출되는 것이 "원문처럼 보인다"의 정량 지표.

## 4. Deferred

- 배치 교체 대화상자에 정렬 선택(현재는 자동 정렬 적용).
- 교체 대화상자 내 실시간 미리보기.
- 줄 내 리플로우(뒤 단어 밀기) — 서브셋 폰트 재삽입 충실도 문제로 보류.
