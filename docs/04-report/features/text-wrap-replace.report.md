# Text Wrap Replace - Completion Report

> **Summary**: 긴 텍스트 교체 시 폰트 축소 대신 자동 줄바꿈(멀티라인 워드랩)으로 가독성·정보 보존 — 완료 보고
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-02
> **Status**: ✅ Completed
> **Match Rate**: 100%
> **Cycle**: text-wrap-replace (Plan → Design → Do → Check → Report)

---

## 1. 개요

전 PDCA 문서에 걸쳐 반복 등장한 **#1 미해결 사용성 이슈**("긴 텍스트가 좁은 영역에서 8pt까지 축소 후에도 삽입 실패")를 근본 해결했다.

기존 자동 맞춤(autofit)은 **폭 기반 폰트 축소만** 수행해 긴 텍스트를 6~8pt로 줄이거나(가독성 저하) overflow로 누락시켰다. `insert_textbox`가 이미 지원하는 자동 줄바꿈을 박스 높이가 1줄로 고정돼 활용하지 못한 것이 원인이었다. 이번 사이클은 **줄바꿈 우선(wrap-first)** 정책으로 전환했다.

## 2. 결과 요약

| 항목 | 결과 |
|------|------|
| 줄바꿈 우선 정책 | ✅ 1줄 초과 시 박스 높이를 페이지 경계 내에서 아래로 확장 → 폰트 유지 |
| 폰트 축소 | ✅ 줄바꿈 불가 시(긴 단어 폭 초과 / 세로 공간 부족) 폴백으로 재배치 |
| 신규 경고 | ✅ `text.wrapped` (info, 비차단) + i18n(en/ko) + statusbar + 히스토리 배지 |
| Preview = Save | ✅ 단일 경로 유지, 동등성 보존 |
| 테스트 | ✅ **146 passed** (신규 4 + 기존 전량, 회귀 0) |
| mypy strict | ✅ 게이트 회귀 0 |
| 기능 검증(SAVE) | ✅ 긴 문장이 **3줄 12pt로 전량 보존** 렌더 (이전: 6pt 축소/누락) |

## 3. 변경 파일

| 파일 | 변경 |
|------|------|
| `app/config.py` | `TEXT_WRAP_ENABLED`, `TEXT_WRAP_LINE_HEIGHT_FACTOR`, `TEXT_WRAP_BOTTOM_MARGIN` 추가 |
| `app/operations/applicator.py` | `_wrap_line_count` 헬퍼 추가; `_insert_text_with_autofit` 재구성(wrap-first → shrink 폴백); `text.wrapped` 경고 emit |
| `app/ui_statusbar.py` | `text.wrapped` 코드 표시 분기 추가 |
| `app/handlers/state_handlers.py` | 히스토리 패널 `info` severity 정보 아이콘/툴팁 추가 |
| `app/i18n/en.json`, `ko.json` | `warn.code.text.wrapped`, `warn.history.badge_wrapped` 추가 |
| `tests/test_text_wrap.py` | 신규 — wrap 발생 / 긴단어 폴백 / 페이지경계 / 정책 off |
| `tests/test_long_text_warning.py` | i18n required 키 집합에 wrapped 키 2종 추가 |

## 4. 핵심 기술 결정

1. **줄바꿈 우선, 축소는 폴백**: 폰트 축소는 가독성을 희생하므로, 세로 여백이 있으면 원 크기로 줄바꿈하는 것이 정보 보존·가독성 모두 우수. 긴 단어가 폭을 넘어 줄바꿈이 무의미한 경우에만 축소.
2. **라인 수 사전 계산**(`_wrap_line_count`): `insert_textbox`와 동일한 공백 기준 greedy wrap을 미리 시뮬레이션해 필요한 박스 높이를 산출 → `insert_textbox`는 기존대로 **1회만** 호출(SAVE 모드 이중 렌더 방지). 추정이 빗나가도 기존 `_insert_with_shrink` 폴백이 흡수.
3. **페이지 경계 가드**: 확장 높이를 `page.rect.y1 - TEXT_WRAP_BOTTOM_MARGIN`로 상한, 초과 시 축소 폴백 → 페이지 밖 침범 방지.
4. **`info` severity 채택**: 줄바꿈은 정보 보존에 성공한 정상 동작이므로 비차단. `has_blocking_warnings()`(error만)에 영향 없어 저장 흐름 방해 없음.

## 5. 기존 테스트 보존 근거 (정직성 노트)

`test_narrow_rect_long_text_emits_shrink_warning`("A somewhat long replacement")는 줄바꿈 우선 정책에도 **여전히 `text.shrunk`를 방출**한다. "replacement"(18pt에서 ~99pt)가 박스 폭(~89pt)을 넘는 unbreakable 토큰이라 `longest_token > target_width` 가드에 걸려 자연히 축소 폴백으로 빠지기 때문. 즉 테스트 수정 없이 기존 의미가 보존됐다.

## 6. 사용자 영향 (Before → After)

| 시나리오 | Before | After |
|----------|--------|-------|
| 한 줄을 긴 문장으로 교체 | 6~8pt 축소(읽기 어려움) | 원 크기로 여러 줄 줄바꿈 |
| 좁은 영역 + 긴 텍스트 | 축소 실패 시 글자 누락 | 세로 공간 활용해 보존 |
| 알림 | 축소/실패 경고만 | 줄바꿈 성공 정보(info) 안내 |

## 7. 차기 사이클 후보

- Replace 다이얼로그에 줄바꿈 on/off + 정렬 토글 **UI** 노출 (현재 설정 상수)
- 아래쪽 *후속 콘텐츠* 침범 감지(현재 페이지 경계만)
- `typing-legacy-core`: `document_session`/`model`/`pdf_engine` strict 전환 (기존 백로그)
