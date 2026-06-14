# Pyproject + Ruff - Completion Report

> **Summary**: 분산 설정(pytest.ini/mypy.ini)을 pyproject.toml로 통합하고 ruff 린터 도입(자동수정 + CI 게이트). R5에서 미뤄둔 정리. 매치율 100%, **294 passed**, ruff 0 위반
>
> **Author**: Claude (bkit)
> **Completed**: 2026-06-15
> **Cycle**: pyproject-ruff
> **Match Rate**: 100%

---

## 1. 무엇을 했나

- **pyproject.toml 신설**: `[tool.ruff]`(line-length 120, select E/F/I/W, scripts E402 ignore), `[tool.pytest.ini_options]`, `[tool.mypy]` + 4개 override 그룹, `[project]` 최소 메타. `pytest.ini`/`mypy.ini` 삭제 → 설정 단일 소스.
- **ruff 도입**: requirements에 `ruff==0.14.4` 핀, CI에 `ruff check` 단계(pytest 전). 위반 261개 → **0**: 자동수정 176(공백/import정렬/미사용) + W293 docstring 23(unsafe-fix, 보이지 않는 공백) + 수동 정리(E712 5·F841 4·E701 3·E501 8).
- line-length는 측정 기반 **120** 선택(88이면 E501 48개, 120이면 9개 → 기존 스타일 수용).

## 2. 위험 관리 — mypy strict 약화 방지

mypy.ini → pyproject 변환의 핵심 위험: **strict가 실수로 꺼져도 0 에러는 유지**되어 test_mypy가 약화를 못 잡는다. 두 단계로 차단:
1. **strict 적용 스모크**: 변환 후 applicator에 어노테이션 없는 함수를 임시 삽입 → `mypy -p app.operations`가 `no-untyped-def`로 잡는지 확인 → 제거. strict가 실제 작동함을 실증.
2. **gap-detector 1:1 대조**: ini의 4개 strict 그룹(operations.*+2완화 / shim ignore / leaf8+model plain / legacy3+warn_return_any) 전부 override에 보존, 누락·다운그레이드 0 확인.

TOML은 UTF-8 표준(mypy가 tomllib로 읽음)이라 r4의 mypy.ini cp949 인코딩 함정도 구조적으로 해소됐다.

## 3. ruff 수동수정의 안전성

가장 주의한 F841(`batch_replace_dialog`의 `page_model`/`words`/`start_pos`/`end_pos` 제거): 이들은 match dict 계약(5키)과 무관하고 소비자(`process_batch_replacements`)와의 계약이 무손상 — 배치 교체 동작 불변. E712는 `==True`→`is True`로 의미 동일, E701/E501은 형식만. 전체 294 테스트가 회귀 그물.

## 4. 검증

- 전체 **294 passed**, `ruff check` 0 위반, test_mypy(strict 게이트) 통과 + strict 스모크 확인.
- mypy.ini/pytest.ini 삭제 반영, CI ruff 단계 추가.

## 5. 다음 (로드맵)

- validate_i18n 강화(tr() 참조 키 검증), ruff format(포매터) 별도 검토, 공격적 ruff 규칙 확대. ui 계층 strict·풀 async-save는 보류.
