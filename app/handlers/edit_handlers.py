"""Edit-action event handlers for :class:`app.ui.MainWindow`.

Exposes :class:`EditHandlerMixin` covering undo / redo / delete / replace
selection and replacement font selection.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

import fitz
from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox

from app.config import save_config, set_config_value
from app.i18n import tr
from app.model import RedactDelete, RedactReplace
from app.text_utils import contains_hangul

if TYPE_CHECKING:
    from app.ui import MainWindow


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
