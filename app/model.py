"""Backward-compatible facade for the document model (model-restructure).

The former 690-line monolith was decomposed into single-responsibility
modules. This module re-exports every public symbol so existing call sites
and tests can keep importing from ``app.model`` unchanged:

* :mod:`app.document_model`            — :class:`WordBox`, :class:`PageModel`
* :mod:`app.text_metadata`             — :func:`_extract_text_metadata`
* :mod:`app.document_session`          — :class:`DocumentSession`
* :mod:`app.operations.base`           — :class:`Operation`
* :mod:`app.operations.redact`         — :class:`RedactDelete`, :class:`RedactReplace`
* :mod:`app.operations.crop`           — :class:`CropMargins`
* :mod:`app.operations.remove_section` — :class:`RemoveSectionAsImage`
"""
from app.document_model import PageModel, WordBox
from app.document_session import DocumentSession
from app.operations.base import Operation
from app.operations.crop import CropMargins
from app.operations.redact import RedactDelete, RedactReplace
from app.operations.remove_section import RemoveSectionAsImage
from app.operations.watermark import WatermarkText
from app.text_metadata import _extract_text_metadata

__all__ = [
    "WordBox",
    "Operation",
    "RedactDelete",
    "RedactReplace",
    "CropMargins",
    "RemoveSectionAsImage",
    "WatermarkText",
    "PageModel",
    "DocumentSession",
    "_extract_text_metadata",
]
