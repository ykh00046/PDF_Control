"""Controller/viewer signal reactions for :class:`app.ui.MainWindow`.

Exposes :class:`StateUpdateMixin` which keeps derived UI state (history
panel, edit-action enable flags, warning indicator, window title)
in sync with the controller and viewer.
"""

from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Dict

from PySide6.QtWidgets import QListWidgetItem, QMessageBox, QStyle

from app.config import save_config, set_config_value
from app.i18n import tr
from app.model import (
    CropMargins,
    RedactDelete,
    RedactReplace,
    RemoveSectionAsImage,
)

if TYPE_CHECKING:
    from app.ui import MainWindow


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
        self.statusBar().showMessage(tr("status.selection_made", pdf_rect, self.viewer.current_page_index + 1))
        self.logger.debug(f"Selection made: {pdf_rect} on page {self.viewer.current_page_index}")
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
                op_str += f" ({op.dpi} DPI, {op.format.upper()}, {op.remove_rect.height:.0f}pt {tr('history.removed')})"
                op_str += f" @ {time.strftime('%H:%M:%S')}"

            item = QListWidgetItem(f"{i + 1}. {op_str}")

            # Attach warning icon if this op was flagged in the latest preview.
            if isinstance(op, (RedactDelete, RedactReplace)):
                intra_idx = redaction_counter.get(op.page_index, 0)
                redaction_counter[op.page_index] = intra_idx + 1
                sev = warn_map.get((op.page_index, intra_idx))
                if sev == "error":
                    item.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxCritical))
                    item.setToolTip(tr("warn.history.badge_overflow"))
                elif sev == "warn":
                    item.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxWarning))
                    item.setToolTip(tr("warn.history.badge_shrunk"))
                elif sev == "info":
                    item.setIcon(self.style().standardIcon(QStyle.SP_MessageBoxInformation))
                    item.setToolTip(tr("warn.history.badge_wrapped"))

            self.history_list_widget.addItem(item)

    def _update_edit_action_states(self: "MainWindow") -> None:  # type: ignore[misc]
        session = self.controller.session
        if session and self.viewer.current_page_index != -1:
            self.undo_action.setEnabled(bool(session.history))
            self.redo_action.setEnabled(bool(session.redo_stack))
            self.delete_action.setEnabled(bool(self.last_selected_rect))
            self.replace_action.setEnabled(bool(self.last_selected_rect))
            self.prev_page_action.setEnabled(self.viewer.current_page_index > 0)
            self.next_page_action.setEnabled(self.viewer.current_page_index < session.doc.page_count - 1)
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
