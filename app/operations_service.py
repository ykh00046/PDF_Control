"""Backward-compat shim. Public API now lives in :mod:`app.operations`.

Existing call sites such as ``from app.operations_service import
OperationApplicator`` continue to work; new code should prefer
:mod:`app.operations`.

This shim will be removed after the consumer-migration PDCA cycle confirms
no external callers rely on the legacy import path.
"""
from app.operations import (  # noqa: F401
    ApplyMode,
    ApplyResult,
    OpWarning,
    OperationApplicator,
    TextMetadata,
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
