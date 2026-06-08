from PySide6.QtCore import QObject, Signal
from typing import Optional
import fitz
from app.model import DocumentSession, Operation, RedactDelete, RedactReplace, CropMargins, RemoveSectionAsImage
from app.encryption import EncryptedPDFError
from app.logger import get_logger

class EditorController(QObject):
    """
    Controller class that manages the DocumentSession and handles business logic.
    Acts as a bridge between the UI (View) and the Data (Model).
    """
    # Signals to notify the UI about state changes
    document_loaded = Signal(str) # Emits file path
    document_closed = Signal()
    history_changed = Signal() # Emits when undo/redo stack changes
    operation_applied = Signal() # Emits when an operation is applied (requires re-render)
    error_occurred = Signal(str) # Emits error message

    def __init__(self):
        super().__init__()
        self._session: Optional[DocumentSession] = None
        self.logger = get_logger()

    @property
    def session(self) -> Optional[DocumentSession]:
        """Read-only access to the current session. Used by Viewer for rendering."""
        return self._session

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
        applied at save time (password protection + permissions).
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
        if not self._session:
            return False
        
        try:
            self._session.add_operation(operation)
            self.operation_applied.emit()
            return True
        except Exception as e:
            self.logger.error(f"Failed to add operation: {e}")
            self.error_occurred.emit(f"Failed to add operation: {e}")
            return False

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
        if not self._session:
            return False
        try:
            self._session.rotate_page(page_index, angle)
            self.operation_applied.emit()
            return True
        except Exception as e:
            self.logger.error(f"Failed to rotate page: {e}")
            self.error_occurred.emit(str(e))
            return False

    def delete_pages(self, page_indices: list) -> bool:
        """Delete specified pages from the document."""
        if not self._session:
            return False
        try:
            self._session.delete_pages(page_indices)
            self.operation_applied.emit()
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete pages: {e}")
            self.error_occurred.emit(str(e))
            return False

    def move_page(self, from_index: int, to_index: int) -> bool:
        """Move a page from one position to another."""
        if not self._session:
            return False
        try:
            self._session.move_page(from_index, to_index)
            self.operation_applied.emit()
            return True
        except Exception as e:
            self.logger.error(f"Failed to move page: {e}")
            self.error_occurred.emit(str(e))
            return False

    def insert_blank_page(self, after_index: int = -1) -> bool:
        """Insert a blank A4 page."""
        if not self._session:
            return False
        try:
            self._session.insert_blank_page(after_index)
            self.operation_applied.emit()
            return True
        except Exception as e:
            self.logger.error(f"Failed to insert blank page: {e}")
            self.error_occurred.emit(str(e))
            return False

    def duplicate_pages(self, page_indices: list) -> bool:
        """Duplicate selected pages (copy inserted directly after each original)."""
        if not self._session:
            return False
        try:
            self._session.duplicate_pages(page_indices)
            self.operation_applied.emit()
            return True
        except Exception as e:
            self.logger.error(f"Failed to duplicate pages: {e}")
            self.error_occurred.emit(str(e))
            return False

    def extract_pages(self, page_indices: list, output_path: str) -> bool:
        """Extract selected pages to a new PDF (source document unchanged)."""
        if not self._session:
            return False
        try:
            self._session.extract_pages(page_indices, output_path)
            return True
        except Exception as e:
            self.logger.error(f"Failed to extract pages: {e}")
            self.error_occurred.emit(str(e))
            return False

    def merge_pdf(self, source_path: str, after_index: int = -1) -> bool:
        """Insert pages from another PDF after after_index (-1 = end of document)."""
        return self.merge_pdfs([source_path], after_index)

    def merge_pdfs(self, source_paths: list, after_index: int = -1) -> bool:
        """Insert pages from several PDFs (in order) after after_index (-1 = end)."""
        if not self._session:
            return False
        try:
            self._session.merge_pdfs(source_paths, after_index)
            self.operation_applied.emit()
            return True
        except Exception as e:
            self.logger.error(f"Failed to merge PDFs: {e}")
            self.error_occurred.emit(str(e))
            return False

    def split_document(self, output_dir: str, groups: list, base_name=None) -> list:
        """Split the document into multiple PDFs (source unchanged).

        Returns the list of written file paths, or an empty list on failure.
        """
        if not self._session:
            return []
        try:
            return self._session.split_document(output_dir, groups, base_name)
        except Exception as e:
            self.logger.error(f"Failed to split document: {e}")
            self.error_occurred.emit(str(e))
            return []

    def export_text(self, output_path: str, page_indices=None, fmt: str = "txt") -> bool:
        """Export page/document text to a txt or md file (source unchanged)."""
        if not self._session:
            return False
        try:
            self._session.export_text(output_path, page_indices, fmt)
            return True
        except Exception as e:
            self.logger.error(f"Failed to export text: {e}")
            self.error_occurred.emit(str(e))
            return False

    def _on_history_changed(self):
        """Relay session history changed signal."""
        self.history_changed.emit()

    def has_document(self) -> bool:
        return self._session is not None

    def is_current_encrypted(self) -> bool:
        """True when the loaded document was opened from a protected source."""
        return bool(self._session and self._session.is_encrypted)
