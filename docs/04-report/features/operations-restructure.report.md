# Report: operations-restructure

> **Plan**: [`01-plan/features/operations-restructure.plan.md`](../../01-plan/features/operations-restructure.plan.md)
> **Design**: [`02-design/features/operations-restructure.design.md`](../../02-design/features/operations-restructure.design.md)
> **Status**: ✅ Complete (Cycle 1 of 2 — Match Rate **100%** of cycle scope)
> **Author**: Claude (bkit / Opus 4.7)
> **Completed**: 2026-05-27

---

## 1. Summary

`app/operations_service.py` 601줄을 `app/operations/` 패키지 4개 모듈로 분리하고,
`WarningReport` 집계 API를 신규로 추가. 외부 호출자는 backward-compat shim으로 **100% 무변경**.

| 지표 | Before | After | Δ |
|---|---:|---:|---|
| 최대 파일 라인 수 | 601 | 556 | −8% (applicator만 잔존) |
| 공개 API 모듈 | 1 | 3 (types/warnings/applicator) | 응집도 ↑ |
| mypy strict scope | 1 파일 | **4 파일 (패키지 전체)** | ✅ 확장 |
| 회귀 테스트 | 119 pass | **127 pass** | +8 (신규 WarningReport) |
| 호출자 import 변경 | — | 0 | ✅ 무파괴 |

> applicator.py가 여전히 556줄인 것은 의도된 결정 — Pass 메서드들이 `self.current_warnings` 인스턴스 상태에 결합되어 있어, 함수형 분리는 Non-Goal "외부 동작 100% 동일"과 충돌. stateless 재설계는 차기 PDCA로 분리.

## 2. Deliverables

```
app/
├── operations_service.py     26 lines  (backward-compat shim · 6 symbols re-exported)
└── operations/               ← NEW
    ├── __init__.py           29 lines  (public API surface)
    ├── types.py              25 lines  (ApplyMode, TextMetadata)
    ├── warnings.py           82 lines  (OpWarning, WarningReport★, ApplyResult)
    └── applicator.py        556 lines  (OperationApplicator + 9 Pass methods)

tests/
└── test_warning_report.py    91 lines  ← NEW (8 unit tests)
```

★ `WarningReport`는 본 사이클 신규 API.

## 3. PDCA Execution Trace

| Phase | 결과 |
|---|---|
| **Plan**     | 기존 4월 21일 Plan을 2-cycle scope로 분할 (본 사이클 = 패키지 분리 + WarningReport / 차기 = 호출자 마이그레이션) |
| **Design**   | 신규 작성 — Open Questions 4개에 결정 기록, mypy.ini 변경 매트릭스 |
| **Do**       | 4파일 신규 + shim 축소 + mypy.ini 갱신 + `test_mypy.py` 경로 갱신 + WarningReport 단위 테스트 8개 |
| **Analyze**  | shim identity (`OperationApplicator is app.operations.OperationApplicator`) 확인, 모듈 경로 `app.operations.applicator` 확정 |
| **Iterate**  | **이슈 0건** — 한 번에 통과 |
| **QA**       | pytest 127/127, mypy --strict on `app.operations` (4 files) ✅ |
| **Report**   | 본 문서 |

## 4. WarningReport — 신규 API

추가된 집계 API (모두 stateless façade):

```python
report = WarningReport(warnings_list)
report.summary()           # → {"text.shrunk": 3, "text.overflow": 1}
report.by_kind("text.shrunk")    # → [OpWarning, ...]
report.has("text.overflow")      # → bool
report.has_errors()              # → bool (any severity=='error')
```

`ApplyResult`는 `report` property를 새로 노출하면서 **기존 property는 위임으로 전환**:

```python
@property
def text_shrink_count(self) -> int:
    return self.report.summary().get("text.shrunk", 0)
```

→ 소비 측 `result.text_shrink_count`, `result.font_size_adjustments`, `result.has_errors`는 **동일하게 동작**.

## 5. Verification Evidence

### 5.1 Backward-compat shim
```
$ py -3.13 -c "from app.operations_service import OperationApplicator; \
               print(OperationApplicator.__module__)"
app.operations.applicator
```
Shim과 패키지에서 import한 객체는 동일 identity (`is` 비교 통과).

### 5.2 pytest
```
127 passed, 1 warning in 13.86s
```
- 회귀 (119) ✅
- 신규 WarningReport 단위 8건 ✅

### 5.3 mypy --strict (scope 확장)
```
$ py -3.13 -m mypy -p app.operations
Success: no issues found in 4 source files
```

### 5.4 mypy.ini diff (개념)
```
- [mypy-app.operations_service]
- strict = True
+ [mypy-app.operations.*]
+ strict = True
+ [mypy-app.operations_service]
+ ignore_errors = True
```

## 6. Migration Invariants 점검

| 약속 | 결과 |
|---|---|
| 메서드 시그니처 보존 | ✅ — `OperationApplicator`의 9개 메서드 모두 그대로 |
| `# type: ignore`, `# noqa` 보존 | ✅ |
| `ApplyResult.warnings`는 `List[OpWarning]` 유지 | ✅ — `WarningReport`로 교체하지 않음 |
| lazy import (`from app.model import ...`) 보존 | ✅ — 순환 방지 |
| 인스턴스 상태(`current_warnings`, `_current_op_index`) 보존 | ✅ |
| 외부 호출자 0 변경 | ✅ — model.py / pdf_engine.py / 3개 test 파일 그대로 |

## 7. Plan Acceptance Criteria — 매핑

| Plan §Acceptance Criteria | Cycle | 상태 |
|---|---|---|
| `app/operations/` 패키지 생성, public symbol re-export | 1 | ✅ |
| 하위 모듈 분할 (applicator/passes/warnings/types) | 1 | ✅ (passes 통합, Design Q1 결정) |
| `WarningReport.summary()` | 1 | ✅ |
| `WarningReport.by_kind(code)` | 1 | ✅ |
| `WarningReport.has(code)` | 1 | ✅ |
| `ApplyResult.font_size_adjustments`/`text_shrink_count` 위임 | 1 | ✅ |
| `model.py:395`, `ui.py:162` 등 호출자 → `WarningReport` 전환 | **2** | ⏭ 차기 |
| `mypy.ini` strict scope → `app.operations.*` | 1 | ✅ |
| 회귀 100/100 유지 (신규 unit test 추가 후 최소 103) | 1 | ✅ **127** |
| PyInstaller onedir 빌드 정상 (import 경로) | 2 | ⏭ 빌드 검증 별도 |
| `docs/_INDEX.md` / `CLAUDE.md` 갱신 | 2 | ⏭ |
| `unified-operations.design.md` superseded 표기 | 2 | ⏭ |

→ **Cycle 1 acceptance 8/8 ✅, Cycle 2 acceptance 4건 보류**.

## 8. Decisions Made (Plan Open Questions 답)

| Q | 답 |
|---|---|
| Q1: 분할 입도 | **applicator.py 단일** — 인스턴스 상태 결합으로 함수형 분리 비용 과다 |
| Q2: ApplyResult vs WarningReport | **별도 dataclass, `result.report` property** — 추가만, 기존 API 변경 0 |
| Q3: Shim 유지 기간 | **차기 사이클까지** (operations-consumers 완료 후 제거 검토) |
| Q4: `current_warnings` 인스턴스 상태 정리 | **이번 사이클 ❌** — Non-Goal 준수, 차기 PDCA 후보 |

## 9. Risks & Mitigation Outcome

| Plan §Risk | 실제 발생? | 처리 |
|---|---|---|
| Import 경로 파급 (`__pycache__`, PyInstaller hidden imports) | ❌ | shim 유지로 0건 변경. grep으로 `from app.operations_service` 7건 모두 호환 확인 |
| mypy strict 확장 시 신규 에러 노출 | ❌ | `follow_imports=silent` 유지, 패키지 내부 4 파일 모두 통과 |
| `ApplyResult` property 제거 시 외부 breakage | ❌ | 제거 ❌ → 위임 전환 ✅ |
| 리팩토링 범위 팽창 | ❌ | Non-Goals 엄수, Cycle 2로 분리 |

## 10. Follow-ups (Cycle 2: operations-consumers)

| Task | 우선 |
|---|---|
| `app/model.py:395` 등 호출자가 `result.report.summary()` / `by_kind()` 사용으로 전환 | High |
| `app/handlers/state_handlers.py`의 `last_preview_warnings` 순회를 `WarningReport`로 위임 | Medium |
| `app/operations_service.py` shim 제거 (외부 호출 0 확인 후) | Low |
| `OperationApplicator.current_warnings` 인스턴스 상태 → 함수 반환값으로 stateless 화 | Medium |
| `CLAUDE.md` "Project Structure" 트리에 `app/operations/`, `app/handlers/` 반영 | Low |
| `docs/_INDEX.md` 갱신 (ui-handlers-split, operations-restructure 추가) | Low |
| `docs/02-design/features/unified-operations.design.md` superseded 주석 | Low |

## 11. Source-of-truth Updates Suggested

- `docs/_INDEX.md` — 본 PDCA 4 문서 등재
- `CLAUDE.md` "Project Structure" — `app/operations/`, `app/handlers/` 패키지 트리 반영
- `docs/03-analysis/features/current-state.analysis.md` — "operations_service 601줄" 항목 갱신

---

### Acceptance Test Re-run
```bash
cd C:/X/Tools/PDF_Control
$env:QT_QPA_PLATFORM='offscreen'; py -3.13 -m pytest tests/ -q
# → 127 passed
py -3.13 -m mypy -p app.operations
# → Success: no issues found in 4 source files
```

**PDCA Cycle 1: 7/7 complete · Match Rate 100% · Cycle 2 백로그 등록 완료.**
