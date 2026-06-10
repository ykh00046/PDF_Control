"""Document session: open/save, undo/redo history, and page management.

Split out of the former monolithic ``app/model.py`` (model-restructure).
"""
import os
from typing import Any, Dict, List, Optional

import fitz
from PySide6.QtCore import QObject, Signal

from app.document_model import PageModel
from app.logger import get_logger, log_file_operation, log_operation
from app.operations.base import Operation
from app.operations.remove_section import RemoveSectionAsImage
from app.operations_service import ApplyMode
from app.pdf_engine import apply_page_operations, open_document, save_document_copy
from app.text_export import build_text, export_text_to_file, resolve_indices


class DocumentSession(QObject):
    history_changed = Signal()
    warnings_changed = Signal()

    def __init__(self, file_path: str, password: Optional[str] = None):
        super().__init__()
        logger = get_logger()
        try:
            self.doc: fitz.Document = open_document(file_path, password=password)
            self.file_path = file_path
            # Password used to unlock the source; threaded to every path that
            # re-opens the source by file path (save, preview). Also drives the
            # "Remove Protection" action and the encrypted-state indicator.
            self._password: Optional[str] = password
            self.is_encrypted: bool = password is not None
            self.pages: List[PageModel] = [PageModel(i) for i in range(self.doc.page_count)]
            self.history: List[Operation] = []
            self.redo_stack: List[Operation] = []
            self.modified = False
            # Cache of most-recent preview warnings keyed by page_index.
            # Values are lists of dicts shaped like OpWarning (see operations_service).
            self.last_preview_warnings: Dict[int, List[Dict[str, Any]]] = {}
            log_file_operation("open", file_path, success=True)
            logger.info(f"Document loaded: {self.doc.page_count} pages")
        except Exception as e:
            log_file_operation("open", file_path, success=False, error_msg=str(e))
            raise

    def render_password(self) -> Optional[str]:
        """Password for re-opening the encrypted source (e.g. render worker).

        Returns the plaintext password, so it must never be written to disk;
        pass it over an in-memory channel (stdin pipe). None when the
        document is not encrypted.
        """
        return self._password if self.is_encrypted else None

    def _bind_document(self, doc: fitz.Document, file_path: str):
        """Swap the active document handle and rebuild per-page caches."""
        old_doc = getattr(self, "doc", None)
        self.doc = doc
        self.file_path = file_path
        self.pages = [PageModel(i) for i in range(self.doc.page_count)]

        if old_doc is not None and old_doc is not doc:
            old_doc.close()

    def add_operation(self, operation: Operation):
        if isinstance(operation, RemoveSectionAsImage):
            already_exists = any(
                isinstance(existing, RemoveSectionAsImage)
                and existing.page_index == operation.page_index
                for existing in self.history
            )
            if already_exists:
                raise ValueError("Only one section removal operation is allowed per page.")

        self.history.append(operation)
        self.redo_stack.clear()
        self.modified = True
        self.history_changed.emit()
        log_operation(operation.__class__.__name__, operation.page_index, len(operation.rects))

    def update_warnings(self, page_index: int, warnings: List[Dict[str, Any]]) -> None:
        """Update the cached preview warnings for a page and notify observers.

        Passing an empty list clears warnings for that page. This is the
        single entry point UI code should use to reflect preview fit issues.
        """
        if warnings:
            self.last_preview_warnings[page_index] = list(warnings)
        else:
            self.last_preview_warnings.pop(page_index, None)
        self.warnings_changed.emit()

    def has_blocking_warnings(self) -> bool:
        """True if any cached warning has severity 'error' (hard overflow)."""
        for warnings in self.last_preview_warnings.values():
            for w in warnings:
                if w.get("severity") == "error":
                    return True
        return False

    def undo(self) -> Optional[Operation]:
        if self.history:
            op = self.history.pop()
            self.redo_stack.append(op)
            self.modified = bool(self.history)
            get_logger().info(f"Undo: {op.__class__.__name__} on page {op.page_index}")
            self.history_changed.emit()
            return op
        return None

    def redo(self) -> Optional[Operation]:
        if self.redo_stack:
            op = self.redo_stack.pop()
            self.history.append(op)
            self.modified = True
            get_logger().info(f"Redo: {op.__class__.__name__} on page {op.page_index}")
            self.history_changed.emit()
            return op
        return None

    def apply_operations_to_page(self, page: fitz.Page, page_index: int):
        """
        Applies all operations for a page using OperationApplicator service.

        This method now delegates to the unified OperationApplicator service,
        which handles all the multi-pass logic for applying operations.
        """
        # Filter operations for this page
        operations_for_page = [op for op in self.history if op.page_index == page_index]

        if not operations_for_page:
            return

        apply_page_operations(page, operations_for_page, mode=ApplyMode.SAVE, logger=get_logger())

    def save_document(self, output_path: str, encryption=None):
        logger = get_logger()
        try:
            logger.info(f"Saving document: {len(self.history)} operations to apply")
            save_document_copy(
                self.file_path, output_path, self.history,
                logger=logger, encryption=encryption, password=self._password,
            )

            # The reload password matches whatever protection the *output* now
            # carries: the new unlock password if we just encrypted, otherwise
            # None (plain save / decrypt). This also keeps is_encrypted accurate.
            if encryption is not None and encryption.is_active():
                new_password: Optional[str] = encryption.unlock_password()
            else:
                new_password = None
            reloaded_doc = open_document(output_path, password=new_password)
            self._bind_document(reloaded_doc, output_path)
            self._password = new_password
            self.is_encrypted = new_password is not None

            self.history.clear()
            self.redo_stack.clear()
            self.modified = False
            self.history_changed.emit()
            log_file_operation("save", output_path, success=True)
        except Exception as e:
            log_file_operation("save", output_path, success=False, error_msg=str(e))
            raise

    # ── Page Management (direct document manipulation) ──────────────

    def rotate_page(self, page_index: int, angle: int):
        """Rotate a page by the given angle (must be multiple of 90)."""
        if angle % 90 != 0:
            raise ValueError(f"Rotation angle must be a multiple of 90, got {angle}")
        page = self.doc[page_index]
        page.set_rotation((page.rotation + angle) % 360)
        self.pages[page_index].clear_cache()
        self.modified = True
        get_logger().info(f"Rotated page {page_index} by {angle}° (now {page.rotation}°)")

    def delete_pages(self, page_indices: List[int]):
        """Delete pages by indices (0-based). Indices are sorted descending to avoid shifting."""
        if len(page_indices) >= self.doc.page_count:
            raise ValueError("Cannot delete all pages")
        # Delete from last to first to keep indices stable
        for idx in sorted(page_indices, reverse=True):
            self.doc.delete_page(idx)
            # Remove operations referencing deleted page, adjust indices
            self.history = [
                op for op in self.history if op.page_index != idx
            ]
            for op in self.history:
                if op.page_index > idx:
                    op.page_index -= 1
            self.redo_stack.clear()
        # Rebuild page models
        self.pages = [PageModel(i) for i in range(self.doc.page_count)]
        self.modified = True
        self.history_changed.emit()
        get_logger().info(f"Deleted {len(page_indices)} page(s)")

    def move_page(self, from_index: int, to_index: int):
        """Move a page from one position to another."""
        if from_index == to_index:
            return
        self.doc.move_page(from_index, to_index)
        # Rebuild page models and adjust operation indices
        self._rebuild_after_reorder()
        get_logger().info(f"Moved page {from_index} → {to_index}")

    def insert_blank_page(self, after_index: int = -1, width: float = 595, height: float = 842):
        """Insert a blank page (default A4) after the specified index. -1 means at the end."""
        if after_index == -1:
            insert_at = self.doc.page_count
        else:
            insert_at = after_index + 1
        self.doc.new_page(insert_at, width=width, height=height)
        # Adjust operation indices
        for op in self.history:
            if op.page_index >= insert_at:
                op.page_index += 1
        self.redo_stack.clear()
        self.pages = [PageModel(i) for i in range(self.doc.page_count)]
        self.modified = True
        self.history_changed.emit()
        get_logger().info(f"Inserted blank page at index {insert_at}")

    def _rebuild_after_reorder(self):
        """Rebuild page models after page reorder. Clears operation history as indices are invalidated."""
        self.history.clear()
        self.redo_stack.clear()
        self.pages = [PageModel(i) for i in range(self.doc.page_count)]
        self.modified = True
        self.history_changed.emit()

    def duplicate_pages(self, page_indices: List[int]) -> int:
        """Duplicate the given pages, inserting each copy directly after the original.

        Indices are 0-based. Duplication is processed in descending order so
        that earlier indices remain valid while later ones expand.
        Pending edit history is invalidated because page indices shift.
        """
        if not page_indices:
            raise ValueError("page_indices must not be empty")
        if len(set(page_indices)) != len(page_indices):
            raise ValueError("page_indices must not contain duplicates")
        page_count = self.doc.page_count
        for idx in page_indices:
            if idx < 0 or idx >= page_count:
                raise IndexError(f"page index out of range: {idx}")
        for idx in sorted(page_indices, reverse=True):
            current_count = self.doc.page_count
            target = idx + 1 if idx + 1 < current_count else -1
            self.doc.copy_page(idx, target)
        self._rebuild_after_reorder()
        get_logger().info(f"Duplicated {len(page_indices)} page(s)")
        return len(page_indices)

    def extract_pages(self, page_indices: List[int], output_path: str) -> None:
        """Save the selected pages to a new PDF file. The source document is unchanged.

        Raises ValueError on empty input or destination conflict, IndexError on
        invalid page indices.
        """
        if not page_indices:
            raise ValueError("page_indices must not be empty")
        page_count = self.doc.page_count
        for idx in page_indices:
            if idx < 0 or idx >= page_count:
                raise IndexError(f"page index out of range: {idx}")
        if not output_path:
            raise ValueError("output_path must not be empty")
        parent_dir = os.path.dirname(os.path.abspath(output_path))
        if parent_dir and not os.path.isdir(parent_dir):
            raise ValueError(f"output directory does not exist: {parent_dir}")
        if self.file_path and os.path.abspath(output_path) == os.path.abspath(self.file_path):
            raise ValueError("Cannot overwrite source document")

        new_doc = fitz.open()
        try:
            for idx in page_indices:
                new_doc.insert_pdf(self.doc, from_page=idx, to_page=idx)
            new_doc.save(output_path)
        finally:
            new_doc.close()
        get_logger().info(
            f"Extracted {len(page_indices)} page(s) to {output_path}"
        )

    def merge_pdfs(self, source_paths: List[str], after_index: int = -1) -> int:
        """Insert every page from each source PDF, in order, after ``after_index``.

        Sources are inserted sequentially so the chosen order is preserved
        (``after_index = -1`` appends at the end). Returns the total number of
        pages inserted across all sources.

        Raises:
            ValueError: empty list, invalid PDF, or out-of-range ``after_index``.
            FileNotFoundError: a source path does not exist.
        """
        if not source_paths:
            raise ValueError("source_paths must not be empty")
        for source_path in source_paths:
            if not source_path or not os.path.isfile(source_path):
                raise FileNotFoundError(f"PDF not found: {source_path}")
        page_count = self.doc.page_count
        if after_index != -1 and (after_index < 0 or after_index >= page_count):
            raise ValueError(f"after_index out of range: {after_index}")

        # Insertion cursor advances past each batch so order is preserved.
        cursor = page_count if after_index == -1 else after_index + 1
        total_added = 0
        for source_path in source_paths:
            try:
                src = fitz.open(source_path)
            except (OSError, IOError) as e:
                raise ValueError(f"Invalid PDF: {e}") from e
            try:
                added = src.page_count
                self.doc.insert_pdf(src, start_at=cursor)
            finally:
                src.close()
            cursor += added
            total_added += added
            get_logger().info(
                f"Merged {added} page(s) from {source_path}"
            )
        self._rebuild_after_reorder()
        get_logger().info(
            f"Merged {total_added} page(s) total from {len(source_paths)} file(s)"
        )
        return total_added

    def merge_pdf(self, source_path: str, after_index: int = -1) -> int:
        """Insert every page from one PDF after ``after_index`` (-1 = end).

        Backward-compatible thin wrapper over :meth:`merge_pdfs`. Returns the
        number of pages inserted.
        """
        return self.merge_pdfs([source_path], after_index)

    def split_document(
        self,
        output_dir: str,
        groups: List[List[int]],
        base_name: Optional[str] = None,
    ) -> List[str]:
        """Write each page-index group to its own PDF file in ``output_dir``.

        Read-only with respect to the current document: the source is not
        modified, so undo/redo history and the ``modified`` flag are untouched
        (same contract as :meth:`extract_pages`).

        File naming: ``f"{base}_{i + 1:03d}.pdf"`` where ``base`` defaults to the
        source file's stem, or ``"split"`` for an unsaved document.

        Args:
            output_dir: Existing directory to write output files into.
            groups: List of 0-based page-index groups (each non-empty).
            base_name: Optional output filename stem.

        Returns:
            The list of written file paths, in group order.

        Raises:
            ValueError: empty ``groups``, an empty group, missing ``output_dir``,
                or a destination colliding with the source document.
            IndexError: a page index is out of range.
        """
        if not groups:
            raise ValueError("groups must not be empty")
        if not output_dir or not os.path.isdir(output_dir):
            raise ValueError(f"output directory does not exist: {output_dir}")

        page_count = self.doc.page_count
        for group in groups:
            if not group:
                raise ValueError("split group must not be empty")
            for idx in group:
                if idx < 0 or idx >= page_count:
                    raise IndexError(f"page index out of range: {idx}")

        if base_name:
            base = base_name
        elif self.file_path:
            base = os.path.splitext(os.path.basename(self.file_path))[0]
        else:
            base = "split"

        source_abs = os.path.abspath(self.file_path) if self.file_path else None
        written: List[str] = []
        for i, group in enumerate(groups):
            output_path = os.path.join(output_dir, f"{base}_{i + 1:03d}.pdf")
            if source_abs and os.path.abspath(output_path) == source_abs:
                raise ValueError("Cannot overwrite source document")
            new_doc = fitz.open()
            try:
                for idx in group:
                    new_doc.insert_pdf(self.doc, from_page=idx, to_page=idx)
                new_doc.save(output_path)
            finally:
                new_doc.close()
            written.append(output_path)

        get_logger().info(
            f"Split document into {len(written)} file(s) in {output_dir}"
        )
        return written

    def extract_text(self, page_indices: Optional[List[int]] = None, fmt: str = "txt") -> str:
        """Return the selected pages' text as a string (whole document when None).

        Read-only delegate to :mod:`app.text_export`. Raises ValueError on an
        unknown format and IndexError on an out-of-range page index.
        """
        indices = resolve_indices(page_indices, self.doc.page_count)
        return build_text(self.doc, indices, fmt)

    def export_text(
        self,
        output_path: str,
        page_indices: Optional[List[int]] = None,
        fmt: str = "txt",
    ) -> int:
        """Export the selected pages' text (all pages when ``page_indices`` is None).

        Read-only: the source document is not modified, so this does not touch
        the undo/redo history or the ``modified`` flag. Returns the number of
        characters written.
        """
        return export_text_to_file(
            self.doc,
            output_path,
            page_indices=page_indices,
            fmt=fmt,
            source_path=self.file_path,
        )

    def close(self):
        if self.doc:
            log_file_operation("close", self.file_path, success=True)
            self.doc.close()
            self.doc = None
