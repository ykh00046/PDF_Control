# R6 Quality - Gap Analysis

> **Summary**: 설계-구현 갭 분석 — 매치율 **100%** (M1-M3 + S1 전 항목), Act 불필요
>
> **Analyzer**: bkit gap-detector
> **Date**: 2026-06-10
> **Design**: [r6-quality.design.md](../../02-design/features/r6-quality.design.md)

---

## 매치율: 100%

| 항목 | 구현 증거 | 일치 |
|---|---|:--:|
| M1 `_run_session_action` 가드 (ValueError→warning / 기타→error / emit / default) | `app/controller.py:29-59` | ✅ |
| M1 위임 10곳 + int 결과 폐기 3곳(inner `run()`) + load/close/save/undo/redo 현행 유지 + 미사용 import 제거 | `controller.py` 전반, grep 0건 | ✅ |
| M2 함수 내 `from app.model` 0건 → 모듈 상단 직수입 | `applicator.py:34-39`, grep 0건 | ✅ |
| M2 `_insert_text_with_autofit` 분해 (~58줄) + `_compute_text_layout`/`_grow_rect_for_wrap`/`_shrink_fontsize_to_width` | `applicator.py:484-541, 543, 618, 654` | ✅ |
| M2 경고 코드·세버리티·이진탐색 동작 불변 | 기존 wrap/warning 테스트 전체 통과 | ✅ |
| M3 mypy strict 4모듈 승격 (model/document_model/pdf_engine/document_session) + 시그니처 타입화 + 셰임 우회 | `mypy.ini:62-75`, `pdf_engine.py`, `document_session.py`, `document_model.py` | ✅ |
| M3 STRICT_LEAF_MODULES 12개로 확대 | `tests/test_mypy.py:34-37` | ✅ |
| S1 가드 테스트 5건 | `tests/test_controller_guard.py` | ✅ |

- 검증: 전체 **226 passed** (221+5), `mypy -p app.operations` + 승격 4모듈 strict 0 에러.
- 갭: 누락 0, 무허가 동작 변경 0. 표기 차이(`Optional[X]` vs `X | None`)는 의미 동일.
- 설계 문서의 mypy.ini 스니펫에 `document_model` 블록 반영 완료(권장 조치).

## 결론

매치율 100% ≥ 90% → Act 생략, Report 진행.
