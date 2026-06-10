# R5 Infra - Completion Report

> **Summary**: 운영 인프라 1차 개혁 완료 — GitHub Actions CI 신설, requirements 전 항목 핀 고정(+누락 테스트 의존성 명시), `ui_handlers` 셰임 제거, 루트 정리. 매치율 100%, 221 passed 유지
>
> **Author**: Claude (bkit)
> **Completed**: 2026-06-10
> **Cycle**: r5-infra
> **Match Rate**: 100%

---

## 1. 무엇을 했나

### CI 도입 (`.github/workflows/ci.yml` 신규)

- windows-latest + Python 3.13, `QT_QPA_PLATFORM=offscreen`(렌더 워커 서브프로세스 상속), push(main)/PR 트리거.
- 단일 step `pytest tests -q`가 mypy strict 게이트·i18n 검증·CLAUDE.md drift 가드를 전부 포함.
- 동기: r4의 mypy.ini cp949 회귀가 커밋 후 로컬에서만 발견된 사례. **첫 실행은 push 시점** — 현재 main이 origin 대비 ahead 상태이므로 push 필요.

### 의존성 핀 고정 (`requirements.txt`)

- 런타임: PySide6==6.10.1, PyMuPDF==1.26.6, Pillow==12.1.0
- 테스트: pytest==8.4.2, pytest-qt==4.5.0, **pytest-timeout==2.4.0, mypy==1.19.0, PyYAML==6.0.2** (기존 누락 — 신규 환경 재현 불가 원인)
- PyMuPDF 1.26 `get_text_length` 제거 전례(r2)를 핀 사유로 파일 주석에 명시.

### 셰임 제거 + 루트 정리

- `app/ui_handlers.py` 삭제 ("다음 사이클 후 제거" 조건 충족) — `app/ui.py`가 `app.handlers` 직수입.
- deprecated 문서 3종 → `docs/archive/legacy-root/` (PROJECT_STATUS, IMPROVEMENT_PLAN, NEXT_STEPS).
- 스크래치 스크립트 5종 → `scripts/` (app을 import하는 3종에 파일위치 기준 `sys.path` 부트스트랩 추가, cwd 무관 실행 보장).
- CLAUDE.md의 레거시 참조 절 2곳 갱신.

## 2. 검증

- 전체 테스트 **221 passed** (변경 전후 동일, Python 3.13)
- ci.yml YAML 파스 검증, 이동 스크립트 신규 위치 실행 확인
- Gap 분석 매치율 **100%** (16/16)

## 3. 보류 (의도적)

- **pyproject.toml + ruff**: 전 코드베이스 lint diff가 커서 별도 사이클로 분리.
- **push / CI 첫 실행**: 사용자 결정 — `git push` 시 CI가 처음 돈다.

## 4. 다음 (로드맵)

- **R6 품질**: controller 예외 가드 공통화(14곳 중복), applicator 분해(`_insert_text_with_autofit` ~150줄), `pdf_engine`→`document_session` mypy strict 확장
- **R7+**: RemoveSection 비동기화, 히스토리 정책 통일, watermark, text-export-range
