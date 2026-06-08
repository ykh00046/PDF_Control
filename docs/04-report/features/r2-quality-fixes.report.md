# R2 Quality Fixes - Completion Report

> **Summary**: Critical 버그(get_text_length API) 수정 + mypy strict 게이트 확대 완료 보고
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-02
> **Status**: ✅ Completed
> **Match Rate**: 100%
> **Cycle**: r2-quality-fixes (Plan → Design → Do → Check → Report)

---

## 1. 개요

1차 종합 분석에서 도출된 코드 품질 개선점 3건을 단일 PDCA 사이클로 처리했다. 코드 재검증 결과 #3은 이미 해결되어 있어 회귀 검증으로 대체하고, #1(Critical)·#2에 집중했다.

## 2. 결과 요약

| # | 항목 | 결과 |
|---|------|------|
| 1 | `get_text_length` API 깨짐 | ✅ 수정 — Replace 저장/미리보기 복구 |
| 1b | autofit 축소 경고 누락 (발견된 설계갭) | ✅ 보너스 수정 |
| 2 | mypy strict 게이트 확대 | ✅ 6개 모듈 추가 (config/logger/path_helper/text_utils/text_metadata/fonts) |
| 3 | Preview/Save DRY | ✅ 이미 통합됨 확인, 회귀 없음 |

**테스트: 11 failed → 0 failed (128 passed)**

## 3. 변경 파일

| 파일 | 변경 |
|------|------|
| `app/operations/applicator.py` | get_text_length → `fitz.Font.text_length`; initial-fit 시 축소 생략; autofit 축소 경고 emit |
| `app/text_metadata.py` | `dict` → `Dict[str, Any]` 반환 타입 |
| `app/fonts.py` | 반환 타입 annotation, None-narrowing |
| `app/config.py` | `Dict[str, Any]` type-arg |
| `app/logger.py` | 함수 6종 annotation, handler 타입 명시, `Any` import |
| `app/path_helper.py` | `sys._MEIPASS` `type: ignore[attr-defined]` |
| `mypy.ini` | 6개 leaf 모듈 strict 게이트 추가; 차기 사이클 모듈 명시 |
| `tests/test_mypy.py` | `test_strict_leaf_modules_pass_mypy` 게이트 추가 |

## 4. 핵심 기술 결정

1. **`fitz.Font.text_length()` 채택** (모듈 함수 대신): base14·커스텀 fontfile 모두 지원. Font는 바이너리서치 루프 밖에서 1회 생성하여 재사용.
2. **initial-fit 시 축소 생략**: 텍스트가 원래 크기에서 들어가면 폰트 유지 → 시각적 동등성 보존 + 불필요한 `text.shrunk` 경고 방지.
3. **autofit 축소 경고 emit**: 폴백(`_insert_with_shrink`)뿐 아니라 autofit 경로에서도 축소를 사용자에게 보고.
4. **게이트 실효화**: mypy.ini 설정만으로는 CI 차단이 안 되므로 `test_mypy.py`에 leaf 모듈 검사 테스트 추가.

## 5. 교훈 (Lessons)

- **stale 문서 함정**: 1차 분석의 "Preview/Save DRY 위반"은 2026-01-30 문서 기반 오판이었다. 코드 재검증으로 정정 → 불필요한 재구현 회피.
- **측정 오염 주의**: `mypy.ini`의 기존 `ignore_errors=True`가 사전 strict 측정을 0으로 왜곡. 게이트 활성화 후 실측 필수.
- **버그가 버그를 가린다**: get_text_length 예외가 autofit 전체를 무력화해 축소 경고 갭을 은폐하고 있었다.

## 6. 잔여/후속

- `/pdca plan typing-legacy-core` — document_session(16)·model·pdf_engine strict 전환
- 신규 기능 큐(page-undo-redo, watermark, ocr) 유지
