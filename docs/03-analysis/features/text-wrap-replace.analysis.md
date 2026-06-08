# Text Wrap Replace - Gap Analysis

> **Summary**: 설계(design) 대비 구현(implementation) 일치도 분석 — Check 단계
>
> **Author**: Claude (bkit / gap-detector 기준)
> **Created**: 2026-06-02
> **Status**: ✅ Done
> **Design**: [text-wrap-replace.design.md](../../02-design/features/text-wrap-replace.design.md)

---

## 1. 일치도 요약

| 항목 | 결과 |
|------|------|
| **Match Rate** | **100%** (필수/권장 전 항목 구현) |
| 신규 테스트 | 4/4 통과 |
| 전체 테스트 | 146 passed (회귀 0) |
| mypy strict 게이트 | 통과 (회귀 0) |
| 기능 검증(SAVE 렌더) | 통과 (3줄 줄바꿈, 텍스트 전량 보존) |

---

## 2. 설계 항목별 대조

| # | 설계 명세 | 구현 위치 | 상태 |
|---|-----------|-----------|------|
| M1 | 1줄 초과 시 폰트 축소 대신 박스 높이 확장 + 줄바꿈 | `applicator.py::_insert_text_with_autofit` (wrap-first 분기) | ✅ |
| M2 | 확장은 페이지 경계 내, 한계 시 축소 폴백 | `avail_h = page.rect.y1 - TEXT_WRAP_BOTTOM_MARGIN - y0`, `needed_h <= avail_h` 가드 | ✅ |
| M3 | 줄바꿈 시 `text.wrapped` (info) 경고 | `_insert_text_with_autofit` 말미 `elif wrapped_lines > 1` | ✅ |
| M4 | preview·save 동일 동작 | 시그니처 불변, 단일 `apply_operations` 경로 (`test_preview_save_equivalence` 통과) | ✅ |
| S1 | 폰트 메트릭으로 라인 수 사전 계산 | `_wrap_line_count` (greedy whitespace wrap) | ✅ |
| S2 | config 상수로 제어 | `TEXT_WRAP_ENABLED / _LINE_HEIGHT_FACTOR / _BOTTOM_MARGIN` | ✅ |

### 설계 초과 구현 (Bonus)
- `state_handlers.py`: 히스토리 패널에 `info` severity용 정보 아이콘 + `warn.history.badge_wrapped` 툴팁 추가 (설계엔 statusbar만 명시했으나 UX 일관성을 위해 확장).

---

## 3. 엣지 케이스 검증 결과

| 케이스 | 기대 | 실측 |
|--------|------|------|
| 짧은 단어들로 된 긴 텍스트 (폭 200, tall page) | 줄바꿈(info) | ✅ `text.wrapped` lines=3, 폰트 12pt 유지 |
| 긴 단어 "replacement"(99pt) > 폭(89pt) | 축소 폴백 | ✅ `text.shrunk` — 기존 테스트 보존 |
| 1x1 극단 박스 | overflow | ✅ `text.overflow` (error) — 기존 테스트 보존 |
| 페이지 하단 근처 박스 (세로 공간 부족) | 경계 내 폴백 | ✅ 페이지 초과 없음 |
| `TEXT_WRAP_ENABLED=False` | 기존 축소 동작 | ✅ `text.shrunk` |

---

## 4. 잔여 Gap / 차기 사이클 (Won't로 명시된 범위 외)

- Replace 다이얼로그에 사용자 토글 UI (현재 설정 상수 기본 on) → 후속
- 위/좌우 확장, 박스 드래그 리사이즈, justify/하이픈네이션 → 후속
- 아래쪽 *후속 콘텐츠* 침범 감지 (현재는 페이지 경계만 기준) → 후속

> 위 항목은 Plan에서 의도적으로 범위 외로 선언한 것으로 Gap이 아닌 **계획된 비포함**이다.

---

## 5. 결론

설계 100% 구현 + 설계 초과 UX 보강 1건. 회귀 0, 기능 검증 통과. **Match Rate ≥ 90% → 반복(iterate) 불필요, Report로 진행.**
