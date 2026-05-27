"""Operation application service (split package).

Re-exports the public API so existing call sites continue to use:

    from app.operations import OperationApplicator, ApplyMode, ApplyResult, ...

Sub-modules:

* :mod:`app.operations.types`      — :class:`ApplyMode`, :class:`TextMetadata`
* :mod:`app.operations.warnings`   — :class:`OpWarning`, :class:`WarningReport`,
                                     :class:`ApplyResult`
* :mod:`app.operations.applicator` — :class:`OperationApplicator`
"""
from app.operations.applicator import OperationApplicator
from app.operations.types import ApplyMode, TextMetadata
from app.operations.warnings import (
    ApplyResult,
    OpWarning,
    WarningReport,
)

__all__ = [
    "ApplyMode",
    "ApplyResult",
    "OpWarning",
    "OperationApplicator",
    "TextMetadata",
    "WarningReport",
]
