"""Event handler mixins for MainWindow.

Four stateless mixins supplying handler methods to ``MainWindow`` through
multiple inheritance:

* :class:`FileHandlerMixin` — open / save / drag-drop / close
* :class:`EditHandlerMixin` — undo / redo / delete / replace selection
* :class:`DialogHandlerMixin` — launch child dialogs and apply results
* :class:`StateUpdateMixin` — react to controller / viewer signals

All state remains on ``MainWindow`` (``self.controller``, ``self.viewer``,
``self.config``, etc.); mixins carry no instance state of their own.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import TYPE_CHECKING, Any, Dict, List

import fitz
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction  # noqa: F401  (kept for type-narrowing readers)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QLineEdit,
    QListWidgetItem,
    QMessageBox,
    QProgressDialog,
    QStyle,
)

from app.batch_replace_dialog import BatchReplaceDialog
from app.config import save_config, set_config_value
from app.i18n import tr
from app.logger import get_log_file_path
from app.model import (
    CropMargins,
    RedactDelete,
    RedactReplace,
    RemoveSectionAsImage,
)
from app.text_utils import contains_hangul

if TYPE_CHECKING:
    from app.ui import MainWindow


# ============================================================================
# File handlers
# ============================================================================
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
            if self.controller.load_document(file_path):
                self.last_directory = os.path.dirname(file_path)
                set_config_value(self.config, "last_directory", value=self.last_directory)
                save_config(self.config)
        else:
            self.logger.info("User cancelled file selection")
            self.statusBar().showMessage(tr("status.cancelled_open"))
            self._update_edit_action_states()

    def save_file_as(self: "MainWindow") -> bool:  # type: ignore[misc]
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

        suggested_path = (
            self.controller.session.file_path.replace(".pdf", "_edited.pdf")
            if self.controller.session.file_path
            else "untitled.pdf"
        )
        output_path, _ = QFileDialog.getSaveFileName(
            self, tr("dialog.save_pdf_as"), suggested_path, "PDF Files (*.pdf)"
        )

        if output_path:
            try:
                self.controller.save_document(output_path)
                saved_path = (
                    self.controller.session.file_path
                    if self.controller.session
                    else output_path
                )
                self.statusBar().showMessage(tr("status.saved", saved_path))
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
                if self.controller.load_document(file_path):
                    self.last_directory = os.path.dirname(file_path)
                    set_config_value(self.config, "last_directory", value=self.last_directory)
                    save_config(self.config)
                break  # Only open the first PDF.


# ============================================================================
# Edit handlers
# ============================================================================
class EditHandlerMixin:
    """Undo / redo / delete / replace selection handlers + font selection."""

    def undo_operation(self: "MainWindow") -> None:  # type: ignore[misc]
        if not self.controller.session:
            self.statusBar().showMessage(tr("error.no_document"))
            return

        self.controller.undo()
        self.statusBar().showMessage(tr("status.undo_success"))
        self.last_selected_rect = None
        self.viewer.clear_selection()

    def redo_operation(self: "MainWindow") -> None:  # type: ignore[misc]
        if not self.controller.session:
            self.statusBar().showMessage(tr("error.no_document"))
            return

        self.controller.redo()
        self.statusBar().showMessage(tr("status.redo_success"))
        self.last_selected_rect = None
        self.viewer.clear_selection()

    def delete_selection(self: "MainWindow") -> None:  # type: ignore[misc]
        if not self.controller.session or not self.last_selected_rect:
            self.statusBar().showMessage(tr("error.no_selection_hint"))
            return

        try:
            page_index = self.viewer.current_page_index
            operation = RedactDelete(page_index, [self.last_selected_rect])
            if not self.controller.add_operation(operation):
                return

            self.statusBar().showMessage(
                tr("status.deleted", self.last_selected_rect)
            )
            self.logger.info(f"User deleted selection on page {page_index}")
            self.last_selected_rect = None
            self.viewer.clear_selection()
        except Exception as e:
            self.logger.error(f"Error deleting selection: {e}")
            self.statusBar().showMessage(tr("error.delete_selection", e))

    def _snap_selection_to_text(self: "MainWindow", page, selection_rect):  # type: ignore[misc]
        """Smart Snap: tighten selection rect to span bbox of contained text.

        Returns (target_rect, existing_text).
        """
        target_rect = selection_rect
        try:
            text_instances = page.get_text("dict", clip=selection_rect)
            spans_rects = [
                span["bbox"]
                for block in text_instances.get("blocks", [])
                for line in block.get("lines", [])
                for span in line.get("spans", [])
            ]
            if spans_rects:
                x0 = min(r[0] for r in spans_rects)
                y0 = min(r[1] for r in spans_rects)
                x1 = max(r[2] for r in spans_rects)
                y1 = max(r[3] for r in spans_rects)
                target_rect = fitz.Rect(x0, y0, x1, y1)
                self.logger.debug(f"Smart Snap: {selection_rect} → {target_rect}")
            return target_rect, page.get_textbox(target_rect).strip()
        except Exception as e:
            self.logger.warning(f"Smart snap failed: {e}")
            return selection_rect, page.get_textbox(selection_rect).strip()

    def _prompt_replacement_text(self: "MainWindow", existing_text):  # type: ignore[misc]
        """Open input dialog; returns replacement string or None on cancel/error."""
        try:
            text, ok = QInputDialog.getText(
                self,
                tr("dialog.replace.title"),
                tr("dialog.replace.prompt"),
                QLineEdit.Normal,
                existing_text,
            )
        except Exception as e:
            self.logger.error(f"Failed to open input dialog: {e}")
            self.statusBar().showMessage(tr("dialog.error"))
            return None
        if not ok or text is None:
            self.logger.info("User cancelled replace dialog")
            self.statusBar().showMessage(tr("status.cancelled_replace"))
            return None
        return text

    def _resolve_replacement_font(  # type: ignore[misc]
        self: "MainWindow", replacement_text: str = ""
    ):
        """Return font path, auto-selecting Korean fallback only when needed."""
        font_path = self.current_replacement_font_path
        if font_path:
            return font_path
        if not contains_hangul(replacement_text):
            return None
        from app.fonts import get_default_korean_font_path

        font_path = get_default_korean_font_path()
        if font_path:
            self.logger.info(
                f"Auto-selected default Korean font: {os.path.basename(font_path)}"
            )
            self.statusBar().showMessage(
                tr("status.font_auto_selected", os.path.basename(font_path))
            )
        return font_path

    def replace_selection(self: "MainWindow") -> None:  # type: ignore[misc]
        self.logger.debug("replace_selection called")
        if not self.controller.session or not self.last_selected_rect:
            self.logger.warning("replace_selection: No session or selection")
            self.statusBar().showMessage(tr("error.no_selection_hint"))
            return

        page_index = self.viewer.current_page_index
        page = self.controller.session.doc[page_index]
        target_rect, existing_text = self._snap_selection_to_text(
            page, self.last_selected_rect
        )

        replacement_text = self._prompt_replacement_text(existing_text)
        if replacement_text is None:
            return

        try:
            font_path = self._resolve_replacement_font(replacement_text)
            from app.model import _extract_text_metadata

            meta = _extract_text_metadata(page, target_rect)
            operation = RedactReplace(
                page_index,
                [target_rect],
                replacement_text,
                fontname=meta["fontname"],
                fontfile=font_path,
                fontsize=meta["fontsize"],
                color=meta["color"],
                font_flags=meta["font_flags"],
            )
            if not self.controller.add_operation(operation):
                return
            self.statusBar().showMessage(
                tr("status.replaced", target_rect, replacement_text)
            )
            self.logger.info(f"User replaced selection on page {page_index}")
            self.last_selected_rect = None
            self.viewer.clear_selection()
        except Exception as e:
            self.logger.error(f"Error replacing selection: {e}")
            self.statusBar().showMessage(tr("error.replace_selection", e))

    def select_replacement_font(self: "MainWindow") -> None:  # type: ignore[misc]
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import QFontDialog

        from app.fonts import get_font_path_by_name

        initial_font = QFont()
        if self.current_replacement_font_path:
            # A more robust approach might store QFont properties; today the
            # path is sufficient because we only need the file when applying.
            pass

        # Note: PySide6.QFontDialog.getFont returns (QFont, bool) tuple.
        result = QFontDialog.getFont(initial_font, self, tr("font_dialog.title"))
        font = result[0]
        ok = result[1]

        if ok:
            font_family = font.family()
            font_path = get_font_path_by_name(font_family)

            if font_path:
                self.current_replacement_font_path = font_path
                self.statusBar().showMessage(
                    tr("status.font_selected", os.path.basename(font_path))
                )
                self.logger.info(
                    f"Replacement font selected: {os.path.basename(font_path)}"
                )
                set_config_value(
                    self.config, "replacement_font_path", value=font_path
                )
                save_config(self.config)
                self._update_status_bar_font_info()
            else:
                self.current_replacement_font_path = None
                QMessageBox.warning(
                    self,
                    tr("font_dialog.warning.title"),
                    tr("font_dialog.warning.message", font_family),
                )
                self.statusBar().showMessage(
                    tr("status.font_not_found", font_family)
                )
                self.logger.warning(
                    f"Could not find font file for '{font_family}'"
                )
        else:
            self.statusBar().showMessage(tr("status.font_selection_cancelled"))
            self.logger.info("Font selection cancelled.")


# ============================================================================
# Dialog handlers
# ============================================================================
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

            operation = RedactReplace(
                page_index,
                [rect],
                new_text,
                fontfile=self.current_replacement_font_path,
                fontsize=fontsize,
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
        """영역 제거 적용 (QProgressDialog 사용)."""
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

        progress = QProgressDialog(
            tr("status.remove_processing"),
            tr("batch.button.cancel"),
            0,
            100,
            self,
        )
        progress.setWindowTitle(tr("progress.remove.title"))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()

        try:
            progress.setLabelText(tr("progress.remove.rendering_top"))
            progress.setValue(25)
            QApplication.processEvents()
            if progress.wasCanceled():
                return

            progress.setLabelText(tr("progress.remove.rendering_bottom"))
            progress.setValue(50)
            QApplication.processEvents()
            if progress.wasCanceled():
                return

            progress.setLabelText(tr("progress.remove.merging"))
            progress.setValue(75)
            QApplication.processEvents()
            if progress.wasCanceled():
                return

            operation = RemoveSectionAsImage(
                page_index, final_rect, dpi=dpi, format=fmt
            )

            if not self.controller.add_operation(operation):
                return

            progress.setLabelText(tr("progress.remove.replacing"))
            progress.setValue(90)
            QApplication.processEvents()

            # 작업 추가 직후에는 미리보기를 생략 (성능 최적화).
            # 줌/패닝 등을 하면 자동으로 프리뷰가 렌더링됩니다.

            progress.setValue(100)

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
        finally:
            progress.close()

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
        except Exception as e:
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


# ============================================================================
# Controller / viewer signal reactions
# ============================================================================
class StateUpdateMixin:
    """React to controller/viewer signals; refresh derived UI state."""

    def on_document_loaded(self: "MainWindow", file_path: str) -> None:  # type: ignore[misc]
        """Handle document loaded signal."""
        self.viewer.set_document_session(self.controller.session)
        session = self.controller.session
        if session is not None and session is not getattr(self, "_wired_session", None):
            session.warnings_changed.connect(self._on_warnings_changed)
            self._wired_session = session
        self.statusBar().showMessage(tr("status.opened", file_path))
        self.setWindowTitle(f"{tr('app.title')} - {os.path.basename(file_path)}")
        self._update_edit_action_states()
        self._update_history_panel()
        self._refresh_warning_indicator()
        self.logger.info(f"Document loaded in UI: {file_path}")

    def _on_warnings_changed(self: "MainWindow") -> None:  # type: ignore[misc]
        """Session cache updated — refresh status bar + history panel."""
        self._refresh_warning_indicator()
        self._update_history_panel()

    def on_document_closed(self: "MainWindow") -> None:  # type: ignore[misc]
        """Handle document closed signal."""
        self.viewer.set_document_session(None)
        self.setWindowTitle(tr("app.title"))
        self._update_edit_action_states()
        self._update_history_panel()
        self.statusbar_manager.hide_warning_indicator()
        self.logger.info("Document closed in UI")

    def on_operation_applied(self: "MainWindow") -> None:  # type: ignore[misc]
        """Handle operation applied (or undo/redo)."""
        # Re-render the current page to show changes (e.g. redactions).
        if self.controller.session:
            self.viewer.render_current_page_with_operations()

        self._update_history_panel()
        self._update_edit_action_states()

    def _handle_page_changed(self: "MainWindow", page_index: int) -> None:  # type: ignore[misc]
        self.last_selected_rect = None
        self.viewer.clear_selection()
        self._update_edit_action_states()
        self._update_status_bar_page_info()

    def on_error_occurred(self: "MainWindow", message: str) -> None:  # type: ignore[misc]
        """Handle errors from controller."""
        QMessageBox.critical(self, tr("dialog.error"), message)

    def handle_selection_made(self: "MainWindow", pdf_rect) -> None:  # type: ignore[misc]
        self.statusBar().showMessage(
            tr("status.selection_made", pdf_rect, self.viewer.current_page_index + 1)
        )
        self.logger.debug(
            f"Selection made: {pdf_rect} on page {self.viewer.current_page_index}"
        )
        self.last_selected_rect = pdf_rect
        self._update_edit_action_states()

    # --- Derived UI -----------------------------------------------------
    def _get_operation_display_name(  # type: ignore[misc]
        self: "MainWindow", op
    ) -> str:
        """Get i18n-friendly display name for an operation."""
        op_type_map = {
            "RedactDelete": tr("history.op.delete"),
            "RedactReplace": tr("history.op.replace"),
            "CropMargins": tr("history.op.crop"),
            "RemoveSectionAsImage": tr("history.op.remove_section"),
        }
        return op_type_map.get(op.__class__.__name__, op.__class__.__name__)

    def _update_history_panel(self: "MainWindow") -> None:  # type: ignore[misc]
        self.history_list_widget.clear()
        if not self.controller.session:
            return

        # Build (page_index, intra_page_redaction_index) -> worst severity map.
        # op_index inside OpWarning is the index within the per-page
        # redactions list passed to _insert_replacement_text, so we mirror
        # that counting here.
        warn_map: Dict[tuple, str] = {}
        for p_idx, ws in self.controller.session.last_preview_warnings.items():
            for w in ws:
                key = (p_idx, w.get("op_index", -1))
                sev = w.get("severity", "warn")
                prev = warn_map.get(key)
                if prev != "error":
                    warn_map[key] = sev
        redaction_counter: Dict[int, int] = {}
        for i, op in enumerate(self.controller.session.history):
            op_name = self._get_operation_display_name(op)
            op_str = tr("history.entry", op.page_index + 1, op_name)
            if isinstance(op, RedactReplace):
                # Privacy: don't show actual replacement text, only length.
                text_len = len(op.new_text) if op.new_text else 0
                op_str += f" ({text_len} {tr('history.chars')})"
                if op.fontfile:
                    op_str += f" [{tr('history.font')}: {os.path.basename(op.fontfile)}]"
                op_str += f" @ {time.strftime('%H:%M:%S')}"
            elif isinstance(op, CropMargins):
                margins = []
                if op.top > 0:
                    margins.append(f"T:{op.top:.0f}")
                if op.bottom > 0:
                    margins.append(f"B:{op.bottom:.0f}")
                if op.left > 0:
                    margins.append(f"L:{op.left:.0f}")
                if op.right > 0:
                    margins.append(f"R:{op.right:.0f}")
                if margins:
                    op_str += f" ({', '.join(margins)} pt)"
            elif isinstance(op, RemoveSectionAsImage):
                op_str += (
                    f" ({op.dpi} DPI, {op.format.upper()}, "
                    f"{op.remove_rect.height:.0f}pt {tr('history.removed')})"
                )
                op_str += f" @ {time.strftime('%H:%M:%S')}"

            item = QListWidgetItem(f"{i+1}. {op_str}")

            # Attach warning icon if this op was flagged in the latest preview.
            if isinstance(op, (RedactDelete, RedactReplace)):
                intra_idx = redaction_counter.get(op.page_index, 0)
                redaction_counter[op.page_index] = intra_idx + 1
                sev = warn_map.get((op.page_index, intra_idx))
                if sev == "error":
                    item.setIcon(
                        self.style().standardIcon(QStyle.SP_MessageBoxCritical)
                    )
                    item.setToolTip(tr("warn.history.badge_overflow"))
                elif sev == "warn":
                    item.setIcon(
                        self.style().standardIcon(QStyle.SP_MessageBoxWarning)
                    )
                    item.setToolTip(tr("warn.history.badge_shrunk"))

            self.history_list_widget.addItem(item)

    def _update_edit_action_states(self: "MainWindow") -> None:  # type: ignore[misc]
        session = self.controller.session
        if session and self.viewer.current_page_index != -1:
            self.undo_action.setEnabled(bool(session.history))
            self.redo_action.setEnabled(bool(session.redo_stack))
            self.delete_action.setEnabled(bool(self.last_selected_rect))
            self.replace_action.setEnabled(bool(self.last_selected_rect))
            self.prev_page_action.setEnabled(self.viewer.current_page_index > 0)
            self.next_page_action.setEnabled(
                self.viewer.current_page_index < session.doc.page_count - 1
            )
            self.zoom_in_action.setEnabled(True)
            self.zoom_out_action.setEnabled(True)
            self.fit_to_width_action.setEnabled(True)
            self.history_dock.setEnabled(True)
            self.toggle_history_action.setEnabled(True)
        else:
            self.undo_action.setEnabled(False)
            self.redo_action.setEnabled(False)
            self.delete_action.setEnabled(False)
            self.replace_action.setEnabled(False)
            self.prev_page_action.setEnabled(False)
            self.next_page_action.setEnabled(False)
            self.zoom_in_action.setEnabled(False)
            self.zoom_out_action.setEnabled(False)
            self.fit_to_width_action.setEnabled(False)
            self.history_dock.setEnabled(False)
            self.toggle_history_action.setEnabled(False)

    def _toggle_history_panel(  # type: ignore[misc]
        self: "MainWindow", checked: bool
    ) -> None:
        self.history_dock.setVisible(checked)
        set_config_value(self.config, "ui", "history_panel_visible", value=checked)
        save_config(self.config)

    def _on_page_spinbox_changed(  # type: ignore[misc]
        self: "MainWindow", value: int
    ) -> None:
        """Handle page jump from spinbox."""
        if not self.controller.session:
            return
        target_index = value - 1  # SpinBox is 1-indexed, viewer is 0-indexed.
        if target_index != self.viewer.current_page_index:
            self.viewer.current_page_index = target_index
            self.viewer.page_changed.emit(target_index)
            self.viewer.request_render()
