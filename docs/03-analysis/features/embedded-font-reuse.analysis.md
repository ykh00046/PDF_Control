# Embedded Font Reuse - Gap Analysis

> **Summary**: 설계-구현 갭 분석 — 매치율 **100%** (M1-M3 + S1), 미승인 동작 변경 0. 갭 분석가 관찰(별칭 충돌)은 보강 반영. Act 불필요
>
> **Analyzer**: bkit gap-detector
> **Date**: 2026-06-13
> **Design**: [embedded-font-reuse.design.md](../../02-design/features/embedded-font-reuse.design.md)

---

## 매치율: 100%

| 항목 | 구현 증거 | 일치 |
|---|---|:--:|
| M1 `_font_covers` 추출 + `_font_file_covers` 래핑 | `fonts.py:123-140` | ✅ |
| M1 `extract_embedded_font` (후보 교집합·최구체 우선·`bytes()`·broad except·커버리지) | `fonts.py:143-200` | ✅ |
| M1 서브셋 자연 거부 (cmap 제거→has_glyph 0) | 커버리지 검사 자동 거부, `test_embedded_font_subset_rejected`로 고정 | ✅ |
| M2 resolved 3원소 + 우선순위 ①②③④ | `applicator.py` `_prepare_fonts` | ✅ |
| M2 추출 전·등록 후 분리(`_register_fonts` Pass 2.5) | 추출 redaction 전, 등록 후 | ✅ |
| M2 등록 실패→Base-14 강등 | `_register_fonts` except 분기 | ✅ |
| M2 `fontbuffer` 측정/삽입 플러밍 (buffer>file>name, 삽입은 별칭) | autofit/layout 파라미터 | ✅ |
| M3 테스트 6 + 별칭충돌 보강 1 (Arial 게이트) | `test_text_fidelity.py` | ✅ |
| S1 재사용 xref/basefont debug 로그 | `fonts.py:197-200` | ✅ |

## 검토관 질문 답변 (요지)

- **(a) preview=save** 유지 — 패스 순서는 모드 분기 바깥 단일 경로. PREVIEW는 `apply_redactions` 미호출이라 register-before 드롭 문제 자체가 없고, 후등록으로 옮겨도 양쪽 결과 동일.
- **(b) SAVE 파괴 전 추출** — 추출(`_prepare_fonts`)이 파괴적 redaction보다 엄격히 선행.
- **(c) 사용자 fontfile 우선** — 우선순위 1 분기 보존, else 안의 매칭/추출 미실행.
- **(d) 기존 system-match 회귀** — 없음. 체인은 순수 추가, `resolve_pdf_fontname` 비-None 시 추출 단락.

## 보강 (갭 분석 경미 관찰 반영)

- 임베디드 별칭 `"emb"+정규화명[:20]`의 절단 충돌(배치 다중 폰트 교체 시) → **crc32 내용 기반 별칭**으로 교체. `test_embedded_aliases_do_not_collide`(Arial+Times 동시 교체, 각자 서체 유지)로 회귀망 신설. `re` 미사용 import 제거.

## 검증

- 전체 **261 passed** (254 + 신규 7), mypy strict(operations + fonts) 0 에러.
- 구현 중 발견·해결: `apply_redactions`가 미참조 폰트 리소스를 스트립해 register-before가 "need font file or buffer"로 실패 → Pass 2.5(후등록) 분리로 해결.

## 결론

매치율 100% ≥ 90% → Act 생략, Report 진행.
