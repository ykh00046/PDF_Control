"""File-level event handlers for :class:`app.ui.MainWindow`.

Exposes :class:`FileHandlerMixin` covering open / save / close / drag-drop.
All state lives on ``MainWindow``; this mixin holds no instance state.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QLineEdit,
    QMessageBox,
)

from app.config import save_config, set_config_value
from app.encryption import IncorrectPassword, PasswordRequired
from app.i18n import tr
from app.recent_files import add_recent_file, clear_recent_files, get_recent_files, remove_recent_file

if TYPE_CHECKING:
    from app.ui import MainWindow


class FileHandlerMixin:
    """Open / save / drag-drop / close event handlers."""

    def _confirm_discard_changes(self: "MainWindow") -> bool:  # type: ignore[misc]
        """Ask "save changes?" when the session is dirty.

        Returns True when it is safe to proceed (nothing to save, user saved,
        or user chose Discard); False when the user cancelled or a requested
        save did not complete. Shared by open / close / exit.
        """
        if not (self.controller.session and self.controller.session.modified):
            return True
        reply = QMessageBox.question(
            self,
            tr("dialog.save_changes.title"),
            tr("dialog.save_changes.message"),
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Save:
            return self.save_file_as()
        if reply == QMessageBox.StandardButton.Cancel:
            self.logger.info("User cancelled (unsaved changes prompt)")
            return False
        return True

    def _remember_file(self: "MainWindow", file_path: str) -> None:  # type: ignore[misc]
        """Persist last directory + recent list after a successful open/save."""
        self.last_directory = os.path.dirname(file_path)
        set_config_value(self.config, "last_directory", value=self.last_directory)
        add_recent_file(self.config, file_path)
        save_config(self.config)

    def open_file(self: "MainWindow") -> None:  # type: ignore[misc]
        if not self._confirm_discard_changes():
            return

        initial_dir = self.last_directory if self.last_directory else ""
        file_path, _ = QFileDialog.getOpenFileName(self, tr("dialog.open_pdf"), initial_dir, "PDF Files (*.pdf)")
        if file_path:
            if self._load_with_password_prompt(file_path):
                self._remember_file(file_path)
        else:
            self.logger.info("User cancelled file selection")
            self.statusBar().showMessage(tr("status.cancelled_open"))
            self._update_edit_action_states()

    def open_recent_file(self: "MainWindow", file_path: str) -> bool:  # type: ignore[misc]
        """Open an entry from File -> Open Recent; prunes it when missing."""
        if not os.path.isfile(file_path):
            remove_recent_file(self.config, file_path)
            save_config(self.config)
            QMessageBox.warning(self, tr("dialog.error"), tr("error.recent_missing", file_path))
            return False
        if not self._confirm_discard_changes():
            return False
        if self._load_with_password_prompt(file_path):
            self._remember_file(file_path)
            return True
        return False

    def clear_recent_files(self: "MainWindow") -> None:  # type: ignore[misc]
        clear_recent_files(self.config)
        save_config(self.config)

    def _populate_recent_menu(self: "MainWindow") -> None:  # type: ignore[misc]
        """Rebuild File -> Open Recent from config (most recent first).

        Connected to the submenu's ``aboutToShow`` so it never shows stale
        entries after an open or Save As.
        """
        menu = self.recent_menu
        menu.clear()
        recent = get_recent_files(self.config)
        for index, path in enumerate(recent, start=1):
            action = QAction(f"&{index}  {os.path.basename(path)}", self)
            action.setToolTip(path)
            action.setStatusTip(path)
            action.triggered.connect(lambda _checked=False, p=path: self.open_recent_file(p))
            menu.addAction(action)
        if recent:
            menu.addSeparator()
        clear_action = QAction(tr("menu.file.open_recent.clear"), self)
        clear_action.setEnabled(bool(recent))
        clear_action.triggered.connect(self.clear_recent_files)
        menu.addAction(clear_action)

    def close_file(self: "MainWindow") -> bool:  # type: ignore[misc]
        """Close the current document (Ctrl+W), prompting for unsaved changes."""
        if not self.controller.session:
            return False
        if not self._confirm_discard_changes():
            return False
        self.controller.close_document()
        self.statusBar().showMessage(tr("status.closed"))
        return True

    def _load_with_password_prompt(self: "MainWindow", file_path: str) -> bool:  # type: ignore[misc]
        """Load a PDF, prompting for a password when the source is encrypted.

        Loops on an incorrect password until the user succeeds or cancels.
        Returns True only on a successful load.
        """
        password = None
        prompt = tr("dialog.password.prompt")
        while True:
            try:
                return self.controller.load_document(file_path, password=password)
            except PasswordRequired:
                prompt = tr("dialog.password.prompt")
            except IncorrectPassword:
                prompt = tr("dialog.password.retry")

            password, accepted = QInputDialog.getText(
                self,
                tr("dialog.password.title"),
                prompt,
                QLineEdit.Password,
            )
            if not accepted:
                self.logger.info("User cancelled password entry")
                self.statusBar().showMessage(tr("status.cancelled_open"))
                return False

    def save_file_as(self: "MainWindow") -> bool:  # type: ignore[misc]
        return self._commit_save(encryption=None)

    def save_file(self: "MainWindow") -> bool:  # type: ignore[misc]
        """Plain Save (Ctrl+S): overwrite the open file in place.

        An encrypted source is routed to "Encrypt & Save As..." instead --
        a plain in-place save would silently strip its protection.
        """
        session = self.controller.session
        if not session:
            self.statusBar().showMessage(tr("status.no_document_save"))
            return False
        if self.controller.is_current_encrypted():
            self.statusBar().showMessage(tr("status.save_encrypted_redirect"))
            return self.save_file_encrypted()
        return self._commit_save(encryption=None, output_path=session.file_path)

    def save_file_encrypted(self: "MainWindow") -> bool:  # type: ignore[misc]
        """Save As… with password protection / permission restrictions."""
        if not self.controller.session:
            self.statusBar().showMessage(tr("status.no_document_save"))
            return False

        # Local import keeps Qt dialog code out of the module's import-time deps.
        from app.encryption_dialog import EncryptionDialog

        dialog = EncryptionDialog(self)
        if dialog.exec() != EncryptionDialog.Accepted:
            self.statusBar().showMessage(tr("status.cancelled_save"))
            return False
        return self._commit_save(encryption=dialog.get_settings())

    def save_file_decrypted(self: "MainWindow") -> bool:  # type: ignore[misc]
        """Remove protection: save the current encrypted document as a plain PDF.

        Saving with ``encryption=None`` produces an unencrypted copy, so this
        reuses the shared save path. Guarded so it only acts on a document that
        was actually opened from a protected source.
        """
        if not self.controller.session:
            self.statusBar().showMessage(tr("status.no_document_save"))
            return False
        if not self.controller.is_current_encrypted():
            self.statusBar().showMessage(tr("status.not_encrypted"))
            return False
        return self._commit_save(encryption=None, decrypt=True)

    def _commit_save(  # type: ignore[misc]
        self: "MainWindow", encryption=None, decrypt=False, output_path: str | None = None
    ) -> bool:
        """Shared save path: blocking-warning guard, path picker, write.

        ``decrypt=True`` is a cosmetic variant (suffix + status message) of a
        plain save used by the Remove Protection action. ``output_path``
        skips the file picker (plain Save onto the open file).
        """
        if not self.controller.session:
            self.statusBar().showMessage(tr("status.no_document_save"))
            return False

        # Hard-failure guard: if the most recent preview reported text that
        # overflowed even at minimum size, ask before committing to disk.
        if self.controller.session.has_blocking_warnings():
            reply = QMessageBox.warning(
                self,
                tr("warn.save_with_errors.title"),
                tr("warn.save_with_errors.body"),
                QMessageBox.Save | QMessageBox.Cancel,
                QMessageBox.Cancel,
            )
            if reply != QMessageBox.Save:
                self.statusBar().showMessage(tr("status.ready"))
                return False

        if output_path is None:
            suffix = "_decrypted" if decrypt else "_edited"
            current_path = self.controller.session.file_path
            # splitext (not str.replace) so "Report.PDF" and a ".pdf" that
            # appears earlier in the directory path are handled correctly.
            suggested_path = f"{os.path.splitext(current_path)[0]}{suffix}.pdf" if current_path else "untitled.pdf"
            output_path, _ = QFileDialog.getSaveFileName(
                self, tr("dialog.save_pdf_as"), suggested_path, "PDF Files (*.pdf)"
            )

        if output_path:
            # Saving is synchronous and can take up to a few seconds on large
            # documents (measured: ~0.9s for 100p + RemoveSection). Show a wait
            # cursor + status so the blocking window doesn't read as "not
            # responding"; processEvents paints them once before the blocking
            # save. The cursor is always restored in finally (a leaked
            # WaitCursor would persist for the whole session).
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self.statusBar().showMessage(tr("status.saving"))
            QApplication.processEvents()
            try:
                self.controller.save_document(output_path, encryption=encryption)
                saved_path = self.controller.session.file_path if self.controller.session else output_path
                encrypted = encryption is not None and encryption.is_active()
                if decrypt:
                    status_msg = tr("status.decrypted", saved_path)
                elif encrypted:
                    status_msg = tr("status.saved_encrypted", saved_path)
                else:
                    status_msg = tr("status.saved", saved_path)
                self.statusBar().showMessage(status_msg)
                self.logger.info("User saved document successfully")

                self.setWindowTitle(f"{tr('app.title')} - {os.path.basename(saved_path)}")
                self._remember_file(saved_path)
                return True
            except Exception as e:
                self.logger.error(f"Failed to save file: {e}")
                QMessageBox.critical(self, tr("dialog.error"), tr("error.cannot_save", e))
                return False
            finally:
                QApplication.restoreOverrideCursor()

        self.statusBar().showMessage(tr("status.cancelled_save"))
        return False

    def closeEvent(self: "MainWindow", event) -> None:  # type: ignore[misc]
        if not self._confirm_discard_changes():
            event.ignore()
            return

        # Persist window geometry before exiting.
        set_config_value(self.config, "window", "x", value=self.geometry().x())
        set_config_value(self.config, "window", "y", value=self.geometry().y())
        set_config_value(self.config, "window", "width", value=self.geometry().width())
        set_config_value(self.config, "window", "height", value=self.geometry().height())
        save_config(self.config)

        self.controller.close_document()
        event.accept()

    # --- Drag & drop ----------------------------------------------------
    def dragEnterEvent(self: "MainWindow", event) -> None:  # type: ignore[misc]
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith(".pdf"):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self: "MainWindow", event) -> None:  # type: ignore[misc]
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith(".pdf"):
                self.logger.info(f"PDF file dropped: {file_path}")
                if self._confirm_discard_changes() and self._load_with_password_prompt(file_path):
                    self._remember_file(file_path)
                break  # Only open the first PDF.
