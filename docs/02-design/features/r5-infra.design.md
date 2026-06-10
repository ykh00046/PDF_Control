# R5 Infra - Design

> **Summary**: CI(GitHub Actions windows-latest) + requirements 핀 고정 + 루트/셰임 정리의 구체 설계
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-10
> **Status**: ✅ Completed (2026-06-10, 매치율 100%)
> **Plan**: [r5-infra.plan.md](../../01-plan/features/r5-infra.plan.md)

---

## 1. M1 — requirements.txt 핀 고정

2026-06-10 로컬(Python 3.13.x, 221 tests pass)에서 검증된 설치 버전 그대로:

```
# Runtime
PySide6==6.10.1
PyMuPDF==1.26.6
Pillow==12.1.0

# Test / QA (tests/ 가 직접 요구: test_mypy -> mypy, timeout 마커 -> pytest-timeout,
# drift 가드 -> PyYAML)
pytest==8.4.2
pytest-qt==4.5.0
pytest-timeout==2.4.0
mypy==1.19.0
PyYAML==6.0.2
```

- `==` 핀 채택(상한 지정 대신): 데스크톱 앱 + CI 재현성 우선. 업그레이드는 의도적 PR로.
- `requirements-build.txt`는 `-r requirements.txt` 참조 구조 그대로(변경 없음).

## 2. M2 — `.github/workflows/ci.yml`

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

env:
  # Deterministic headless Qt on the runner; inherited by the render-worker
  # subprocess as well.
  QT_QPA_PLATFORM: offscreen

jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
          cache: pip
      - run: pip install -r requirements.txt
      - run: python -m pytest tests -q
```

- 단일 잡: `pytest tests -q`에 mypy 게이트(`test_mypy.py`)·i18n·drift 가드가 이미 포함(S1) — 별도 step 불필요.
- `windows-latest` 채택: 실사용 플랫폼과 동일(경로·인코딩·frozen 가정). cp949 회귀는 러너(UTF-8 로케일)에서 재현 안 되지만 mypy.ini ASCII 가드 주석 + 로컬에서 방어.

## 3. M3 — ui_handlers 셰임 제거

- `app/ui.py:37` `from app.ui_handlers import (...)` → `from app.handlers import (...)` (동일 4개 믹스인).
- `app/ui.py:15` 모듈 docstring의 `app.ui_handlers` 언급 → `app.handlers`로 갱신.
- `app/ui_handlers.py` 삭제. 사전 조건: 저장소 전체에서 `ui_handlers` import가 ui.py 한 곳뿐임을 grep으로 확인(2026-06-10 확인 완료 — tests/test_regressions.py:78은 주석, docs는 역사 기록).

## 4. M4 — 루트 정리

### 문서 (git mv → `docs/archive/legacy-root/`)

| 파일 | 비고 |
|---|---|
| `PROJECT_STATUS.md` | deprecated 스텁(본문이 docs로 이관 안내) |
| `IMPROVEMENT_PLAN.md` | 〃 |
| `NEXT_STEPS.md` | 〃 |

- `CLAUDE.md`의 "PDCA Document Structure"(legacy 존재 언급)와 "References > Internal Documents" 절을 이동 후 상태로 갱신.
- docs 내부의 과거 상대링크(`../../../PROJECT_STATUS.md` 등)는 역사 문서라 미수정(아카이브 원칙).

### 스크립트 (git mv → `scripts/`)

| 파일 | 경로 보정 |
|---|---|
| `quick_test.py` | `sys.path` 부트스트랩 **추가**(현재 `from app...` 직수입이라 이동 시 깨짐) |
| `verify_precision_ui.py` | `sys.path.append(os.getcwd())` → 파일 위치 기준 부트스트랩으로 교체 |
| `verify_style_inheritance.py` | 〃 |
| `check_pymupdf_api.py` | 불필요(app 미참조) |
| `generate_sample_pdf.py` | 불필요(app 미참조) |

부트스트랩 표준형(파일 위치 기준 — cwd 무관):

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
```

## 5. 검증 절차

1. requirements 핀 후: `pip install -r requirements.txt --dry-run`으로 해석 가능성 확인(다운그레이드/충돌 없음 — 로컬 동일 버전).
2. ci.yml: PyYAML로 파스 검증.
3. 셰임 제거 후: 전체 테스트 221개 (Python 3.13).
4. 이동 스크립트: `python scripts/check_pymupdf_api.py` 등 대표 실행 확인.
