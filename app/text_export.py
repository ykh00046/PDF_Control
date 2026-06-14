"""Plain-text / Markdown extraction from a PDF document.

Pure, Qt-free helpers used by :class:`app.document_session.DocumentSession`
(``extract_text`` / ``export_text``) and :class:`app.controller.EditorController`.
Keeping the logic free of Qt makes it fully unit-testable and deterministic.

The source document is never modified — extraction is read-only.
"""

from __future__ import annotations

import os
from typing import List, Optional, Sequence

import fitz

from app.logger import get_logger

TXT = "txt"
MD = "md"
SUPPORTED_FORMATS = (TXT, MD)


def resolve_indices(page_indices: Optional[Sequence[int]], page_count: int) -> List[int]:
    """Return sorted, de-duplicated 0-based indices; ``None`` means every page.

    Raises:
        IndexError: When any provided index is outside ``0..page_count-1``.
    """
    if page_indices is None:
        return list(range(page_count))
    for idx in page_indices:
        if idx < 0 or idx >= page_count:
            raise IndexError(f"page index out of range: {idx}")
    return sorted(set(page_indices))


def build_text(doc: fitz.Document, page_indices: Sequence[int], fmt: str) -> str:
    """Serialise the selected pages' text in the requested format.

    - ``txt``: page texts joined by a blank line.
    - ``md`` : each page prefixed with a ``## Page {n}`` header (1-based ``n``).
    """
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"unsupported format: {fmt}")

    blocks: List[str] = []
    for idx in page_indices:
        page_text = doc[idx].get_text("text").strip()
        if fmt == MD:
            header = f"## Page {idx + 1}"
            blocks.append(f"{header}\n\n{page_text}" if page_text else header)
        else:
            blocks.append(page_text)
    return "\n\n".join(blocks)


def extract_text(
    doc: fitz.Document,
    page_indices: Optional[Sequence[int]] = None,
    fmt: str = TXT,
) -> str:
    """Return the selected pages' text (all pages when ``page_indices`` is None).

    Read-only helper with no filesystem side effects.

    Raises:
        ValueError: Unsupported format.
        IndexError: Invalid page index.
    """
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError(f"unsupported format: {fmt}")
    indices = resolve_indices(page_indices, doc.page_count)
    return build_text(doc, indices, fmt)


def export_text_to_file(
    doc: fitz.Document,
    output_path: str,
    *,
    page_indices: Optional[Sequence[int]] = None,
    fmt: str = TXT,
    source_path: Optional[str] = None,
) -> int:
    """Extract text from ``doc`` and write it to ``output_path`` as UTF-8.

    Args:
        doc: Open PyMuPDF document (read-only here).
        output_path: Destination file path.
        page_indices: 0-based indices to export; ``None`` exports every page.
        fmt: ``"txt"`` or ``"md"``.
        source_path: If given, overwriting this exact path is refused.

    Returns:
        The number of characters written.

    Raises:
        ValueError: Unsupported format, empty path, missing destination
            directory, or attempt to overwrite the source document.
        IndexError: Invalid page index.
    """
    if not output_path:
        raise ValueError("output_path must not be empty")

    parent_dir = os.path.dirname(os.path.abspath(output_path))
    if parent_dir and not os.path.isdir(parent_dir):
        raise ValueError(f"output directory does not exist: {parent_dir}")
    if source_path and os.path.abspath(output_path) == os.path.abspath(source_path):
        raise ValueError("Cannot overwrite source document")

    content = extract_text(doc, page_indices, fmt)

    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    get_logger().info(f"Exported text to {output_path} (fmt={fmt}, {len(content)} chars)")
    return len(content)
