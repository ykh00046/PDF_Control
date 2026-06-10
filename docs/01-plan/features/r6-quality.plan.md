# R6 Quality - Plan

> **Summary**: 2026-06-10 전체 검토의 코드 품질 개선분 — controller 예외 가드 공통화(14곳 중복 제거), applicator 분해(최대 함수 ~150줄 + 함수 내 지연 import 6회 정리), mypy strict 게이트를 `pdf_engine`/`document_session`/`model`로 확장(typing-legacy-core 해소)
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-10
> **Status**: ✅ Completed (2026-06-10, 매치율 100%, 226 passed)
> **Cycle**: r6-quality

---

## 1. 배경 (Why)

2026-06-10 code-analyzer 분석에서 확인된 구조 품질 이슈 3건:

- **M1 (controller 예외 평탄화)**: `controller.py`의 페이지 관리·내보내기 메서드 10곳이 동일한 `if not session → try → emit → except Exception → log → error_occurred.emit → return` 보일러플레이트를 반복(DRY 위반). 사용자 입력 검증 오류(`ValueError` — 예: "Cannot delete all pages")와 내부 버그가 같은 로그 레벨·같은 경로로 평탄화된다.
- **M2 (applicator 복잡도)**: `applicator.py`(624줄, 최대 파일)의 `_insert_text_with_autofit`가 ~150줄(wrap 판정 + 이진탐색 축소 + 3종 경고를 한 함수에서). `from app.model import ...` 지연 import가 메서드 본문 안에 6회 반복 — 실제로는 형제 모듈(`app.operations.redact` 등)과 `app.text_metadata`에서 직접 import하면 순환이 없어 모듈 상단으로 올릴 수 있다.
- **M3 (typing-legacy-core)**: `mypy.ini`가 `model`/`pdf_engine`/`document_session`을 `ignore_errors=True`로 제외 중(차기 과제로 명시돼 있던 항목). `pdf_engine`은 거의 완료 상태(시그니처 느슨함만), `document_session`은 반환 타입 누락 위주, `model`은 재-export 셰임이라 거의 무료.

## 2. 목표 (What)

### 필수 (Must)

- **M1**: controller에 `_run_session_action(action, func, *, applied, default)` 가드 헬퍼 신설. 페이지 관리·내보내기 10개 메서드를 위임으로 전환. `ValueError`(사용자 검증 오류)는 warning 로그, 그 외는 error 로그로 분리 — `error_occurred` emit 동작은 유지. 미사용 import(fitz, op 클래스 4종) 제거.
- **M2**: applicator의 지연 import 6곳을 모듈 상단 직수입(`app.operations.crop/redact/remove_section`, `app.text_metadata`)으로 통합. `_insert_text_with_autofit`를 레이아웃 계산(`_compute_text_layout`: wrap 시도 + 축소 폴백)과 삽입/경고 단계로 분해 — **동작 불변**(동일 이진탐색·동일 경고 코드·동일 폴백 순서).
- **M3**: mypy strict 게이트에 `app.pdf_engine`, `app.document_session`, `app.model` 추가(`warn_return_any=False` — fitz 무스텁로 인한 Any 반환 허용, operations 게이트와 동일 정책). 누락 어노테이션 보강, `operations_service` 셰임 경유 import를 `app.operations` 직수입으로 교체. `tests/test_mypy.py` STRICT_LEAF_MODULES에 3개 모듈 추가.

### 권장 (Should)

- **S1**: controller 가드 분기(세션 없음 / ValueError / 내부 오류) 직접 단위 테스트 신설.

### 범위 외 (Won't)

- 에러 메시지 i18n화 — emit 텍스트는 예외 문자열 그대로(현행 유지). 단 `add_operation`의 emit이 `"Failed to add operation: {e}"` → `str(e)`로 통일됨(접두어 제거)은 허용 — UI는 메시지를 그대로 표시할 뿐이고 테스트는 포맷 비의존(확인 완료).
- ui/handlers 계층 strict — 비용 대비 효과 낮음(Qt 믹스인 패턴), 보류.
- RemoveSection 비동기화, 히스토리 정책 통일 — R7.

## 3. 성공 기준 (Acceptance)

- [ ] 전체 테스트 221개+ 전부 통과 (Python 3.13).
- [ ] controller: 가드 헬퍼 1곳 + 위임 10곳, `except Exception` 중복 블록 제거. 미사용 import 0.
- [ ] applicator: 함수 내 `from app.model` import 0건, `_insert_text_with_autofit` 본문 ≤ ~60줄, 경고 코드(`text.shrunk`/`text.wrapped`/`text.overflow`) 동작 불변(기존 wrap/warning 테스트 통과로 검증).
- [ ] `mypy -p app.operations` + 확장된 leaf 목록(`pdf_engine`, `document_session`, `model` 포함) strict 0 에러.
- [ ] Gap 분석 매치율 ≥ 90%.

## 4. 영향 범위 (Scope)

| 파일 | 변경 |
|---|---|
| `app/controller.py` | 가드 헬퍼 + 10개 메서드 위임 + import 정리 (M1) |
| `app/operations/applicator.py` | 상단 import 통합 + autofit 분해 (M2) |
| `app/pdf_engine.py` | 시그니처 타입 보강 (M3) |
| `app/document_session.py` | 반환/인자 어노테이션 보강 (M3) |
| `mypy.ini` | 3개 모듈 strict 전환 (M3) |
| `tests/test_mypy.py` | STRICT_LEAF_MODULES 확장 (M3) |
| `tests/test_controller_guard.py` | 신규 (S1) |

## 5. 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| applicator 분해 중 경고 의미 변동 | 기존 `test_text_wrap.py`/`test_long_text_warning.py`/`test_warning_report.py`가 경고 코드·세버리티를 직접 검증 — 회귀 즉시 검출 |
| 상단 import로 순환 재발 | import 체인 사전 확인 완료: `operations.redact/crop/remove_section/base`·`text_metadata`는 `app.model`을 import하지 않음 |
| controller emit 메시지 변화가 UI 깨뜨림 | UI는 문자열 표시만, 테스트는 `errors` 존재만 검증(확인 완료) |
| strict 확장이 fitz Any로 불가능 | operations 게이트와 동일하게 `warn_return_any=False` 완화 적용 |
