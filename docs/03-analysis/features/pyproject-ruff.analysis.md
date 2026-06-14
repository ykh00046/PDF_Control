# Pyproject + Ruff - Gap Analysis

> **Summary**: 설계-구현 갭 분석 — 매치율 **100%**, mypy strict 1:1 보존(약화 0), ruff 수동수정 런타임 변경 0, Act 불필요
>
> **Analyzer**: bkit gap-detector
> **Date**: 2026-06-15
> **Design**: [pyproject-ruff.design.md](../../02-design/features/pyproject-ruff.design.md)

---

## 매치율: 100% (M1-M6 + S1 + Acceptance 7/7)

| 항목 | 구현 증거 | 일치 |
|---|---|:--:|
| M1 [tool.ruff]/[tool.pytest]/[tool.mypy] + 4 overrides | `pyproject.toml:8-64` | ✅ |
| M1 requirements ruff==0.14.4 | `requirements.txt:18` | ✅ |
| M4 mypy override 1:1 (전역 + operations.* + shim + leaf8+model + legacy3) | `pyproject.toml:32-64` | ✅ |
| M2 ruff 0 위반 (E712/F841/E701/E501 수동) | grep 0건 | ✅ |
| M3/M4 pytest.ini/mypy.ini 삭제 | git D | ✅ |
| M5 CI ruff check (pytest 전) | `ci.yml:23` | ✅ |
| M6 294 passed + test_mypy + strict 스모크 | 검증됨 | ✅ |
| S1 [project] 메타 | `pyproject.toml:1-4` | ✅ |

## 핵심 검증 (가장 중요)

- **mypy strict 약화 0**: 4개 strict 그룹 + 전역 1:1 보존, 누락/다운그레이드 없음. `app.model`은 plain-strict(warn_return_any 미완화), operations.*/legacy-core는 완화 유지. **strict 적용 스모크**(untyped def 임시 삽입 → mypy 검출 → 제거)로 strict가 실제 작동 확인 — 0 에러가 약화를 가리는 위험 차단.
- **ruff 수동수정 런타임 변경 0**: F841로 제거한 `page_model`/`words`/`start_pos`/`end_pos`는 batch_replace match dict 계약(5키)과 무관, 소비자(`process_batch_replacements`)와 계약 무손상. E712(`==True`→`is True`) 의미 동일, E701/E501은 형식만.

## 검증

- 전체 **294 passed**, ruff 0 위반, test_mypy 통과(pyproject 자동발견), i18n 무관.
- 경미 드리프트(test_mypy 주석 "mypy.ini") → pyproject로 갱신 완료.

## 결론

매치율 100% ≥ 90% → Act 생략, Report 진행.
