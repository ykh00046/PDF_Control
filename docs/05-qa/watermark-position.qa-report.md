# QA Report: watermark-position

> **Date**: 2026-06-19 | **Result**: QA_PASS

## 1. Test Scope

텍스트·이미지 위치 렌더링, 회전, 직렬화 호환성, Controller 전달, 두 Dialog의 위치 선택과 타일 상호작용, 전체 회귀를 검증했다.

## 2. Pre-Release Scan Results

`scripts/qa/pre-release-check.sh`가 저장소에 없어 플러그인 전용 사전 스캔은 N/A다. 프로젝트 네이티브 릴리스 게이트로 대체했다.

## 3. Results

| Level | Target | Result | Detail |
|---|---|:---:|---|
| L1 | Operation/helper/serialization | PASS | 집중 suite 포함 전체 통과 |
| L2 | Dialog UI action | PASS | pytest-qt |
| L3 | PDF 렌더·Controller 통합 | PASS | PyMuPDF 실 PDF 검증 |
| L4 | 정적 품질 | PASS | ruff check, format 76 files |
| L5 | 전체 데이터/회귀 | PASS | 309 passed |

## 4. Quality Gates

| Gate | Result |
|---|---|
| `py -3.13 -m pytest -q` | 309 passed |
| `ruff check app tests` | pass |
| `ruff format --check app tests` | 76 files formatted |
| configured strict mypy targets | 21 files, 0 issues |
| `git diff --check` | pass |

## 5. Notes

pytest cache 디렉터리에 대한 Windows 접근 경고 1건은 테스트 결과와 산출물에 영향을 주지 않는 환경 경고다. 기능 실패, 보안 문제, 미해결 결함은 0건이다.

## 6. Verdict

**QA_PASS** — Report 단계 진행 조건 충족.
