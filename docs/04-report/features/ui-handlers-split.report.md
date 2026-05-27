# Report: ui_handlers.py 4-Mixin 파일 분리

> **Plan**: [`01-plan/features/ui-handlers-split.plan.md`](../../01-plan/features/ui-handlers-split.plan.md)
> **Design**: [`02-design/features/ui-handlers-split.design.md`](../../02-design/features/ui-handlers-split.design.md)
> **Status**: ✅ Complete (Match Rate: **100%**)
> **Author**: Claude (bkit / Opus 4.7)
> **Completed**: 2026-05-27

---

## 1. Summary

`app/ui_handlers.py` 894줄을 4개 Mixin 책임에 맞춰 `app/handlers/` 패키지로 분리.
외부 임포트 경로는 backward-compat shim으로 **100% 호환** 유지.

| 지표 | Before | After | Δ |
|---|---:|---:|---|
| 최대 파일 라인 수 | 894 | 328 | **−63%** |
| 단일 파일 메서드 수 | 35 | ≤ 12 | 분산 |
| 외부 import 변경 | — | 0 | ✅ 무파괴 |
| 회귀 테스트 | 110 pass | **112 pass** | +2 |
| mypy 게이트 | OK | OK | ✅ |

> 회귀 +2는 stale `pytest_tmp` 정리 후 페이지매니저 일부 테스트가 처음으로 풀로 돌아간 결과.

## 2. Deliverables

```
app/
├── ui_handlers.py             21 lines  (backward-compat shim)
└── handlers/                  ← NEW
    ├── __init__.py            24 lines  (re-export)
    ├── file_handlers.py      157 lines  (FileHandlerMixin     · 5 methods)
    ├── edit_handlers.py      227 lines  (EditHandlerMixin     · 8 methods)
    ├── dialog_handlers.py    328 lines  (DialogHandlerMixin   · 10 methods)
    └── state_handlers.py     214 lines  (StateUpdateMixin     · 12 methods)
```

각 모듈은 자기 사용 심볼만 import → unused-import 잡음 0.

## 3. PDCA Execution Trace

| Phase | 결과 |
|---|---|
| **Plan**     | `01-plan/features/ui-handlers-split.plan.md` 작성 — Done When 6개 항목 정의 |
| **Design**   | `02-design/features/ui-handlers-split.design.md` — 모듈별 책임/import 매트릭스/MRO 보존 전략 |
| **Do**       | 5개 신규 파일 작성 + `ui_handlers.py`를 21줄 shim으로 축소 |
| **Analyze**  | Mixin × 4 / 메서드 35개 / 객체 identity / MainWindow MRO 모두 검증 — **Gap 0** |
| **Iterate**  | `tests/test_regressions.py` AST 경로를 신규 모듈로 갱신 (1 line) |
| **QA**       | pytest 112/112 ✅, mypy ✅ |
| **Report**   | 본 문서 |

## 4. Verification Evidence

### 4.1 메서드 수 보존 (TOTAL = 35)
```
FileHandlerMixin   : 5  methods  (app.handlers.file_handlers)
EditHandlerMixin   : 8  methods  (app.handlers.edit_handlers)
DialogHandlerMixin : 10 methods  (app.handlers.dialog_handlers)
StateUpdateMixin   : 12 methods  (app.handlers.state_handlers)
```

### 4.2 MainWindow MRO (변경 없음)
```
MainWindow → QMainWindow → QWidget → QObject → QPaintDevice → Object
           → FileHandlerMixin → EditHandlerMixin → DialogHandlerMixin → StateUpdateMixin → object
```

### 4.3 Backward-compat
```python
# 세 경로 모두 동일 객체
from app.ui_handlers import FileHandlerMixin as A
from app.handlers     import FileHandlerMixin as B
from app.handlers.file_handlers import FileHandlerMixin as C
assert A is B is C    # ✅
```

### 4.4 Test outcomes
- `pytest tests/` (excluding pyinstaller bundling) → **112 passed**
- `mypy app/operations_service.py` → **Success: no issues found**

## 5. Risks & Mitigation Outcome

| Plan 등록 리스크 | 실제 발생? | 처리 |
|---|---|---|
| 메서드 누락 | ❌ | Phase 4에서 `__dict__` diff로 0 confirmed |
| import 누락 | ❌ | per-file import 분리 + 분리 직후 smoke import |
| pytest 회귀 | ⚠️ 1건 | AST 경로 의존 회귀 1개 — Iterate에서 1라인 수정으로 해결 |
| 순환 import | ❌ | `TYPE_CHECKING` 가드 보존 |

## 6. Decisions Made (no user input required)

1. **패키지 vs 평탄 4파일** → 패키지 `app/handlers/` — 4 파일이 단일 의미 그룹
2. **`ui_handlers.py` 처리** → 즉시 삭제 ❌ / shim 유지 ✅ — 외부 안정성 우선, 다음 PDCA에서 삭제 검토
3. **import 분배** → 각 모듈에 실제 사용 심볼만 — lint 잡음 방지
4. **`_extract_text_metadata` lazy import 보존** — 원본 의도(런타임 분리) 유지
5. **`page_management::test_rotate_180` ERROR** → 코드 회귀 아님 (stale `logs/pytest_tmp` 디렉토리 잠금) — 정리 후 정상 통과 확인

## 7. Follow-ups (Suggested Next PDCA)

1. **`ui_handlers.py` shim 제거** — 1주 grace 후 호출처 grep 0건 확인 시 삭제
2. **Mixin별 단위 테스트 작성** — `tests/handlers/test_file_handlers.py` 등 — `test_ui.py` 67줄의 비대칭 해소
3. **`model.py` (657줄), `operations_service.py` (601줄) 같은 분리 전략 적용** — 본 PDCA의 패키지 분리 패턴 재사용

## 8. Source-of-truth Updates

- `docs/_INDEX.md` — features 항목에 `ui-handlers-split` 추가 권장
- `docs/03-analysis/features/current-state.analysis.md` §2 weakness #3 (Large UI Surface) — 본 분리로 일부 해소, 다음 분석 사이클에서 표현 갱신
- `CLAUDE.md` — Project Structure 트리에 `app/handlers/` 반영 권장 (다음 문서 사이클)

---

### Acceptance Test Re-run
```bash
cd C:/X/Tools/PDF_Control
PYTHONPATH=. py -3.13 -m pytest tests/ --ignore=tests/test_pyinstaller_bundling.py -q
# → 112 passed
py -3.13 -m mypy app/operations_service.py
# → Success: no issues found in 1 source file
```

**PDCA Cycle: 7/7 complete · Match Rate ≥ 90% → Report 단계 진입 가능 조건 충족.**
