# Text Fidelity - Gap Analysis

> **Summary**: 설계-구현 갭 분석 — 매치율 **98% → 보강 후 100%**, 미승인 동작 변경 0, Act 불필요
>
> **Analyzer**: bkit gap-detector
> **Date**: 2026-06-11
> **Design**: [text-fidelity.design.md](../../02-design/features/text-fidelity.design.md)

---

## 매치율: 98% (분석 시점) → 권장 보강 반영 후 잔여 갭 0

| 항목 | 구현 증거 | 일치 |
|---|---|:--:|
| M1 후보 생성(서브셋/공백/camelCase/플래그/패밀리, dedupe) | `fonts.py:84-120` | ✅ |
| M1 글리프 커버리지 프로브 + resolve | `fonts.py:123-153` | ✅ |
| M1 applicator 체인(메타 추출 → 해석, 우선순위 3단, helv-always 교정) | `applicator.py:158-162, 237-270` | ✅ |
| M1 측정·삽입에 해석된 폰트 일관 사용 | `applicator.py:407-430` | ✅ |
| M2 baseline 추출(`min(origins)`)·TypedDict·앵커 공식·경계 가드 | `types.py:21`, `text_metadata.py:46,57`, `applicator.py:654-662` | ✅ |
| M3 추출 크기 신뢰(rect 추정은 무텍스트 폴백만) + docstring | `text_metadata.py:1-8, 48-67` | ✅ |
| S1 단일 교체 우선순위(사용자 > 원본 매칭 > 한글 기본) | `edit_handlers.py:127-156, 178-181` | ✅ |
| 테스트 단위 12 + 통합 | `test_font_matching.py`, `test_text_fidelity.py` | ✅ |

## 플래그 검토 (미승인 동작 변경)

1. **사용자 명시 폰트 오버라이드** — 없음: `op.fontfile` 1순위 선점.
2. **preview=save** — 유지: 폰트/크기/베이스라인 산출은 mode 무관 단일 경로 (mode는 클리어 방식·미리보기 회색만).
3. **op.fontname 별칭 도출 잔존** — 실질 경로 없음 (메타 부재 시 방어 폴백만).

## 유일 갭과 해소

- 글리프 커버리지 거부가 **단위 수준만** 검증되고 applicator 다운스트림 폴백 e2e 미커버 → `test_uncovered_match_is_not_embedded_end_to_end` 추가(한글 교체 시 Arial 미임베딩 검증) + 설계 §4 표 동기화로 해소.

## 검증

- 전체 **254 passed** (235 + 신규 19), mypy strict(operations·fonts·text_metadata) 0 에러.
- 실측 프로브: 교체 결과가 원본과 동일 베이스라인(200.0→200.0)·동일 크기(10.0pt)·ArialMT 매칭 확인.
- 참고: `test_async_rendering_and_cache` 1회 타이밍 플레이크(전체 실행 시 렌더 워커 경합) — 단독·재실행 통과, 본 사이클 무관. 뷰어 race 테스트 부재(검토 M7)의 알려진 영역.

## 결론

매치율 ≥ 90% → Act 생략, Report 진행.
