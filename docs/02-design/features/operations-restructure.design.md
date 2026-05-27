# Design: operations-restructure

> **Plan ref**: [`01-plan/features/operations-restructure.plan.md`](../../01-plan/features/operations-restructure.plan.md)
> **Status**: 🟢 Approved
> **Created**: 2026-05-27
> **Cycle**: 1 of 2 (consumer migration deferred)

---

## 1. Target Layout

### Before
```
app/
└── operations_service.py    601 lines
```

### After
```
app/
├── operations_service.py     ~25 lines  (backward-compat shim)
└── operations/               ← NEW
    ├── __init__.py           ~30 lines  (re-export public API)
    ├── types.py              ~30 lines  (ApplyMode, TextMetadata)
    ├── warnings.py           ~95 lines  (OpWarning, WarningReport, ApplyResult)
    └── applicator.py        ~470 lines  (OperationApplicator + Pass 메서드들)
```

## 2. Public API (변경 없음)

| Symbol | 신규 모듈 | shim re-export |
|---|---|---|
| `OperationApplicator` | `app.operations.applicator` | ✅ |
| `ApplyMode`           | `app.operations.types`      | ✅ |
| `ApplyResult`         | `app.operations.warnings`   | ✅ |
| `OpWarning`           | `app.operations.warnings`   | ✅ |
| `TextMetadata`        | `app.operations.types`      | ✅ |
| `WarningReport` (NEW) | `app.operations.warnings`   | ✅ |

## 3. Plan Open Questions — 결정

| Q | 결정 | 근거 |
|---|---|---|
| **Q1 분할 입도** | **applicator.py 단일** (passes.py 추가 분리 ❌) | 현재 Pass 메서드들이 `self.logger`, `self.current_warnings`, `self._current_op_index` 등 인스턴스 상태에 결합 → 함수형 분리는 추가 리팩토링 필요(non-goal). 470줄로 임계치 내. |
| **Q2 ApplyResult vs WarningReport** | **WarningReport 별도 dataclass**, `ApplyResult.report` property로 제공 | embed/상속 모두 외부 API 변경. property 추가는 backward-compat 안전. |
| **Q3 Shim 유지 기간** | **다음 release까지** (최소 1 사이클) | ui_handlers 분리에서 검증된 패턴 |
| **Q4 `current_warnings` 인스턴스 상태 정리** | **이번 사이클 처리 ❌** | Plan Non-Goals "외부 동작 100% 동일". stateless 재설계는 별도 PDCA |

## 4. WarningReport 신규 API

```python
@dataclass
class WarningReport:
    """Aggregated query/count helpers over a list of OpWarning entries.

    Stateless façade — does not own the warning list, just adapts it.
    """
    warnings: List[OpWarning] = field(default_factory=list)

    def summary(self) -> Dict[str, int]:
        """Return ``{code: count}`` for every distinct warning code present."""
        counts: Dict[str, int] = {}
        for w in self.warnings:
            counts[w.code] = counts.get(w.code, 0) + 1
        return counts

    def by_kind(self, code: str) -> List[OpWarning]:
        return [w for w in self.warnings if w.code == code]

    def has(self, code: str) -> bool:
        return any(w.code == code for w in self.warnings)

    def has_errors(self) -> bool:
        return any(w.severity == "error" for w in self.warnings)
```

### ApplyResult 변경 (additive only)

```python
@dataclass
class ApplyResult:
    success: bool
    operations_applied: int
    warnings: List[OpWarning] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def report(self) -> WarningReport:                    # NEW
        return WarningReport(self.warnings)

    @property
    def font_size_adjustments(self) -> int:               # 위임으로 전환
        return self.report.summary().get("text.shrunk", 0)

    @property
    def text_shrink_count(self) -> int:                   # 위임으로 전환
        return self.report.summary().get("text.shrunk", 0)

    @property
    def has_errors(self) -> bool:                         # 위임으로 전환
        return self.report.has_errors()
```

소비 측에서 `result.warnings`, `result.font_size_adjustments`, `result.text_shrink_count`, `result.has_errors`는 **모두 동일하게 동작**.

## 5. mypy Strict Scope 확장

`mypy.ini`:
```ini
# 변경 전
[mypy-app.operations_service]
strict = True

# 변경 후
[mypy-app.operations.*]
strict = True
disallow_any_decorated = False
warn_return_any = False

# Shim — re-export only, strict 면제
[mypy-app.operations_service]
ignore_errors = True
```

`tests/test_mypy.py`도 대상 경로를 `app/operations/` 디렉토리로 갱신.

## 6. Import 경로 — 변경 매트릭스

| 파일 | 변경 |
|---|---|
| `app/model.py:8` | 그대로 — shim 유효 |
| `app/pdf_engine.py:16` | 그대로 — shim 유효 |
| `tests/test_long_text_warning.py:15` | 그대로 — shim 유효 |
| `tests/test_preview_save_equivalence.py:15` | 그대로 — shim 유효 |
| `tests/test_regressions.py:19` | 그대로 — shim 유효 |
| `tests/test_mypy.py:20` | `app/operations_service.py` → `app/operations/` (디렉토리 단위 검사) |
| `quick_test.py:10` | 그대로 — shim 유효 |

→ **호출지 0 변경**. shim과 mypy.ini만 갱신.

## 7. Migration Invariants

1. 함수/메서드 시그니처 보존 — 한 줄도 수정하지 않음
2. `OperationApplicator` 내부 인스턴스 상태(`current_warnings`, `_current_op_index`) 보존
3. `# type: ignore`, `# noqa` 주석 보존
4. `ApplyResult.warnings` 필드는 그대로 `List[OpWarning]` — `WarningReport`로 교체하지 않음
5. lazy import (`from app.model import ...`) 보존 — 순환 방지

## 8. Test Plan

### 회귀 (필수)
```bash
py -3.13 -m pytest tests/ -q             # 119 → 119+
py -3.13 -m mypy app/operations/         # 새 scope 통과
```

### 신규 (선택, 본 사이클에 한 파일 추가)
`tests/test_warning_report.py`:
- `WarningReport().summary() == {}`
- `WarningReport([w1, w2_same_code]).summary() == {"text.shrunk": 2}`
- `WarningReport([...]).by_kind("text.shrunk")` 정확 필터
- `WarningReport([err_w]).has_errors() is True`
- `ApplyResult.text_shrink_count == ApplyResult.report.summary()["text.shrunk"]`

## 9. Decision Log

| 결정 | 선택 | 대안 | 사유 |
|---|---|---|---|
| 패키지 vs 평탄 | 패키지 `app/operations/` | `app/applicator.py` + `app/op_warnings.py` 등 | 같은 의미 그룹 / ui_handlers 분리와 일관성 |
| applicator.py 분할 | 단일 파일 | Pass별 함수 분리 | non-goal 충돌(상태 결합) |
| WarningReport 위치 | `warnings.py` | `types.py` | warning 도메인 응집도 |
| shim 위치 | `operations_service.py` 유지 | 즉시 삭제 | 외부 호출자 보호 |
| 호출자 마이그레이션 | **차기 사이클** | 한 번에 처리 | 회귀 위험 분리 |

---

**Next**: implementation in Phase 3 (Do).
