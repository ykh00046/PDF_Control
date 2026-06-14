from typing import Any, Callable, List, Optional, Sequence, Tuple

from PySide6.QtCore import QObject, Signal

from app.encryption import EncryptedPDFError
from app.logger import get_logger
from app.model import DocumentSession, Operation, WatermarkImage, WatermarkText


class EditorController(QObject):
    """
    Controller class that manages the DocumentSession and handles business logic.
    Acts as a bridge between the UI (View) and the Data (Model).
    """

    # Signals to notify the UI about state changes
    document_loaded = Signal(str)  # Emits file path
    document_closed = Signal()
    history_changed = Signal()  # Emits when undo/redo stack changes
    operation_applied = Signal()  # Emits when an operation is applied (requires re-render)
    error_occurred = Signal(str)  # Emits error message

    def __init__(self):
        super().__init__()
        self._session: Optional[DocumentSession] = None
        self.logger = get_logger()

    @property
    def session(self) -> Optional[DocumentSession]:
        """Read-only access to the current session. Used by Viewer for rendering."""
        return self._session

    def _run_session_action(
        self,
        action: str,
        func: Callable[[DocumentSession], Any],
        *,
        applied: bool = True,
        default: Any = False,
    ) -> Any:
        """Run a session mutation with unified guard + error reporting.

        ValueError is an expected user-validation rejection (warning log);
        anything else is an internal failure (error log). Both emit
        ``error_occurred`` with the exception text and return ``default``.
        On success, emits ``operation_applied`` when ``applied`` is True and
        returns the session method's result (or True when it returns None).
        """
        if not self._session:
            return default
        try:
            result = func(self._session)
        except ValueError as e:
            self.logger.warning(f"{action} rejected: {e}")
            self.error_occurred.emit(str(e))
            return default
        except Exception as e:
            self.logger.error(f"Failed to {action}: {e}")
            self.error_occurred.emit(str(e))
            return default
        if applied:
            self.operation_applied.emit()
        return True if result is None else result

    def load_document(self, file_path: str, password: Optional[str] = None) -> bool:
        """Loads a new document session.

        ``password`` unlocks an encrypted PDF. Password-related failures
        (:class:`~app.encryption.EncryptedPDFError`) are *re-raised* rather than
        converted to an ``error_occurred`` signal, so the UI layer can drive a
        retry/prompt loop. Other failures emit ``error_occurred`` and return
        ``False`` as before.
        """
        new_session = None
        try:
            self.logger.info(f"Controller loading document: {file_path}")
            new_session = DocumentSession(file_path, password=password)
        except EncryptedPDFError:
            raise
        except Exception as e:
            self.logger.error(f"Failed to load document: {e}")
            self.error_occurred.emit(f"Failed to load document: {e}")
            return False

        old_session = self._session
        self._session = new_session
        self._session.history_changed.connect(self._on_history_changed)

        if old_session is not None:
            try:
                old_session.history_changed.disconnect(self._on_history_changed)
            except (RuntimeError, TypeError):
                pass
            try:
                old_session.close()
            except Exception as e:
                self.logger.error(f"Error closing previous document: {e}")

        self.document_loaded.emit(file_path)
        return True

    def close_document(self):
        """Closes the current document session."""
        if self._session:
            try:
                try:
                    self._session.history_changed.disconnect(self._on_history_changed)
                except (RuntimeError, TypeError):
                    pass
                self._session.close()
            except Exception as e:
                self.logger.error(f"Error closing document: {e}")
            finally:
                self._session = None
                self.document_closed.emit()

    def save_document(self, output_path: str, encryption=None):
        """Saves the modified document to the specified path.

        ``encryption`` is an optional :class:`~app.encryption.EncryptionSettings`
        applied at save time (password protection + permissions). Failures are
        reported AND re-raised so save dialogs can react, which is why this
        does not go through :meth:`_run_session_action`.
        """
        if not self._session:
            return

        try:
            self._session.save_document(output_path, encryption=encryption)
            self.operation_applied.emit()
        except Exception as e:
            self.logger.error(f"Failed to save document: {e}")
            self.error_occurred.emit(f"Failed to save document: {e}")
            raise

    def add_operation(self, operation: Operation) -> bool:
        """Adds an operation to the current session."""
        return bool(self._run_session_action("add operation", lambda s: s.add_operation(operation)))

    def undo(self):
        """Performs undo on the current session."""
        if self._session:
            self._session.undo()
            self.operation_applied.emit()

    def redo(self):
        """Performs redo on the current session."""
        if self._session:
            self._session.redo()
            self.operation_applied.emit()

    # ── Page Management ─────────────────────────────────────────────

    def rotate_page(self, page_index: int, angle: int) -> bool:
        """Rotate a page by the given angle (90, 180, 270)."""
        return bool(self._run_session_action("rotate page", lambda s: s.rotate_page(page_index, angle)))

    def delete_pages(self, page_indices: list) -> bool:
        """Delete specified pages from the document."""
        return bool(self._run_session_action("delete pages", lambda s: s.delete_pages(page_indices)))

    def move_page(self, from_index: int, to_index: int) -> bool:
        """Move a page from one position to another."""
        return bool(self._run_session_action("move page", lambda s: s.move_page(from_index, to_index)))

    def insert_blank_page(self, after_index: int = -1) -> bool:
        """Insert a blank A4 page."""
        return bool(self._run_session_action("insert blank page", lambda s: s.insert_blank_page(after_index)))

    def duplicate_pages(self, page_indices: list) -> bool:
        """Duplicate selected pages (copy inserted directly after each original)."""

        def run(s: DocumentSession) -> None:
            s.duplicate_pages(page_indices)  # int result discarded: 0 must not read as failure

        return bool(self._run_session_action("duplicate pages", run))

    def extract_pages(self, page_indices: list, output_path: str) -> bool:
        """Extract selected pages to a new PDF (source document unchanged)."""
        return bool(
            self._run_session_action(
                "extract pages", lambda s: s.extract_pages(page_indices, output_path), applied=False
            )
        )

    def merge_pdf(self, source_path: str, after_index: int = -1) -> bool:
        """Insert pages from another PDF after after_index (-1 = end of document)."""
        return self.merge_pdfs([source_path], after_index)

    def merge_pdfs(self, source_paths: list, after_index: int = -1) -> bool:
        """Insert pages from several PDFs (in order) after after_index (-1 = end)."""

        def run(s: DocumentSession) -> None:
            s.merge_pdfs(source_paths, after_index)  # int result discarded: 0 must not read as failure

        return bool(self._run_session_action("merge PDFs", run))

    def split_document(self, output_dir: str, groups: list, base_name=None) -> List[str]:
        """Split the document into multiple PDFs (source unchanged).

        Returns the list of written file paths, or an empty list on failure.
        """
        result = self._run_session_action(
            "split document", lambda s: s.split_document(output_dir, groups, base_name), applied=False, default=[]
        )
        return result if isinstance(result, list) else []

    def export_text(self, output_path: str, page_indices=None, fmt: str = "txt") -> bool:
        """Export page/document text to a txt or md file (source unchanged)."""

        def run(s: DocumentSession) -> None:
            s.export_text(output_path, page_indices, fmt)  # int result discarded: 0 chars is still success

        return bool(self._run_session_action("export text", run, applied=False))

    def add_watermark(
        self,
        page_indices: Sequence[int],
        text: str,
        fontsize: float = 40.0,
        color: Tuple[float, float, float] = (0.5, 0.5, 0.5),
        opacity: float = 0.3,
        angle: float = 45.0,
    ) -> bool:
        """Add a text watermark to each page in ``page_indices``.

        The caller (UI handler) decides the scope — a single current page or
        every page — keeping the controller Qt/view free. One ``WatermarkText``
        op is added per page (same pattern as batch replace); the guard emits a
        single ``operation_applied`` so the preview re-renders once.
        """

        def run(s: DocumentSession) -> None:
            for i in page_indices:
                s.add_operation(WatermarkText(i, text, fontsize, color, opacity, angle))

        return bool(self._run_session_action("add watermark", run))

    def add_image_watermark(
        self,
        page_indices: Sequence[int],
        image_path: str,
        opacity: float = 0.3,
        scale: float = 0.5,
        rotate: int = 0,
    ) -> bool:
        """Add an image watermark to each page in ``page_indices``.

        Same per-page pattern as :meth:`add_watermark`; the handler decides the
        scope so the controller stays Qt/view free.
        """

        def run(s: DocumentSession) -> None:
            for i in page_indices:
                s.add_operation(WatermarkImage(i, image_path, opacity, scale, rotate))

        return bool(self._run_session_action("add image watermark", run))

    def _on_history_changed(self):
        """Relay session history changed signal."""
        self.history_changed.emit()

    def has_document(self) -> bool:
        return self._session is not None

    def is_current_encrypted(self) -> bool:
        """True when the loaded document was opened from a protected source."""
        return bool(self._session and self._session.is_encrypted)
