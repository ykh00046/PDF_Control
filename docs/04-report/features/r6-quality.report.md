# R6 Quality - Completion Report

> **Summary**: 코드 품질 개선 완료 — controller 예외 처리 14곳→가드 1곳, applicator 최대 함수 분해(150줄→58줄) + 지연 import 정리, typing-legacy-core 해소(strict 4모듈 승격). 매치율 100%, **226 passed**
>
> **Author**: Claude (bkit)
> **Completed**: 2026-06-10
> **Cycle**: r6-quality
> **Match Rate**: 100%

---

## 1. 무엇을 했나

### M1 — controller 예외 가드 공통화 (`app/controller.py`)

- 페이지 관리·내보내기 10개 메서드의 동일 `try/except Exception` 보일러플레이트를 `_run_session_action` 헬퍼 1곳으로 통합.
- **오류 등급 분리**: `ValueError`(사용자 검증 거부 — 예: "Cannot delete all pages")는 warning 로그, 그 외 내부 오류는 error 로그. `error_occurred` emit과 반환값 규약은 기존과 동일.
- 부수 버그 예방: `merge_pdfs`/`duplicate_pages`/`export_text`가 세션의 int 반환(0 가능)을 truthiness로 평가하지 않도록 결과를 명시적으로 폐기 — 0자 내보내기·빈 PDF 병합이 거짓 실패로 읽히지 않음.
- 미사용 import(fitz, op 클래스 4종) 제거. `load/close/save/undo/redo`는 특수 흐름(재raise·finally) 유지.

### M2 — applicator 분해 (`app/operations/applicator.py`)

- 함수 본문 내 `from app.model import` 6회 → 모듈 상단 직수입(형제 모듈 `operations.crop/redact/remove_section` + `text_metadata`). 순환 없음 사전 확인 — 기존 지연 import는 `app.model` 경유 때문이었고 직수입 경로엔 순환이 없다.
- `_insert_text_with_autofit` ~150줄 → 58줄 오케스트레이터 + `_compute_text_layout`(한줄 적합/wrap/축소 결정) + `_grow_rect_for_wrap`(wrap 가능성 판정·박스 확장) + `_shrink_fontsize_to_width`(이진탐색).
- **동작 불변**: 경고 코드(`text.shrunk`/`text.wrapped`/`text.overflow`)·세버리티·폴백 순서·이진탐색 반복수 동일. 기존 wrap/warning 테스트 전체 통과로 검증.

### M3 — typing-legacy-core 해소 (strict 4모듈 승격)

- `pdf_engine`, `document_session`, `document_model`, `model`을 mypy strict 게이트에 추가(`warn_return_any=False` — fitz 무스텁 정책, operations 게이트와 동일). 모두 **0 에러** 측정.
- `pdf_engine`: `Sequence[Operation]`, `logging.Logger | None`, `EncryptionSettings | None`, `ApplyResult | None` 등 시그니처 타입화. `operations_service` 셰임 경유 import를 `app.operations` 직수입으로 교체(document_session 동일).
- STRICT_LEAF_MODULES 8개 → **12개**. 남은 비-strict: ui/handlers/viewer/다이얼로그 계층(Qt 믹스인 — 비용 대비 효과 낮아 의도적 보류)과 `operations_service` 셰임.

## 2. 검증

- 전체 테스트 **226 passed** (기존 221 + 신규 가드 테스트 5)
- mypy: `app.operations` 패키지 + leaf 12모듈 strict 0 에러
- Gap 분석 매치율 **100%**
- 참고: R5의 CI 첫 실행 **성공** (windows-latest, 1m11s) — 이번 사이클부터 push 시 자동 검증

## 3. 다음 (로드맵)

- **R7+**: RemoveSection 비동기화(UI 프리징 해소), 히스토리 정책 통일(delete=보정 vs move/merge=폐기 비대칭), watermark, text-export-range
- **별도**: pyproject.toml + ruff
