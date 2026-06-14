"""
PDF engine helpers.

This module centralizes the PyMuPDF-specific save and preview-render paths so
UI/model layers do not each reimplement document mutation logic.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Sequence

import fitz

from app.encryption import EncryptionSettings, IncorrectPassword, PasswordRequired
from app.logger import get_logger
from app.operations import ApplyMode, ApplyResult, OperationApplicator
from app.operations.base import Operation

RENDER_DPI = 150


def open_document(file_path: str, password: str | None = None) -> fitz.Document:
    """Open a PDF document through the engine boundary.

    For an encrypted document, ``password`` is used to authenticate. Raises
    :class:`~app.encryption.PasswordRequired` when a password is needed but
    none was given, and :class:`~app.encryption.IncorrectPassword` when the
    supplied password does not unlock the file. A plain document ignores
    ``password`` and opens normally (backward compatible).
    """
    doc = fitz.open(file_path)
    if doc.needs_pass:
        if password is None:
            doc.close()
            raise PasswordRequired(file_path)
        # authenticate() returns 0 on failure, a positive bitfield on success.
        if not doc.authenticate(password):
            doc.close()
            raise IncorrectPassword(file_path)
    return doc


def group_operations_by_page(operations: Sequence[Operation]) -> Dict[int, List[Operation]]:
    """Group operation objects by page index."""
    grouped: Dict[int, List[Operation]] = {}
    for operation in operations:
        grouped.setdefault(operation.page_index, []).append(operation)
    return grouped


def apply_page_operations(
    page: fitz.Page,
    operations: Sequence[Operation],
    mode: ApplyMode,
    logger: logging.Logger | None = None,
) -> ApplyResult | None:
    """Apply a list of operations to a single page."""
    if not operations:
        return None

    applicator = OperationApplicator(logger=logger or get_logger())
    return applicator.apply_operations(page, list(operations), mode=mode)


def apply_document_operations(
    document: fitz.Document,
    operations: Sequence[Operation],
    mode: ApplyMode,
    logger: logging.Logger | None = None,
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
    operations: Sequence[Operation],
    logger: logging.Logger | None = None,
    encryption: EncryptionSettings | None = None,
    password: str | None = None,
    source_bytes: bytes | None = None,
) -> None:
    """Save a copy of the source document with operations applied.

    Source selection:

    * ``source_bytes`` (preferred) -- an in-memory snapshot of the CURRENT
      document, with page-management changes (delete/rotate/move/duplicate/
      merge/reorder) already baked in and the content in plaintext. Opened
      directly, so ``password`` is irrelevant here. The session passes this
      so those changes are actually written (without it they were silently
      lost -- save-integrity, 2026-06-14).
    * ``source_path`` (legacy / direct callers) -- re-opens the ORIGINAL file
      and applies operations on top; ``password`` unlocks an encrypted source.

    ``encryption`` controls the OUTPUT protection independently of the source:
    an active :class:`~app.encryption.EncryptionSettings` merges its save
    kwargs (method, passwords, permissions); otherwise the output is plain.
    A protected source can be saved as a plain copy (decrypt) and vice versa.
    """
    logger = logger or get_logger()
    document = None
    try:
        if source_bytes is not None:
            document = fitz.open("pdf", source_bytes)
        else:
            document = open_document(source_path, password=password)
        apply_document_operations(document, operations, mode=ApplyMode.SAVE, logger=logger)
        save_kwargs: Dict[str, Any] = {"garbage": 3, "deflate": True}
        if encryption is not None:
            save_kwargs.update(encryption.save_kwargs())
        document.save(output_path, **save_kwargs)
    finally:
        if document is not None:
            document.close()


def render_page_preview(
    file_path: str,
    page_index: int,
    operations: Sequence[Operation],
    zoom_level: float,
    output_path: str | Path,
    logger: logging.Logger | None = None,
    password: str | None = None,
) -> ApplyResult | None:
    """Render a single page preview with operations applied.

    ``password`` unlocks an encrypted source. Returns the ApplyResult from
    operation application so callers can surface structured warnings (e.g.
    text-fit issues) to the UI.
    """
    logger = logger or get_logger()
    source_doc = None
    preview_doc = None
    try:
        source_doc = open_document(file_path, password=password)
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
