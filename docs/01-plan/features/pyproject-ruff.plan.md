# Pyproject + Ruff - Plan

> **Summary**: 분산된 설정(pytest.ini/mypy.ini)을 `pyproject.toml`로 통합하고 ruff 린터를 도입(자동수정 + CI 게이트). R5에서 "lint diff가 커서 별도 사이클"로 미뤄둔 작업
>
> **Author**: Claude (bkit)
> **Created**: 2026-06-14
> **Status**: ✅ Completed (2026-06-15, 매치율 100%, 294 passed, ruff 0)
> **Cycle**: pyproject-ruff

---

## 1. 배경 (Why)

R5 인프라 사이클이 "전 코드베이스 lint diff가 커서 pyproject/ruff는 별도 사이클로 분리"라고 명시. 현재 설정이 분산: `pytest.ini`, `mypy.ini`, ruff 없음.

### 실측 (ruff 위반 규모 — plan 확정 근거)

ruff 0.14.4 측정 (select E/F/I/W, line-length 120):
- **자동수정 176개**: W293(공백 줄 130), I001(import 정렬 40), F401(미사용 import 22 — 일부), F541(빈 f-string 1), W291/W292(trailing/EOF 6).
- **수동 정리**: E712(`==True/False` 5), F841(미사용 변수 4), E701(한 줄 문장 3), E501(긴 줄, **120 기준 9개만** — 88 기준 48 → 120이 적절).
- **per-file ignore**: E402 2개 = `scripts/verify_precision_ui.py`의 의도적 경로 부트스트랩(sys.path 후 import).

mypy 1.19는 `pyproject.toml [tool.mypy]` + `[[tool.mypy.overrides]]`를 지원.

## 2. 목표 (What)

### 필수 (Must)

- **M1**: `pyproject.toml` 생성 — `[tool.ruff]`(line-length 120, `select = ["E","F","I","W"]`, per-file-ignores: scripts E402). `requirements.txt`에 `ruff==0.14.4` 추가.
- **M2**: ruff 위반 0 — `ruff check --fix`로 자동수정 후 수동 정리(E712→`is True`/직접 비교 제거, F841→삭제, E701→분리, E501 9개→줄바꿈 또는 `# noqa: E501`). **자동수정은 동작 불변**(공백/import 정렬/미사용 제거)이나 전체 테스트로 회귀 확인.
- **M3**: `pytest.ini` → `pyproject.toml [tool.pytest.ini_options]` 이전 후 `pytest.ini` 삭제.
- **M4**: `mypy.ini` → `pyproject.toml [tool.mypy]` + `[[tool.mypy.overrides]]` 1:1 이전 후 `mypy.ini` 삭제. **strict 적용 스모크 검증**(아래 §3) — strict가 실수로 꺼지면 0 에러가 유지돼 test_mypy가 못 잡으므로 필수.
- **M5**: CI(`.github/workflows/ci.yml`)에 `ruff check` 단계 추가(pytest 전).
- **M6**: 전체 테스트 통과 + `test_mypy.py`(strict 게이트) 통과 + `ruff check` 0 위반.

### 권장 (Should)

- **S1**: pyproject에 `[project]` 최소 메타(name/version/requires-python) — 도구 발견성. 의존성은 requirements.txt 유지(CI 워크플로 정착).

### 범위 외 (Won't)

- requirements.txt → `[project.dependencies]` 이전 — CI가 `pip install -r requirements.txt` 정착, 이전 시 워크플로 변경 폭 큼. requirements 유지.
- ruff format(포매터) — 린트만. 포매터는 대량 재포맷이라 별도.
- 공격적 규칙(N/D/ANN 등) — 보수적 E/F/I/W만. 확대는 후속.
- mypy strict 모듈 확대 — 이번은 설정 이전만(동작 불변), 게이트 범위 그대로.

## 3. mypy strict 적용 스모크 (M4 핵심 검증)

mypy.ini → pyproject 변환의 위험: strict가 조용히 꺼져도 0 에러는 유지(더 관대)되어 `test_mypy.py`가 약화를 못 잡는다. 따라서 변환 후 1회 검증:

1. `app/operations/applicator.py`에 의도적 strict 위반(예: 어노테이션 없는 함수 `def _smoke(x): return x`) **임시** 삽입.
2. `mypy -p app.operations` 실행 → **에러 발생 확인**(strict의 `disallow_untyped_defs`가 잡음).
3. 위반 제거(되돌림). strict가 살아있음을 확정.

(plan/report에 절차 기록. 이전 정확성은 gap-detector가 ini 블록 ↔ TOML override 1:1 대조.)

## 4. 성공 기준 (Acceptance)

- [ ] 전체 테스트 294+ 통과.
- [ ] `ruff check app tests scripts main.py` 0 위반.
- [ ] `test_mypy.py`(strict 게이트) 통과 + strict 적용 스모크 확인.
- [ ] `pyproject.toml`이 ruff/pytest/mypy 설정 보유, `pytest.ini`/`mypy.ini` 삭제.
- [ ] CI에 ruff 단계, green.
- [ ] mypy.ini의 strict 블록(operations.*, leaf 8, model, legacy-core 3, operations_service ignore)이 pyproject override에 1:1 보존.
- [ ] Gap 분석 매치율 ≥ 90%.

## 5. 영향 범위 (Scope)

| 파일 | 변경 |
|---|---|
| `pyproject.toml` | 신규 — ruff/pytest/mypy + [project] 메타 |
| `pytest.ini`, `mypy.ini` | 삭제(이전 후) |
| `requirements.txt` | `ruff==0.14.4` 추가 |
| `.github/workflows/ci.yml` | ruff check 단계 |
| `app/**`, `tests/**`, `scripts/**` | ruff 위반 정리(자동+수동) |
| `tests/test_mypy.py` | 경로/동작 확인(config 자동발견 — 변경 없을 가능성) |

## 6. 리스크 & 완화

| 리스크 | 완화 |
|---|---|
| **mypy strict 조용한 약화**(게이트 미검출) | §3 strict 적용 스모크 + gap-detector 1:1 대조 |
| pyproject.toml 인코딩(mypy.ini cp949 함정 재발?) | TOML은 UTF-8 표준, mypy가 tomllib(UTF-8)로 읽음 → ini의 cp949 함정 오히려 해소. ASCII 유지로 이중 안전 |
| ruff 자동수정이 동작 변경 | 자동수정은 공백/import정렬/미사용제거(의미 불변). 전체 테스트가 회귀 그물 |
| mypy.ini와 pyproject 둘 다 존재 시 충돌 | mypy.ini 삭제로 단일 소스 |
| test_mypy가 mypy.ini 직접 참조 | test_mypy는 `mypy -p`/`mypy <files>` 실행(config 자동발견) → pyproject 자동 사용. 참조 없음(확인) |
| ruff 버전 드리프트(CI vs 로컬) | `ruff==0.14.4` 핀(requirements) |
