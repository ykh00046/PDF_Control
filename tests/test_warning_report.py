"""Unit tests for the new WarningReport aggregation API.

Covers:
* summary() — code-keyed counting
* by_kind() — filter
* has() / has_errors() — predicates
* ApplyResult.report property + legacy property delegation
"""
from app.operations import (
    ApplyResult,
    OpWarning,
    WarningReport,
)


def _w(code: str, severity: str = "warn", op_index: int = 0) -> OpWarning:
    return OpWarning(op_index=op_index, severity=severity, code=code, detail={})


def test_summary_empty_report():
    assert WarningReport().summary() == {}


def test_summary_counts_by_code():
    report = WarningReport([
        _w("text.shrunk"),
        _w("text.shrunk"),
        _w("text.shrunk"),
        _w("text.overflow", severity="error"),
    ])
    assert report.summary() == {"text.shrunk": 3, "text.overflow": 1}


def test_by_kind_filters_strictly():
    w1 = _w("text.shrunk", op_index=1)
    w2 = _w("text.overflow", severity="error", op_index=2)
    w3 = _w("text.shrunk", op_index=3)
    report = WarningReport([w1, w2, w3])
    assert report.by_kind("text.shrunk") == [w1, w3]
    assert report.by_kind("text.overflow") == [w2]
    assert report.by_kind("not.a.code") == []


def test_has_predicate():
    report = WarningReport([_w("text.shrunk")])
    assert report.has("text.shrunk") is True
    assert report.has("text.overflow") is False


def test_has_errors_predicate():
    assert WarningReport().has_errors() is False
    assert WarningReport([_w("text.shrunk")]).has_errors() is False
    assert WarningReport([_w("text.overflow", severity="error")]).has_errors() is True


def test_apply_result_report_property_returns_warning_report():
    result = ApplyResult(
        success=True,
        operations_applied=1,
        warnings=[_w("text.shrunk"), _w("text.shrunk")],
    )
    assert isinstance(result.report, WarningReport)
    assert result.report.summary() == {"text.shrunk": 2}


def test_apply_result_legacy_properties_delegate_to_report():
    result = ApplyResult(
        success=True,
        operations_applied=2,
        warnings=[
            _w("text.shrunk"),
            _w("text.shrunk"),
            _w("text.overflow", severity="error"),
        ],
    )
    assert result.text_shrink_count == 2
    assert result.font_size_adjustments == 2
    assert result.has_errors is True
    assert result.text_shrink_count == result.report.summary().get("text.shrunk", 0)


def test_legacy_import_path_still_works():
    """Backward-compat shim re-exports must remain functional."""
    from app.operations_service import (
        ApplyResult as Shim_ApplyResult,
        OpWarning as Shim_OpWarning,
        WarningReport as Shim_WarningReport,
    )
    assert Shim_ApplyResult is ApplyResult
    assert Shim_OpWarning is OpWarning
    assert Shim_WarningReport is WarningReport
