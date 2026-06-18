# watermark-position Gap Analysis

> **Date**: 2026-06-19 | **Status**: Complete | **Final Match Rate**: 100%

## Context Anchor

| Key | Value |
|---|---|
| WHY | 중앙 고정 워터마크의 본문 가림 해소 |
| WHO | 로고·상태 표시를 적용하는 PDF Control 사용자 |
| RISK | 회전 경계 및 구 payload 호환성 |
| SUCCESS | 5개 위치, 전 계층 전달, 전체 품질 게이트 통과 |
| SCOPE | Operation·직렬화·Controller·UI·i18n·테스트 |

## 1. Analysis Overview

Plan/Design/구현을 구조·기능·계약·런타임 네 축으로 비교했다. 이 기능에는 서버 API가 없으므로 계약은 Python 생성자와 settings/serialization payload를 대상으로 평가했다.

## 2. Success Criteria

| Criteria | Status | Evidence |
|---|:---:|---|
| SC-1: 텍스트·이미지 5개 위치 | Met | `tests/test_watermark.py` 위치/회전 렌더 테스트 |
| SC-2: 전달 계층·직렬화 보존 | Met | Controller 및 round-trip/legacy 테스트 |
| SC-3: UI 방출·타일 비활성화 | Met | 텍스트·이미지 pytest-qt 테스트 |
| SC-4: 전체 품질 게이트 | Met | 309 passed, ruff/mypy/diff check 통과 |

## 3. Static Match

| Axis | Initial | Final | Notes |
|---|---:|---:|---|
| Structural | 100% | 100% | 설계된 10개 코드/테스트 파일 변경 |
| Functional | 90% | 100% | 이미지 회전 배치 계산 보정 |
| Contract | 90% | 100% | Controller·Dialog 직접 테스트 보강 |

## 4. Runtime Verification

| Level | Result | Evidence |
|---|---|---|
| L1 unit | PASS | 집중 테스트 38건 |
| L2 UI action | PASS | pytest-qt 위치 payload/tile state |
| L3 integration | PASS | Controller→history, Operation→PDF 렌더 |
| L4 quality | PASS | ruff check/format, strict mypy |
| L5 regression | PASS | 전체 309 tests |

## 5. Gap List and Resolution

| Severity | Gap | Resolution |
|---|---|---|
| Important | 90° 이미지에서 회전 크기를 중복 반영해 여백 비대칭 가능 | `insert_image` target rect 기준으로 계산하도록 수정 |
| Important | 이미지 Dialog·Controller 위치 전달 직접 검증 부족 | 전용 테스트 추가 |

## 6. Match Rate

런타임 실행 공식 기준 최종: Structural 100×0.15 + Functional 100×0.25 + Contract 100×0.25 + Runtime 100×0.35 = **100%**.

## 7. Decision Verification

Option C, 36pt 고정 여백, 타일 우선, 문자열 Literal 결정이 모두 구현에 반영됐다. 전략적 이탈이나 미해결 Critical/Important gap은 없다.
