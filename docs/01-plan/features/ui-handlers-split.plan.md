# Plan: ui_handlers.py 4-Mixin 파일 분리

> **Status**: 🟢 Approved
> **Author**: Claude (bkit)
> **Created**: 2026-05-27
> **Level**: Starter
> **Owner**: refactor track
> **Prior PDCA**: [`ui-refactor`](../../04-report/features/ui-refactor.report.md) (선행 완료)

---

## 1. Why (배경)

`app/ui_handlers.py`는 ui-refactor 단계에서 `ui.py` 거대화를 해소하기 위해 도입된 단일 파일(894줄)인데,
4개 Mixin이 한 파일에 응집된 결과 **현재는 이 파일 자체가 새로운 거대 모듈**이 되었다.

- 분석 문서 `03-analysis/features/current-state.analysis.md` §2: "Large UI Surface — `ui.py` remains the largest" → 동일 패턴 재발
- CLAUDE.md "Refactoring Triggers": `Function exceeds 50 lines → Split` / 동일 원칙은 파일에도 적용 가능
- 테스트 비대칭: `ui_handlers.py` 894줄 vs `test_ui.py` 67줄. 파일 분리로 **Mixin별 단위 테스트 작성 동선** 확보

## 2. Goal

`ui_handlers.py` 894줄을 4개 Mixin 책임에 맞춰 **app/handlers/ 패키지**로 분리하되,
외부 임포트 경로와 런타임 동작은 **100% 동일**하게 유지한다.

### 성공 기준 (Done When)

1. `app/handlers/` 패키지에 4개 모듈 생성 + `__init__.py`에서 Mixin re-export
2. `app/ui_handlers.py`는 backward-compat shim(<20줄)으로 축소
3. `from app.ui_handlers import ...` 기존 임포트 **변경 없이** 동작
4. `pytest tests/` **전체 통과** (기존 베이스라인 대비 신규 실패 0)
5. `mypy app/operations_service.py` 통과 (mypy 전략은 변경 없음)
6. 각 Mixin 파일 ≤ 350줄, 평균 ≤ 250줄

## 3. Scope

### In Scope
- `app/ui_handlers.py` → `app/handlers/*.py` 4파일 + `__init__.py` 분리
- 공통 import는 각 모듈로 이전 (사용처에만 둠)
- 기존 shim 유지로 `app/ui.py` 변경 없음
- Docstring 헤더만 각 파일에 맞게 갱신

### Out of Scope
- Mixin 내부 로직 변경 (메서드 시그니처/동작 보존)
- 새 테스트 작성 (별도 PDCA에서 진행)
- `model.py`, `operations_service.py` 분리 (별도 PDCA)
- `ui.py`의 다중상속 구조 자체 변경

## 4. Non-Goals (명시적 제외)

- 메서드 이름 변경 / 시그니처 정리
- 신규 기능 추가
- mypy strict 모드 확장

## 5. Risk & Mitigation

| 리스크 | 영향도 | 완화 전략 |
|---|---|---|
| 메서드 누락 → AttributeError | 🔴 High | Phase 4(Analyze)에서 메서드 이름 셋 diff 수행 |
| import 누락 → ImportError | 🟡 Med | 각 파일 분리 직후 `python -c "from app.ui_handlers import ..."` 스모크 |
| pytest 회귀 | 🔴 High | shim으로 backward-compat 보장 + 전체 테스트 실행 |
| 순환 import | 🟢 Low | TYPE_CHECKING 가드 보존, 모든 파일이 `app.ui.MainWindow`를 forward ref만 사용 |

## 6. Dependencies

- 선행: `ui-refactor` PDCA 완료 ✅
- 후속(권장): `handler-unit-tests` PDCA — 각 Mixin별 단위 테스트 작성

## 7. Acceptance Test

```bash
cd C:/X/Tools/PDF_Control
# 1) 기존 import가 그대로 동작
python -c "from app.ui_handlers import FileHandlerMixin, EditHandlerMixin, DialogHandlerMixin, StateUpdateMixin; print('OK')"
# 2) 신규 import 경로도 동작
python -c "from app.handlers import FileHandlerMixin; from app.handlers.edit_handlers import EditHandlerMixin; print('OK')"
# 3) 전체 회귀
python -m pytest tests/ -x --tb=short
```

## 8. 예상 산출물

| 파일 | 라인(추정) | 책임 |
|---|---|---|
| `app/handlers/__init__.py`        | ~15  | Mixin re-export |
| `app/handlers/file_handlers.py`   | ~150 | open/save/close/drag-drop |
| `app/handlers/edit_handlers.py`   | ~215 | undo/redo/delete/replace/font |
| `app/handlers/dialog_handlers.py` | ~310 | batch/crop/remove/page/log/help |
| `app/handlers/state_handlers.py`  | ~200 | controller/viewer signal reactions |
| `app/ui_handlers.py` (shim)       | ~15  | backward-compat |
| **총합** | ~905 | 894 + 모듈 헤더/shim 오버헤드 |

---

**Next**: [`02-design/features/ui-handlers-split.design.md`](../../02-design/features/ui-handlers-split.design.md)
