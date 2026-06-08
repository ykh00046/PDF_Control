# R2 Quality Fixes - Plan

> **Summary**: R2 품질 개선 사이클 — Critical 버그(get_text_length API) 수정 + mypy strict 게이트 확대 + Preview/Save DRY 재검증
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-02
> **Status**: 🔄 In Progress
> **Cycle**: r2-quality-fixes

---

## 1. 배경 (Why)

1차 종합 분석(2026-06-02)에서 코드 품질 개선점 3가지가 도출되었다. 실제 코드 재검증 결과 우선순위와 범위를 아래와 같이 확정한다.

| # | 항목 | 1차 분석 | 코드 재검증 결과 | 이번 사이클 조치 |
|---|------|----------|------------------|------------------|
| 1 | `get_text_length` API 깨짐 | Critical | **확정** — 11개 테스트 실패 | ✅ 수정 |
| 2 | mypy strict 범위 협소 | 개선 필요 | `app.operations.*`는 이미 strict, 레거시 모듈만 잔존 | ✅ 레거시 모듈로 확대 |
| 3 | Preview/Save DRY 위반 | 개선 필요 | **이미 해결** — `OperationApplicator`+`ApplyMode`로 통합 완료 | 🔍 회귀 검증만 |

> **정직성 노트**: #3은 2026-01-30 stale 분석 문서에 근거한 오판이었다. `app/pdf_engine.py`가 preview(`ApplyMode.PREVIEW`)·save(`ApplyMode.SAVE`) 모두 동일한 `apply_page_operations`를 호출하므로 코드 경로는 이미 단일화되어 있다. 재구현 대신 회귀 테스트로 보존만 확인한다.

---

## 2. 목표 (What)

### 필수 (Must)
- **M1**: `applicator.py:434` `page.get_text_length(...)` → PyMuPDF 1.26+ 호환 API로 교체
- **M2**: 11개 실패 테스트(test_smoke·regressions·preview_save_equivalence·long_text_warning) 전부 그린
- **M3**: mypy strict 게이트를 0-에러 레거시 모듈(`config`, `logger`, `path_helper`, `text_utils`)로 확대

### 권장 (Should)
- **S1**: `text_metadata`(1 에러)·`fonts`(3 에러) 소규모 타입 수정 후 strict 게이트 추가
- **S2**: #3 Preview/Save 단일 경로 회귀 검증 (`test_preview_save_equivalence` 통과 유지)

### 범위 외 (Won't — 차기 사이클)
- `document_session`(16 strict 에러), `model`, `pdf_engine` strict 전환 → 별도 `/pdca plan typing-legacy-core`
- 신규 기능(page-undo-redo, watermark, ocr 등)

---

## 3. 성공 기준 (Acceptance)

- [ ] `pytest` 127개 전체 통과 (현재 116 pass / 11 fail)
- [ ] `test_mypy` 게이트 통과 + 확대된 모듈 strict 무에러
- [ ] 기능 회귀 없음 (preview=save 동등성 유지)
- [ ] Replace 저장/미리보기 경로 정상 동작

---

## 4. 리스크

| 리스크 | 완화 |
|--------|------|
| `fitz.Font` 재생성 비용(루프 내) | 바이너리서치 루프 밖에서 1회 생성 후 재사용 |
| 커스텀 fontfile vs base14 fontname 분기 | `fitz.Font(fontname=..., fontfile=...)`가 양쪽 모두 수용 |
| strict 확대로 인한 신규 에러 | 0-에러 측정 완료 모듈만 우선 추가, 나머지는 수정 후 |

---

## 5. 작업 분해

1. M1: applicator autofit 폭 계산 API 교체
2. M3/S1: mypy.ini 게이트 확대 + text_metadata/fonts 타입 수정
3. Check: 전체 테스트 + mypy 검증
4. Report: 완료 보고
