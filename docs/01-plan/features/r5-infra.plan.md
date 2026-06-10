# R5 Infra - Plan

> **Summary**: 2026-06-10 전체 검토의 "개혁 제안" 1차분 — CI 도입(GitHub Actions), 의존성 버전 고정, 루트 정리(deprecated 문서·스크래치 스크립트·`ui_handlers` 셰임 제거)
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-10
> **Status**: ✅ Completed (2026-06-10, 매치율 100%, 221 passed)
> **Cycle**: r5-infra

---

## 1. 배경 (Why)

2026-06-10 전체 검토에서 코드 품질보다 **운영 인프라 부재**가 더 시급하다고 판정됐다.

- **CI 부재**: `.github/workflows` 없음. r4의 mypy.ini 인코딩 회귀가 커밋 후 로컬에서만 발견된 것이 직접 근거 — 테스트·mypy가 커밋 시점에 검증되지 않는다. 원격(github.com/ykh00046/PDF_Control)은 이미 존재.
- **의존성 무버전**: `requirements.txt` 5줄 전부 버전 미지정. PyMuPDF 1.26의 `get_text_length` 제거로 11개 테스트가 깨진 전례(r2)가 있다. 또한 테스트가 실제로 요구하는 `mypy`(test_mypy), `pytest-timeout`(timeout 마커), `PyYAML`(drift 가드)이 requirements에 **누락**돼 있어 신규 환경 재현이 불가능하다.
- **루트 오염**: deprecated 스텁 3개(`PROJECT_STATUS.md`, `IMPROVEMENT_PLAN.md`, `NEXT_STEPS.md`), 스크래치 스크립트 5개(`quick_test.py`, `verify_*.py` 2종, `check_pymupdf_api.py`, `generate_sample_pdf.py`)가 루트에 방치. `app/ui_handlers.py` 셰임은 "다음 PDCA 사이클 후 제거" 조건이 충족됐는데 `app/ui.py:37`이 아직 셰임 경유로 import 중.

## 2. 목표 (What)

### 필수 (Must)

- **M1**: `requirements.txt` 전 항목 핀 고정(현재 검증된 설치 버전 기준) + 테스트 의존성(mypy, pytest-timeout, PyYAML) 명시.
- **M2**: GitHub Actions CI — `windows-latest` + Python 3.13, `pip install -r requirements.txt` 후 `pytest tests -q`. push(main)/PR 트리거. Qt는 `QT_QPA_PLATFORM=offscreen`으로 결정적 실행.
- **M3**: `app/ui_handlers.py` 셰임 제거 — `app/ui.py`가 `app.handlers`에서 직접 import하도록 전환 후 셰임 삭제.
- **M4**: 루트 정리 — deprecated 문서 3개 → `docs/archive/legacy-root/`, 스크래치 스크립트 5개 → `scripts/` (이동 후에도 루트 cwd 기준 실행 가능하도록 경로 부트스트랩 보정). CLAUDE.md의 해당 참조 갱신.

### 권장 (Should)

- **S1**: CI에서 mypy 게이트가 pytest 경유로 함께 실행됨을 확인(별도 step 불필요 — `test_mypy.py`가 포함).

### 범위 외 (Won't)

- **pyproject.toml 통합 + ruff 도입** — 전 코드베이스 lint diff가 커서 별도 사이클(R5b 또는 R6 동반)로 분리. 과대 범위 방지.
- CI 배지, release 자동화, PyInstaller 빌드 CI — BUILD/RELEASE 문서 체계 그대로.
- `git push` — 커밋까지만, 푸시(CI 첫 실행)는 사용자 결정.

## 3. 성공 기준 (Acceptance)

- [ ] 전체 테스트 221개 전부 통과 유지 (Python 3.13).
- [ ] `requirements.txt`의 모든 패키지가 `==` 핀 + 테스트 의존성 포함, 해당 버전으로 현재 환경과 일치.
- [ ] `.github/workflows/ci.yml` 존재, 문법 유효(YAML 파스 통과).
- [ ] `app/ui_handlers.py` 부재 + 저장소 내 `ui_handlers` import 0건 + UI 테스트 통과.
- [ ] 루트에 deprecated 문서·스크래치 스크립트 0개, 이동된 스크립트는 `python scripts/<name>.py`로 실행 가능(경로 보정).
- [ ] Gap 분석 매치율 ≥ 90%.

## 4. 영향 범위 (Scope)

| 대상 | 변경 |
|---|---|
| `requirements.txt` | 핀 고정 + 테스트 의존성 3종 추가 |
| `.github/workflows/ci.yml` | 신규 |
| `app/ui.py` | import 경로 `app.ui_handlers` → `app.handlers` |
| `app/ui_handlers.py` | 삭제 |
| 루트 문서 3종 | `docs/archive/legacy-root/`로 git mv |
| 루트 스크립트 5종 | `scripts/`로 git mv + 경로 부트스트랩 |
| `CLAUDE.md` | 레거시 문서 참조 갱신 + R5 항목 추가 |

## 5. 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| 핀 버전이 CI(신규 설치)와 로컬 불일치 | 로컬 검증된 설치 버전 그대로 핀 — 동일 버전 설치 보장 |
| windows-latest에서 Qt 위젯 생성 실패 | `QT_QPA_PLATFORM=offscreen` 강제(렌더 워커 서브프로세스에도 상속) |
| 셰임 삭제가 외부 호출부 깨뜨림 | 저장소 전체 grep으로 import 0건 확인 후 삭제, 전체 테스트로 검증 |
| 이동 스크립트 실행 깨짐 | `sys.path` 부트스트랩(파일 위치 기준 부모 삽입) 추가 |
