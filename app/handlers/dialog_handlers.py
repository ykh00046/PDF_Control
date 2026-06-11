"""Dialog-launching event handlers for :class:`app.ui.MainWindow`.

Exposes :class:`DialogHandlerMixin` which opens child dialogs (batch
replace, crop, remove section, page manager, log viewer, help) and applies
their confirmed results back to the controller.
"""
from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING, Any, Dict, List

from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QMessageBox,
)

from app.batch_replace_dialog import BatchReplaceDialog
from app.i18n import tr
from app.logger import get_log_file_path
from app.model import (
    CropMargins,
    RedactReplace,
    RemoveSectionAsImage,
)

if TYPE_CHECKING:
    from app.ui import MainWindow


class DialogHandlerMixin:
    """Launch child dialogs and apply their results."""

    # --- Batch replace --------------------------------------------------
    def open_batch_replace_dialog(self: "MainWindow") -> None:  # type: ignore[misc]
        if not self.controller.session:
            self.statusBar().showMessage(tr("status.no_document_batch"))
            self.logger.warning(
                "Attempted batch replace with no document loaded."
            )
            return

        dialog = BatchReplaceDialog(self.controller.session, self)
        dialog.replacements_confirmed.connect(self.process_batch_replacements)
        dialog.exec()

    def process_batch_replacements(  # type: ignore[misc]
        self: "MainWindow", replacements: List[Dict[str, Any]]
    ) -> None:
        if not self.controller.session:
            self.logger.error(
                "Attempted to process batch replacements with no document session."
            )
            return

        num_replaced = 0
        for r_data in replacements:
            page_index = r_data["page_index"]
            rect = r_data["rect"]
            new_text = r_data["new_text"]
            fontsize = r_data.get("fontsize") or 0
            wrap = r_data.get("wrap")  # bool from dialog; None falls back to global

            operation = RedactReplace(
                page_index,
                [rect],
                new_text,
                fontfile=self.current_replacement_font_path,
                fontsize=fontsize,
                wrap=wrap,
            )
            # Controller emits operation_applied for each add — batching would
            # avoid repeat signal fan-out, but today the simple loop is
            # sufficient for typical replacement counts.
            if self.controller.add_operation(operation):
                num_replaced += 1

        if num_replaced > 0:
            self.statusBar().showMessage(tr("status.batch_applied", num_replaced))
            self.logger.info(f"Applied {num_replaced} batch replacements.")
        else:
            self.statusBar().showMessage(tr("status.no_batch_applied"))
            self.logger.info("No batch replacements were applied (user selection).")

    # --- Crop -----------------------------------------------------------
    def open_crop_dialog(self: "MainWindow") -> None:  # type: ignore[misc]
        """Open crop dialog to crop page margins."""
        if not self.controller.session or not self.last_selected_rect:
            self.statusBar().showMessage(tr("status.no_selection_crop"))
            self.logger.warning("Attempted crop with no selection.")
            return

        from app.crop_dialog import CropPreviewDialog

        page_index = self.viewer.current_page_index
        page = self.controller.session.doc[page_index]

        dialog = CropPreviewDialog(page, self.last_selected_rect, self)
        dialog.crop_confirmed.connect(lambda settings: self.apply_crop(settings))
        dialog.exec()

    def apply_crop(  # type: ignore[misc]
        self: "MainWindow", crop_settings: dict
    ) -> None:
        """Apply crop operation to the current page."""
        if not self.controller.session:
            return

        page_index = self.viewer.current_page_index
        operation = CropMargins(
            page_index,
            top=crop_settings["top"],
            bottom=crop_settings["bottom"],
            left=crop_settings["left"],
            right=crop_settings["right"],
        )

        if not self.controller.add_operation(operation):
            return
        # Render is handled by signal.
        self.last_selected_rect = None
        self.viewer.clear_selection()
        self.statusBar().showMessage(tr("status.crop_applied"))
        self.logger.info(
            f"User applied crop to page {page_index}: {crop_settings}"
        )

    # --- Remove section -------------------------------------------------
    def open_remove_section_dialog(self: "MainWindow") -> None:  # type: ignore[misc]
        """영역 제거 (이미지 변환) 다이얼로그 열기."""
        if not self.controller.session or not self.last_selected_rect:
            self.statusBar().showMessage(tr("status.no_selection_remove"))
            self.logger.warning("Attempted remove section with no selection.")
            return

        from app.remove_section_dialog import RemoveSectionDialog

        page_index = self.viewer.current_page_index
        page = self.controller.session.doc[page_index]

        # 회전 페이지 감지
        if page.rotation != 0:
            QMessageBox.warning(self, tr("dialog.error"), tr("error.rotated_page"))
            self.logger.warning(
                f"Attempted remove section on rotated page (rotation={page.rotation})"
            )
            return

        dialog = RemoveSectionDialog(page, self.last_selected_rect, self)
        dialog.remove_confirmed.connect(
            lambda settings: self.apply_remove_section(settings)
        )
        dialog.exec()

    def apply_remove_section(  # type: ignore[misc]
        self: "MainWindow", settings: dict
    ) -> None:
        """영역 제거 적용.

        Adding the operation only appends it to the pending history, which
        completes instantly; the heavy rasterizing/merging happens later in
        the render-worker subprocess (preview) or at save time. A staged
        progress dialog here would not correspond to any real work
        (removed in r7-history-policy).
        """
        if not self.controller.session:
            return

        page_index = self.viewer.current_page_index
        dpi = settings.get("dpi", 300)
        fmt = settings.get("format", "jpeg")
        # Use refined rect from dialog if available.
        final_rect = settings.get("rect", self.last_selected_rect)

        self.logger.info(
            f"Applying section removal: page={page_index}, rect={final_rect}, "
            f"dpi={dpi}, fmt={fmt}"
        )

        try:
            operation = RemoveSectionAsImage(
                page_index, final_rect, dpi=dpi, format=fmt
            )

            if not self.controller.add_operation(operation):
                return

            self.last_selected_rect = None
            self.viewer.clear_selection()
            self.statusBar().showMessage(tr("status.remove_applied"))
            self.logger.info(
                f"User applied remove section to page {page_index}: "
                f"DPI={settings['dpi']}, format={settings['format']}"
            )

        except Exception as e:
            self.logger.error(f"Failed to remove section: {e}")
            QMessageBox.critical(
                self, tr("dialog.error"), tr("error.remove_failed", str(e))
            )

    # --- Page manager ---------------------------------------------------
    def open_page_manager_dialog(self: "MainWindow") -> None:  # type: ignore[misc]
        """Open the page manager dialog for reorder/rotate/delete."""
        if not self.controller.session:
            self.statusBar().showMessage(tr("error.no_document"))
            return

        from app.page_manager_dialog import PageManagerDialog

        dialog = PageManagerDialog(self.controller, self)
        dialog.pages_changed.connect(self._on_pages_changed)
        dialog.exec()

        if dialog.changes_made:
            self.viewer.image_cache.clear()
            self.viewer.set_document_session(self.controller.session)
            self._update_history_panel()
            self._update_status_bar_page_info()
            self.statusBar().showMessage(tr("page_manager.changes_applied"))

    def _on_pages_changed(self: "MainWindow") -> None:  # type: ignore[misc]
        """Handle page structure changes from page manager."""
        self.viewer.image_cache.clear()

    # --- Text export ----------------------------------------------------
    def open_text_export_dialog(self: "MainWindow") -> None:  # type: ignore[misc]
        """Open the text export dialog (whole document or current page)."""
        if not self.controller.session:
            self.statusBar().showMessage(tr("status.no_document_export"))
            self.logger.warning("Attempted text export with no document loaded.")
            return

        from app.text_export_dialog import TextExportDialog

        dialog = TextExportDialog(self)
        dialog.export_confirmed.connect(self.apply_text_export)
        dialog.exec()

    def apply_text_export(  # type: ignore[misc]
        self: "MainWindow", settings: dict
    ) -> None:
        """Resolve page scope, prompt for a path, and write the extracted text."""
        if not self.controller.session:
            return

        fmt = settings.get("fmt", "txt")
        if settings.get("scope") == "current":
            page_indices = [self.viewer.current_page_index]
        else:
            page_indices = None  # whole document

        if fmt == "md":
            file_filter = "Markdown Files (*.md)"
            ext = ".md"
        else:
            file_filter = "Text Files (*.txt)"
            ext = ".txt"

        base = self.controller.session.file_path
        suggested = (
            base.rsplit(".", 1)[0] + ext if base else "untitled" + ext
        )
        output_path, _ = QFileDialog.getSaveFileName(
            self, tr("text_export.dialog_title"), suggested, file_filter
        )
        if not output_path:
            self.statusBar().showMessage(tr("status.ready"))
            return
        if not output_path.lower().endswith(ext):
            output_path += ext

        if self.controller.export_text(output_path, page_indices, fmt):
            self.statusBar().showMessage(tr("text_export.success", output_path))
            self.logger.info(f"Exported text to {output_path} ({fmt})")
        else:
            QMessageBox.critical(
                self, tr("dialog.error"), tr("error.export_failed", output_path)
            )

    # --- View logs ------------------------------------------------------
    def view_logs(self: "MainWindow") -> None:  # type: ignore[misc]
        """Open the log file in the system default editor."""
        log_file = get_log_file_path()
        if not log_file.exists():
            QMessageBox.information(
                self,
                tr("dialog.log_not_found.title"),
                tr("dialog.log_not_found.message", log_file),
            )
            return

        try:
            if sys.platform == "win32":
                os.startfile(log_file)
            elif sys.platform == "darwin":
                subprocess.run(["open", log_file])
            else:
                subprocess.run(["xdg-open", log_file])
            self.logger.info("User opened log file")
        except OSError as e:
            self.logger.error(f"Failed to open log file: {e}")
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle(tr("dialog.error"))
            msg.setText(tr("error.open_log", e))
            copy_btn = msg.addButton(
                tr("dialog.log_copy"), QMessageBox.ActionRole
            )
            msg.addButton(QMessageBox.Ok)
            msg.exec()
            if msg.clickedButton() == copy_btn:
                QApplication.clipboard().setText(str(log_file))
                self.statusBar().showMessage(tr("status.log_path_copied"))

    # --- Help -----------------------------------------------------------
    def show_help(self: "MainWindow") -> None:  # type: ignore[misc]
        """Show help dialog with keyboard shortcuts."""
        help_text = f"""
<h2>{tr("app.title")}</h2>

<h3>{tr("dialog.help.shortcuts_header")}</h3>
<ul>
<li><b>Ctrl+O</b> - {tr("dialog.help.shortcut.open")}</li>
<li><b>Ctrl+Shift+S</b> - {tr("dialog.help.shortcut.save")}</li>
<li><b>Ctrl+Z</b> - {tr("dialog.help.shortcut.undo")}</li>
<li><b>Ctrl+Y</b> - {tr("dialog.help.shortcut.redo")}</li>
<li><b>Del</b> - {tr("dialog.help.shortcut.delete")}</li>
<li><b>Ctrl+R</b> - {tr("dialog.help.shortcut.replace")}</li>
<li><b>Ctrl++</b> - {tr("dialog.help.shortcut.zoom_in")}</li>
<li><b>Ctrl+-</b> - {tr("dialog.help.shortcut.zoom_out")}</li>
<li><b>Ctrl+0</b> - {tr("dialog.help.shortcut.fit_width")}</li>
<li><b>Page Up/Down</b> - {tr("dialog.help.shortcut.page_nav")}</li>
<li><b>Ctrl+Wheel</b> - {tr("dialog.help.shortcut.zoom_wheel")}</li>
<li><b>F1</b> - {tr("dialog.help.shortcut.help")}</li>
</ul>

<h3>{tr("dialog.help.usage_header")}</h3>
<ol>
<li>{tr("dialog.help.step1")}</li>
<li>{tr("dialog.help.step2")}</li>
<li>{tr("dialog.help.step3")}</li>
<li>{tr("dialog.help.step4")}</li>
<li>{tr("dialog.help.step5")}</li>
</ol>
        """
        QMessageBox.about(self, tr("dialog.help.title"), help_text)
        self.logger.info("User opened help dialog")
