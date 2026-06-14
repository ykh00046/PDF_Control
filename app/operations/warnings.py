"""Warning data classes and aggregation API.

``OpWarning`` is the raw, per-operation structured warning emitted during
``apply_operations``. ``WarningReport`` is a thin, stateless façade that
provides count/filter/predicate helpers over a list of warnings — call sites
should prefer ``WarningReport`` over re-implementing the same loops.

``ApplyResult`` carries success state plus the raw warning list, and exposes
both legacy properties (``text_shrink_count`` etc.) and a ``report`` property
returning a fresh :class:`WarningReport`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class OpWarning:
    """Structured warning for a single operation-level fit issue."""

    op_index: int  # index in the per-page operations list
    severity: str  # "info" | "warn" | "error"
    code: str  # e.g. "text.shrunk", "text.overflow"
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WarningReport:
    """Aggregated query/count helpers over a list of :class:`OpWarning`.

    Stateless façade — does not own the warning list, just adapts it. Cheap
    to instantiate (no copies); construct a new one whenever needed.
    """

    warnings: List[OpWarning] = field(default_factory=list)

    def summary(self) -> Dict[str, int]:
        """Return ``{code: count}`` for every distinct warning code present."""
        counts: Dict[str, int] = {}
        for w in self.warnings:
            counts[w.code] = counts.get(w.code, 0) + 1
        return counts

    def by_kind(self, code: str) -> List[OpWarning]:
        """Return all warnings whose ``code`` equals the argument."""
        return [w for w in self.warnings if w.code == code]

    def has(self, code: str) -> bool:
        """``True`` iff at least one warning with the given ``code`` exists."""
        return any(w.code == code for w in self.warnings)

    def has_errors(self) -> bool:
        """``True`` iff at least one warning has ``severity == 'error'``."""
        return any(w.severity == "error" for w in self.warnings)


@dataclass
class ApplyResult:
    """Result of operation application."""

    success: bool
    operations_applied: int
    warnings: List[OpWarning] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def report(self) -> WarningReport:
        """Adapter exposing :class:`WarningReport` helpers over ``warnings``."""
        return WarningReport(self.warnings)

    @property
    def font_size_adjustments(self) -> int:
        return self.report.summary().get("text.shrunk", 0)

    @property
    def text_shrink_count(self) -> int:
        return self.report.summary().get("text.shrunk", 0)

    @property
    def has_errors(self) -> bool:
        return self.report.has_errors()
