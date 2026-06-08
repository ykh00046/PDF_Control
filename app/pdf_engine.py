"""
PDF engine helpers.

This module centralizes the PyMuPDF-specific save and preview-render paths so
UI/model layers do not each reimplement document mutation logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import fitz

from app.logger import get_logger
from app.operations_service import ApplyMode, ApplyResult, OperationApplicator

RENDER_DPI = 150


def open_document(file_path: str) -> fitz.Document:
    """Open a PDF document through the engine boundary."""
    return fitz.open(file_path)


def group_operations_by_page(operations: Sequence) -> Dict[int, List]:
    """Group operation objects by page index."""
    grouped: Dict[int, List] = {}
    for operation in operations:
        grouped.setdefault(operation.page_index, []).append(operation)
    return grouped


def apply_page_operations(
    page: fitz.Page,
    operations: Sequence,
    mode: ApplyMode,
    logger=None,
):
    """Apply a list of operations to a single page."""
    if not operations:
        return None

    applicator = OperationApplicator(logger=logger or get_logger())
    return applicator.apply_operations(page, list(operations), mode=mode)


def apply_document_operations(
    document: fitz.Document,
    operations: Sequence,
    mode: ApplyMode,
    logger=None,
) -> None:
    """Apply grouped operations to every affected page in the document."""
    grouped = group_operations_by_page(operations)
    if not grouped:
        return

    logger = logger or get_logger()
    for page_index in range(document.page_count):
        page_operations = grouped.get(page_index)
        if not page_operations:
            continue
        apply_page_operations(document[page_index], page_operations, mode=mode, logger=logger)


def save_document_copy(
    source_path: str,
    output_path: str,
    operations: Sequence,
    logger=None,
    encryption=None,
) -> None:
    """Save a copy of the source document with operations applied.

    When ``encryption`` is an active :class:`~app.encryption.EncryptionSettings`,
    its save kwargs (method, passwords, permissions) are merged into the save
    call; otherwise the document is saved unencrypted.
    """
    logger = logger or get_logger()
    document = None
    try:
        document = open_document(source_path)
        apply_document_operations(document, operations, mode=ApplyMode.SAVE, logger=logger)
        save_kwargs = {"garbage": 3, "deflate": True}
        if encryption is not None:
            save_kwargs.update(encryption.save_kwargs())
        document.save(output_path, **save_kwargs)
    finally:
        if document is not None:
            document.close()


def render_page_preview(
    file_path: str,
    page_index: int,
    operations: Sequence,
    zoom_level: float,
    output_path: str | Path,
    logger=None,
) -> ApplyResult | None:
    """Render a single page preview with operations applied.

    Returns the ApplyResult from operation application so callers can surface
    structured warnings (e.g. text-fit issues) to the UI.
    """
    logger = logger or get_logger()
    source_doc = None
    preview_doc = None
    try:
        source_doc = open_document(file_path)
        preview_doc = fitz.open()
        preview_doc.insert_pdf(source_doc, from_page=page_index, to_page=page_index)

        page = preview_doc[0]
        result = apply_page_operations(page, operations, mode=ApplyMode.PREVIEW, logger=logger)
        page = preview_doc[0]

        scale = zoom_level * RENDER_DPI / 72
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
        pix.save(str(output_path))
        return result
    finally:
        if preview_doc is not None:
            preview_doc.close()
        if source_doc is not None:
            source_doc.close()
