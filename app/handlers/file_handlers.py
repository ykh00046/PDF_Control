"""File-level event handlers for :class:`app.ui.MainWindow`.

Exposes :class:`FileHandlerMixin` covering open / save / close / drag-drop.
All state lives on ``MainWindow``; this mixin holds no instance state.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFileDialog, QInputDialog, QLineEdit, QMessageBox

from app.config import save_config, set_config_value
from app.encryption import IncorrectPassword, PasswordRequired
from app.i18n import tr

if TYPE_CHECKING:
    from app.ui import MainWindow


class FileHandlerMixin:
    """Open / save / drag-drop / close event handlers."""

    def open_file(self: "MainWindow") -> None:  # type: ignore[misc]
        if self.controller.session and self.controller.session.modified:
            reply = QMessageBox.question(
                self,
                tr("dialog.save_changes.title"),
                tr("dialog.save_changes.message"),
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                if not self.save_file_as():
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                self.logger.info("User cancelled open file operation")
                return

        initial_dir = self.last_directory if self.last_directory else ""
        file_path, _ = QFileDialog.getOpenFileName(
            self, tr("dialog.open_pdf"), initial_dir, "PDF Files (*.pdf)"
        )
        if file_path:
            if self._load_with_password_prompt(file_path):
                self.last_directory = os.path.dirname(file_path)
                set_config_value(self.config, "last_directory", value=self.last_directory)
                save_config(self.config)
        else:
            self.logger.info("User cancelled file selection")
            self.statusBar().showMessage(tr("status.cancelled_open"))
            self._update_edit_action_states()

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

    def _commit_save(self: "MainWindow", encryption=None, decrypt=False) -> bool:  # type: ignore[misc]
        """Shared Save As… path: blocking-warning guard, path picker, write.

        ``decrypt=True`` is a cosmetic variant (suffix + status message) of a
        plain save used by the Remove Protection action.
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

        suffix = "_decrypted.pdf" if decrypt else "_edited.pdf"
        suggested_path = (
            self.controller.session.file_path.replace(".pdf", suffix)
            if self.controller.session.file_path
            else "untitled.pdf"
        )
        output_path, _ = QFileDialog.getSaveFileName(
            self, tr("dialog.save_pdf_as"), suggested_path, "PDF Files (*.pdf)"
        )

        if output_path:
            try:
                self.controller.save_document(output_path, encryption=encryption)
                saved_path = (
                    self.controller.session.file_path
                    if self.controller.session
                    else output_path
                )
                encrypted = encryption is not None and encryption.is_active()
                if decrypt:
                    status_msg = tr("status.decrypted", saved_path)
                elif encrypted:
                    status_msg = tr("status.saved_encrypted", saved_path)
                else:
                    status_msg = tr("status.saved", saved_path)
                self.statusBar().showMessage(status_msg)
                self.logger.info("User saved document successfully")

                self.setWindowTitle(
                    f"{tr('app.title')} - {os.path.basename(saved_path)}"
                )

                self.last_directory = os.path.dirname(saved_path)
                set_config_value(self.config, "last_directory", value=self.last_directory)
                save_config(self.config)
                return True
            except Exception as e:
                self.logger.error(f"Failed to save file: {e}")
                QMessageBox.critical(
                    self, tr("dialog.error"), tr("error.cannot_save", e)
                )
                return False

        self.statusBar().showMessage(tr("status.cancelled_save"))
        return False

    def closeEvent(self: "MainWindow", event) -> None:  # type: ignore[misc]
        if self.controller.session and self.controller.session.modified:
            reply = QMessageBox.question(
                self,
                tr("dialog.save_changes.title"),
                tr("dialog.save_changes.message"),
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Save:
                if not self.save_file_as():
                    event.ignore()
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
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
                if self._load_with_password_prompt(file_path):
                    self.last_directory = os.path.dirname(file_path)
                    set_config_value(self.config, "last_directory", value=self.last_directory)
                    save_config(self.config)
                break  # Only open the first PDF.
