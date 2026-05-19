import fitz # Import fitz
from PySide6.QtWidgets import (QMainWindow, QVBoxLayout, QWidget, QFileDialog, QMenu, QToolBar,
                               QMessageBox, QInputDialog, QDockWidget, QListWidget, QListWidgetItem,
                               QProgressDialog, QApplication, QLineEdit, QLabel, QSpinBox,
                               QToolButton, QStyle)
from PySide6.QtGui import QAction, QShortcut, QKeySequence, QColor
from PySide6.QtCore import Qt # Import Qt for dock widget area
from app.viewer import PDFViewer
from app.model import DocumentSession, PageModel, RedactDelete, RedactReplace, CropMargins, RemoveSectionAsImage
from app.controller import EditorController
from app.logger import setup_logger, get_logger, get_log_file_path
from app.batch_replace_dialog import BatchReplaceDialog # Import BatchReplaceDialog
from app.config import load_config, save_config, get_config_value, set_config_value
from app.i18n import load_translations, tr
from app.text_utils import contains_hangul
from typing import Optional, List, Dict, Any # Import Optional, List, Dict, Any
import os
import subprocess
import sys
import time

class MainWindow(QMainWindow):
    """Main application window."""
    def __init__(self):
        super().__init__()

        # Initialize logging first
        setup_logger()
        self.logger = get_logger()
        self.logger.info("MainWindow initialized")

        # Load configuration
        self.config = load_config()
        self.logger.info("Configuration loaded")

        # Load translations
        load_translations()
        self.logger.info("Translations loaded")

        self.setWindowTitle(tr("app.title"))

        # Restore window geometry from config
        window_x = get_config_value(self.config, "window", "x", default=100)
        window_y = get_config_value(self.config, "window", "y", default=100)
        window_width = get_config_value(self.config, "window", "width", default=1200)
        window_height = get_config_value(self.config, "window", "height", default=800)
        self.setGeometry(window_x, window_y, window_width, window_height)

        # Initialize Controller
        self.controller = EditorController()
        self.controller.document_loaded.connect(self.on_document_loaded)
        self.controller.document_closed.connect(self.on_document_closed)
        self.controller.history_changed.connect(self._update_history_panel)
        self.controller.history_changed.connect(self._update_edit_action_states)
        self.controller.operation_applied.connect(self.on_operation_applied)
        self.controller.error_occurred.connect(self.on_error_occurred)

        self.last_selected_rect: Optional[fitz.Rect] = None # Stores the last selected rectangle
        self.last_directory = get_config_value(self.config, "last_directory", default="")
        self.current_replacement_font_path: Optional[str] = None # Stores the path to the selected replacement font (TTF)

        # Create a central widget and layout
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.viewer = PDFViewer(self)
        self.viewer.setBackgroundBrush(QColor(245, 245, 245))
        layout.addWidget(self.viewer)
        self.viewer.selection_made.connect(self.handle_selection_made) # Connect the selection signal
        self.viewer.page_changed.connect(self._handle_page_changed)
        self.viewer.render_started.connect(lambda: self.statusBar().showMessage(tr("status.rendering")))
        self.viewer.render_finished.connect(lambda: self.statusBar().showMessage(tr("status.render_ready")))
        self.viewer.render_finished.connect(self._update_status_bar_page_info)

        self._setup_dock_widgets() # New method for setting up dock widgets
        self.create_menus()
        self.create_toolbar()
        self.create_status_bar()
        self.create_shortcuts() # Add keyboard shortcuts
        self._apply_styles()

        # Enable drag-and-drop for PDF files
        self.setAcceptDrops(True)
    
    def _setup_dock_widgets(self):
        # Operation History Dock
        self.history_dock = QDockWidget(tr("history_panel.title"), self)
        self.history_list_widget = QListWidget()
        self.history_list_widget.setAlternatingRowColors(True)
        self.history_dock.setWidget(self.history_list_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.history_dock)

        self.history_dock.setVisible(get_config_value(self.config, "ui", "history_panel_visible", default=True))
        # keep toggle action (created later) in sync with dock visibility
        self.history_dock.visibilityChanged.connect(lambda visible: hasattr(self, "toggle_history_action") and self.toggle_history_action.setChecked(visible))

    def on_document_loaded(self, file_path: str):
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

    def _on_warnings_changed(self):
        """Session cache updated — refresh status bar + history panel."""
        self._refresh_warning_indicator()
        self._update_history_panel()

    def on_document_closed(self):
        """Handle document closed signal."""
        self.viewer.set_document_session(None)
        self.setWindowTitle(tr("app.title"))
        self._update_edit_action_states()
        self._update_history_panel()
        if hasattr(self, "_warning_indicator"):
            self._warning_indicator.setVisible(False)
        self.logger.info("Document closed in UI")

    def on_operation_applied(self):
        """Handle operation applied (or undo/redo)."""
        # Re-render the current page to show changes (e.g. redactions)
        # Ideally Viewer should listen to this too, but for now UI drives it.
        if self.controller.session:
            # Check if page count changed (e.g. remove section might eventually do that? No, just image replace)
            # For now just re-render current page with operations
            self.viewer.render_current_page_with_operations()
        
        self._update_history_panel()
        self._update_edit_action_states()

    def _handle_page_changed(self, page_index: int):
        self.last_selected_rect = None
        self.viewer.clear_selection()
        self._update_edit_action_states()
        self._update_status_bar_page_info()

    def on_error_occurred(self, message: str):
        """Handle errors from controller."""
        QMessageBox.critical(self, tr("dialog.error"), message)

    def _get_operation_display_name(self, op) -> str:
        """Get i18n-friendly display name for an operation."""
        op_type_map = {
            'RedactDelete': tr("history.op.delete"),
            'RedactReplace': tr("history.op.replace"),
            'CropMargins': tr("history.op.crop"),
            'RemoveSectionAsImage': tr("history.op.remove_section"),
        }
        return op_type_map.get(op.__class__.__name__, op.__class__.__name__)

    def _update_history_panel(self):
        self.history_list_widget.clear()
        if self.controller.session:
            # Build (page_index, intra_page_redaction_index) -> worst severity map.
            # op_index inside OpWarning is the index within the per-page redactions
            # list passed to _insert_replacement_text, so we mirror that counting here.
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
                # Display a user-friendly, i18n representation of the operation
                op_name = self._get_operation_display_name(op)
                op_str = tr("history.entry", op.page_index + 1, op_name)
                if isinstance(op, RedactReplace):
                    # Privacy: Don't show actual replacement text, only length
                    text_len = len(op.new_text) if op.new_text else 0
                    op_str += f" ({text_len} {tr('history.chars')})"
                    if op.fontfile:
                        op_str += f" [{tr('history.font')}: {os.path.basename(op.fontfile)}]"
                    op_str += f" @ {time.strftime('%H:%M:%S')}"
                elif isinstance(op, CropMargins):
                    # Show which margins are being cropped
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
                    # Show DPI, format, and removed height
                    op_str += f" ({op.dpi} DPI, {op.format.upper()}, {op.remove_rect.height:.0f}pt {tr('history.removed')})"
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
            
            # Highlight redo stack operations (optional, for visual clarity)
            # for i, op in enumerate(self.current_session.redo_stack):
            #     op_str = f"Redo Page {op.page_index + 1}: {op.__class__.__name__}"
            #     self.history_list_widget.addItem(f"  > {op_str}")

    def create_menus(self):
        file_menu = self.menuBar().addMenu(tr("menu.file"))

        open_action = QAction(tr("menu.file.open"), self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_as_action = QAction(tr("menu.file.save_as"), self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_file_as)
        file_menu.addAction(save_as_action)

        file_menu.addSeparator()

        exit_action = QAction(tr("menu.file.exit"), self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = self.menuBar().addMenu(tr("menu.edit"))
        self.undo_action = QAction(tr("menu.edit.undo"), self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.triggered.connect(self.undo_operation)
        edit_menu.addAction(self.undo_action)
        self.undo_action.setEnabled(False) # Initially disabled

        self.redo_action = QAction(tr("menu.edit.redo"), self)
        self.redo_action.setShortcut("Ctrl+Y")
        self.redo_action.triggered.connect(self.redo_operation)
        edit_menu.addAction(self.redo_action)
        self.redo_action.setEnabled(False) # Initially disabled

        edit_menu.addSeparator()

        select_font_action = QAction(tr("menu.edit.select_font"), self)
        select_font_action.triggered.connect(self.select_replacement_font)
        edit_menu.addAction(select_font_action)

        view_menu = self.menuBar().addMenu(tr("menu.view"))
        self.zoom_in_action = QAction(tr("menu.view.zoom_in"), self)
        self.zoom_in_action.setShortcut("Ctrl++")
        self.zoom_in_action.triggered.connect(self.viewer.zoom_in)
        view_menu.addAction(self.zoom_in_action)

        self.zoom_out_action = QAction(tr("menu.view.zoom_out"), self)
        self.zoom_out_action.setShortcut("Ctrl+-")
        self.zoom_out_action.triggered.connect(self.viewer.zoom_out)
        view_menu.addAction(self.zoom_out_action)

        self.fit_to_width_action = QAction(tr("menu.view.fit_to_width"), self)
        self.fit_to_width_action.setShortcut("Ctrl+0")
        self.fit_to_width_action.triggered.connect(self.viewer.fit_to_width)
        view_menu.addAction(self.fit_to_width_action)

        self.toggle_history_action = QAction(tr("menu.view.history_toggle"), self, checkable=True)
        self.toggle_history_action.setChecked(self.history_dock.isVisible())
        self.toggle_history_action.toggled.connect(self._toggle_history_panel)
        view_menu.addAction(self.toggle_history_action)

        tools_menu = self.menuBar().addMenu(tr("menu.tools"))
        batch_replace_action = QAction(tr("menu.tools.batch_replace"), self)
        batch_replace_action.triggered.connect(self.open_batch_replace_dialog)
        tools_menu.addAction(batch_replace_action)

        crop_page_action = QAction(tr("menu.tools.crop_page"), self)
        crop_page_action.setShortcut("Ctrl+Shift+C")
        crop_page_action.triggered.connect(self.open_crop_dialog)
        tools_menu.addAction(crop_page_action)

        remove_section_action = QAction(tr("menu.tools.remove_section"), self)
        remove_section_action.setShortcut("Ctrl+Shift+X")
        remove_section_action.triggered.connect(self.open_remove_section_dialog)
        tools_menu.addAction(remove_section_action)

        tools_menu.addSeparator()

        page_manager_action = QAction(tr("menu.tools.page_manager"), self)
        page_manager_action.setShortcut("Ctrl+Shift+P")
        page_manager_action.triggered.connect(self.open_page_manager_dialog)
        tools_menu.addAction(page_manager_action)

        help_menu = self.menuBar().addMenu(tr("menu.help"))
        view_logs_action = QAction(tr("menu.help.view_logs"), self)
        view_logs_action.triggered.connect(self.view_logs)
        help_menu.addAction(view_logs_action)

    def view_logs(self):
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
            if sys.platform == 'win32':
                os.startfile(log_file)
            elif sys.platform == 'darwin':
                subprocess.run(['open', log_file])
            else:
                subprocess.run(['xdg-open', log_file])
            self.logger.info("User opened log file")
        except Exception as e:
            self.logger.error(f"Failed to open log file: {e}")
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Warning)
            msg.setWindowTitle(tr("dialog.error"))
            msg.setText(tr("error.open_log", e))
            copy_btn = msg.addButton(tr("dialog.log_copy"), QMessageBox.ActionRole)
            msg.addButton(QMessageBox.Ok)
            msg.exec()
            if msg.clickedButton() == copy_btn:
                QApplication.clipboard().setText(str(log_file))
                self.statusBar().showMessage(tr("status.log_path_copied"))

    def open_batch_replace_dialog(self):
        if not self.controller.session:
            self.statusBar().showMessage(tr("status.no_document_batch"))
            self.logger.warning("Attempted batch replace with no document loaded.")
            return

        dialog = BatchReplaceDialog(self.controller.session, self)
        dialog.replacements_confirmed.connect(self.process_batch_replacements)
        dialog.exec()

    def open_crop_dialog(self):
        """Open crop dialog to crop page margins."""
        if not self.controller.session or not self.last_selected_rect:
            self.statusBar().showMessage(tr("status.no_selection_crop"))
            self.logger.warning("Attempted crop with no selection.")
            return

        from app.crop_dialog import CropPreviewDialog
        from app.model import CropMargins

        page_index = self.viewer.current_page_index
        page = self.controller.session.doc[page_index]

        dialog = CropPreviewDialog(page, self.last_selected_rect, self)
        dialog.crop_confirmed.connect(lambda settings: self.apply_crop(settings))
        dialog.exec()

    def apply_crop(self, crop_settings: dict):
        """Apply crop operation to the current page."""
        if not self.controller.session:
            return

        from app.model import CropMargins

        page_index = self.viewer.current_page_index
        operation = CropMargins(
            page_index,
            top=crop_settings["top"],
            bottom=crop_settings["bottom"],
            left=crop_settings["left"],
            right=crop_settings["right"]
        )

        if not self.controller.add_operation(operation):
            return
        # render handled by signal
        self.last_selected_rect = None  # Clear selection after action
        self.viewer.clear_selection()  # Clear visual selection highlight
        self.statusBar().showMessage(tr("status.crop_applied"))
        self.logger.info(f"User applied crop to page {page_index}: {crop_settings}")

    def open_remove_section_dialog(self):
        """영역 제거 (이미지 변환) 다이얼로그 열기"""
        if not self.controller.session or not self.last_selected_rect:
            self.statusBar().showMessage(tr("status.no_selection_remove"))
            self.logger.warning("Attempted remove section with no selection.")
            return

        from app.remove_section_dialog import RemoveSectionDialog

        page_index = self.viewer.current_page_index
        page = self.controller.session.doc[page_index]

        # 회전 페이지 감지
        if page.rotation != 0:
            QMessageBox.warning(
                self,
                tr("dialog.error"),
                tr("error.rotated_page")
            )
            self.logger.warning(f"Attempted remove section on rotated page (rotation={page.rotation})")
            return

        dialog = RemoveSectionDialog(page, self.last_selected_rect, self)
        dialog.remove_confirmed.connect(lambda settings: self.apply_remove_section(settings))
        dialog.exec()

    def apply_remove_section(self, settings: dict):
        """영역 제거 적용 (QProgressDialog 사용)"""
        if not self.controller.session:
            return

        page_index = self.viewer.current_page_index
        dpi = settings.get("dpi", 300)
        fmt = settings.get("format", "jpeg")
        # Use refined rect from dialog if available
        final_rect = settings.get("rect", self.last_selected_rect)

        self.logger.info(f"Applying section removal: page={page_index}, rect={final_rect}, dpi={dpi}, fmt={fmt}")

        # 진행률 다이얼로그
        progress = QProgressDialog(
            tr("status.remove_processing"),
            tr("batch.button.cancel"),
            0, 100,
            self
        )
        progress.setWindowTitle(tr("progress.remove.title"))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()

        try:
            # 단계별 진행률 표시
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

            # 연산 생성 및 적용
            from app.model import RemoveSectionAsImage
            operation = RemoveSectionAsImage(
                page_index,
                final_rect,
                dpi=dpi,
                format=fmt
            )

            if not self.controller.add_operation(operation):
                return

            progress.setLabelText(tr("progress.remove.replacing"))
            progress.setValue(90)
            QApplication.processEvents()

            # 작업 추가 직후에는 미리보기를 생략 (성능 최적화)
            # 줌/패닝 등을 하면 자동으로 프리뷰가 렌더링됩니다

            progress.setValue(100)

            self.last_selected_rect = None  # Clear selection after action
            self.viewer.clear_selection()  # Clear visual selection highlight
            self.statusBar().showMessage(tr("status.remove_applied"))
            self.logger.info(f"User applied remove section to page {page_index}: DPI={settings['dpi']}, format={settings['format']}")

        except Exception as e:
            self.logger.error(f"Failed to remove section: {e}")
            QMessageBox.critical(self, tr("dialog.error"), tr("error.remove_failed", str(e)))
        finally:
            progress.close()

    def open_page_manager_dialog(self):
        """Open the page manager dialog for reorder/rotate/delete."""
        if not self.controller.session:
            self.statusBar().showMessage(tr("error.no_document"))
            return

        from app.page_manager_dialog import PageManagerDialog

        dialog = PageManagerDialog(self.controller, self)
        dialog.pages_changed.connect(self._on_pages_changed)
        dialog.exec()

        if dialog.changes_made:
            # Refresh viewer after page changes
            self.viewer.image_cache.clear()
            self.viewer.set_document_session(self.controller.session)
            self._update_history_panel()
            self._update_status_bar_page_info()
            self.statusBar().showMessage(tr("page_manager.changes_applied"))

    def _on_pages_changed(self):
        """Handle page structure changes from page manager."""
        # Clear viewer cache since page structure changed
        self.viewer.image_cache.clear()

    def process_batch_replacements(self, replacements: List[Dict[str, Any]]):
        if not self.controller.session:
            self.logger.error("Attempted to process batch replacements with no document session.")
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
            # We should batch add operations if possible to avoid multiple signal emits?
            # Controller emits operation_applied for each add.
            # Ideally controller handles batch update.
            # But for now, let's add one by one.
            if self.controller.add_operation(operation):
                num_replaced += 1

        if num_replaced > 0:
            # Signal triggers render
            self.statusBar().showMessage(tr("status.batch_applied", num_replaced))
            self.logger.info(f"Applied {num_replaced} batch replacements.")
        else:
            self.statusBar().showMessage(tr("status.no_batch_applied"))
            self.logger.info("No batch replacements were applied (user selection).")

    def create_toolbar(self):
        toolbar = self.addToolBar(tr("toolbar.edit"))

        self.delete_action = QAction(tr("toolbar.delete"), self)
        self.delete_action.setToolTip(tr("toolbar.delete.tooltip"))
        self.delete_action.triggered.connect(self.delete_selection)
        toolbar.addAction(self.delete_action)

        self.replace_action = QAction(tr("toolbar.replace"), self)
        self.replace_action.setToolTip(tr("toolbar.replace.tooltip"))
        self.replace_action.triggered.connect(self.replace_selection)
        toolbar.addAction(self.replace_action)

        toolbar.addSeparator()

        # Reuse undo/redo actions from menu to maintain state synchronization
        toolbar.addAction(self.undo_action)
        toolbar.addAction(self.redo_action)

        toolbar.addSeparator()

        self.prev_page_action = QAction(tr("toolbar.prev_page"), self)
        self.prev_page_action.triggered.connect(self.viewer.prev_page)
        toolbar.addAction(self.prev_page_action)

        # Page jump (GoTo) SpinBox
        self.page_spinbox = QSpinBox()
        self.page_spinbox.setMinimum(1)
        self.page_spinbox.setMaximum(1)
        self.page_spinbox.setPrefix(tr("toolbar.page_prefix"))
        self.page_spinbox.setSuffix("")
        self.page_spinbox.setToolTip(tr("toolbar.page_goto.tooltip"))
        self.page_spinbox.setFixedWidth(100)
        self.page_spinbox.valueChanged.connect(self._on_page_spinbox_changed)
        toolbar.addWidget(self.page_spinbox)

        self.next_page_action = QAction(tr("toolbar.next_page"), self)
        self.next_page_action.triggered.connect(self.viewer.next_page)
        toolbar.addAction(self.next_page_action)

        zoom_toolbar = self.addToolBar(tr("toolbar.zoom"))
        zoom_toolbar.addAction(self.zoom_in_action)
        zoom_toolbar.addAction(self.zoom_out_action)
        zoom_toolbar.addAction(self.fit_to_width_action)

        self._update_edit_action_states() # Set initial states

    def undo_operation(self):
        if not self.controller.session:
            self.statusBar().showMessage(tr("error.no_document"))
            return

        self.controller.undo()
        # Note: render and status updates are handled by signals (on_operation_applied)
        # But we can add specific messages here if we want, or rely on generic one.
        # For now, let's keep it simple.
        self.statusBar().showMessage(tr("status.undo_success"))
        self.last_selected_rect = None
        self.viewer.clear_selection()

    def redo_operation(self):
        if not self.controller.session:
            self.statusBar().showMessage(tr("error.no_document"))
            return

        self.controller.redo()
        self.statusBar().showMessage(tr("status.redo_success"))
        self.last_selected_rect = None
        self.viewer.clear_selection()
    
    def _update_edit_action_states(self):
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
            self.history_dock.setEnabled(True) # Enable history dock when document is open
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
            self.history_dock.setEnabled(False) # Disable history dock when no document is open
            self.toggle_history_action.setEnabled(False)

    def handle_selection_made(self, pdf_rect: fitz.Rect):
        self.statusBar().showMessage(tr("status.selection_made", pdf_rect, self.viewer.current_page_index + 1))
        self.logger.debug(f"Selection made: {pdf_rect} on page {self.viewer.current_page_index}")
        self.last_selected_rect = pdf_rect
        self._update_edit_action_states() # Update button states after selection

    def delete_selection(self):
        if not self.controller.session or not self.last_selected_rect:
            self.statusBar().showMessage(tr("error.no_selection_hint"))
            return

        try:
            page_index = self.viewer.current_page_index
            operation = RedactDelete(page_index, [self.last_selected_rect])
            if not self.controller.add_operation(operation):
                return
            
            # Signal handles update, but we clear local selection state
            self.statusBar().showMessage(tr("status.deleted", self.last_selected_rect))
            self.logger.info(f"User deleted selection on page {page_index}")
            self.last_selected_rect = None # Clear selection after action
            self.viewer.clear_selection()  # Clear visual selection highlight
        except Exception as e:
            self.logger.error(f"Error deleting selection: {e}")
            self.statusBar().showMessage(tr("error.delete_selection", e))

    def _snap_selection_to_text(self, page, selection_rect):
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

    def _prompt_replacement_text(self, existing_text):
        """Open input dialog; returns replacement string or None on cancel/error."""
        try:
            text, ok = QInputDialog.getText(
                self, tr("dialog.replace.title"), tr("dialog.replace.prompt"),
                QLineEdit.Normal, existing_text,
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

    def _resolve_replacement_font(self, replacement_text: str = ""):
        """Return font path, auto-selecting Korean fallback only when needed."""
        font_path = self.current_replacement_font_path
        if font_path:
            return font_path
        if not contains_hangul(replacement_text):
            return None
        from app.fonts import get_default_korean_font_path
        font_path = get_default_korean_font_path()
        if font_path:
            self.logger.info(f"Auto-selected default Korean font: {os.path.basename(font_path)}")
            self.statusBar().showMessage(tr("status.font_auto_selected", os.path.basename(font_path)))
        return font_path

    def replace_selection(self):
        self.logger.debug("replace_selection called")
        if not self.controller.session or not self.last_selected_rect:
            self.logger.warning("replace_selection: No session or selection")
            self.statusBar().showMessage(tr("error.no_selection_hint"))
            return

        page_index = self.viewer.current_page_index
        page = self.controller.session.doc[page_index]
        target_rect, existing_text = self._snap_selection_to_text(page, self.last_selected_rect)

        replacement_text = self._prompt_replacement_text(existing_text)
        if replacement_text is None:
            return

        try:
            font_path = self._resolve_replacement_font(replacement_text)
            from app.model import _extract_text_metadata
            meta = _extract_text_metadata(page, target_rect)
            operation = RedactReplace(
                page_index, [target_rect], replacement_text,
                fontname=meta["fontname"],
                fontfile=font_path,
                fontsize=meta["fontsize"],
                color=meta["color"],
                font_flags=meta["font_flags"],
            )
            if not self.controller.add_operation(operation):
                return
            self.statusBar().showMessage(tr("status.replaced", target_rect, replacement_text))
            self.logger.info(f"User replaced selection on page {page_index}")
            self.last_selected_rect = None
            self.viewer.clear_selection()
        except Exception as e:
            self.logger.error(f"Error replacing selection: {e}")
            self.statusBar().showMessage(tr("error.replace_selection", e))
        
    def create_status_bar(self):
        self.statusBar().showMessage(tr("status.ready"))

        # Current font indicator
        self._status_font_info = QLabel("")
        self._status_font_info.setStyleSheet("color: #555; margin-right: 10px;")
        self.statusBar().addPermanentWidget(self._status_font_info)
        self._update_status_bar_font_info()

        # Text-fit warning indicator (hidden when no warnings)
        self._warning_indicator = QToolButton(self)
        self._warning_indicator.setAutoRaise(True)
        self._warning_indicator.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._warning_indicator.setIcon(
            self.style().standardIcon(QStyle.SP_MessageBoxWarning)
        )
        self._warning_indicator.setVisible(False)
        self._warning_indicator.clicked.connect(self._show_warning_details)
        self.statusBar().addPermanentWidget(self._warning_indicator)

        self._status_page_info = QLabel("")
        self.statusBar().addPermanentWidget(self._status_page_info)
        self._update_status_bar_page_info()

    def _refresh_warning_indicator(self):
        """Sync the status bar warning widget with session cache state."""
        session = self.controller.session if self.controller else None
        if session is None or not session.last_preview_warnings:
            self._warning_indicator.setVisible(False)
            return
        total = sum(
            1 for ws in session.last_preview_warnings.values()
            for w in ws if w.get("severity") in ("warn", "error")
        )
        if total == 0:
            self._warning_indicator.setVisible(False)
            return
        has_error = session.has_blocking_warnings()
        icon_enum = QStyle.SP_MessageBoxCritical if has_error else QStyle.SP_MessageBoxWarning
        self._warning_indicator.setIcon(self.style().standardIcon(icon_enum))
        self._warning_indicator.setText(tr("warn.indicator.label", total))
        self._warning_indicator.setToolTip(tr("warn.indicator.tooltip"))
        self._warning_indicator.setVisible(True)

    def _show_warning_details(self):
        """Modal listing of all cached preview warnings."""
        session = self.controller.session if self.controller else None
        if session is None or not session.last_preview_warnings:
            return
        lines = []
        for page_idx, ws in sorted(session.last_preview_warnings.items()):
            for w in ws:
                code = w.get("code", "")
                detail = w.get("detail", {}) or {}
                if code == "text.shrunk":
                    lines.append(tr(
                        "warn.code.text.shrunk",
                        page_idx + 1,
                        detail.get("fontsize_from", 0),
                        detail.get("fontsize_to", 0),
                    ))
                elif code == "text.overflow":
                    lines.append(tr("warn.code.text.overflow", page_idx + 1))
                else:
                    lines.append(f"p{page_idx + 1}: {code}")
        QMessageBox.information(
            self,
            tr("warn.details.title"),
            "\n".join(lines) if lines else tr("warn.details.none"),
        )

    def create_shortcuts(self):
        """Create keyboard shortcuts for common actions."""
        # Del key for delete selection
        delete_shortcut = QShortcut(QKeySequence(Qt.Key_Delete), self)
        delete_shortcut.activated.connect(self.delete_selection)

        # Ctrl+R for replace
        replace_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        replace_shortcut.activated.connect(self.replace_selection)

        # Page Up/Down for page navigation
        page_up_shortcut = QShortcut(QKeySequence(Qt.Key_PageUp), self)
        page_up_shortcut.activated.connect(self.viewer.prev_page)

        page_down_shortcut = QShortcut(QKeySequence(Qt.Key_PageDown), self)
        page_down_shortcut.activated.connect(self.viewer.next_page)

        # F1 for help (could open documentation or about dialog)
        help_shortcut = QShortcut(QKeySequence(Qt.Key_F1), self)
        help_shortcut.activated.connect(self.show_help)

        self.logger.info("Keyboard shortcuts initialized: Del, Ctrl+R, PageUp/Down, F1")

    def show_help(self):
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

    def select_replacement_font(self):
        from PySide6.QtWidgets import QFontDialog
        from PySide6.QtGui import QFont
        from app.fonts import get_font_path_by_name

        initial_font = QFont()
        if self.current_replacement_font_path:
            # This is a simplification; a more robust approach might store QFont properties
            pass

        # Note: PySide6.QFontDialog.getFont returns (QFont, bool) tuple
        result = QFontDialog.getFont(initial_font, self, tr("font_dialog.title"))
        font = result[0]
        ok = result[1]

        if ok:
            font_family = font.family()
            font_path = get_font_path_by_name(font_family)
            
            if font_path:
                self.current_replacement_font_path = font_path
                self.statusBar().showMessage(tr("status.font_selected", os.path.basename(font_path)))
                self.logger.info(f"Replacement font selected: {os.path.basename(font_path)}")
                set_config_value(self.config, "replacement_font_path", value=font_path)
                save_config(self.config)  # Save immediately for crash safety
                self._update_status_bar_font_info()
            else:
                self.current_replacement_font_path = None
                QMessageBox.warning(self, tr("font_dialog.warning.title"), tr("font_dialog.warning.message", font_family))
                self.statusBar().showMessage(tr("status.font_not_found", font_family))
                self.logger.warning(f"Could not find font file for '{font_family}'")
        else:
            self.statusBar().showMessage(tr("status.font_selection_cancelled"))
            self.logger.info("Font selection cancelled.")
    
    def open_file(self):
        if self.controller.session and self.controller.session.modified:
            # Prompt to save existing document
            reply = QMessageBox.question(self, tr("dialog.save_changes.title"),
                                         tr("dialog.save_changes.message"),
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                if not self.save_file_as():
                    return # User cancelled save, so cancel open
            elif reply == QMessageBox.StandardButton.Cancel:
                self.logger.info("User cancelled open file operation")
                return # User cancelled opening new file

        # Use last directory from config
        initial_dir = self.last_directory if self.last_directory else ""
        file_path, _ = QFileDialog.getOpenFileName(self, tr("dialog.open_pdf"), initial_dir, "PDF Files (*.pdf)")
        if file_path:
            # Controller handles loading and error signals
            if self.controller.load_document(file_path):
                # Update last directory config immediately (or could be in on_document_loaded)
                self.last_directory = os.path.dirname(file_path)
                set_config_value(self.config, "last_directory", value=self.last_directory)
                save_config(self.config)
        else:
            self.logger.info("User cancelled file selection")
            self.statusBar().showMessage(tr("status.cancelled_open"))
            self._update_edit_action_states()

    def save_file_as(self) -> bool:
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

        suggested_path = self.controller.session.file_path.replace(".pdf", "_edited.pdf") if self.controller.session.file_path else "untitled.pdf"
        output_path, _ = QFileDialog.getSaveFileName(self, tr("dialog.save_pdf_as"), suggested_path, "PDF Files (*.pdf)")

        if output_path:
            try:
                self.controller.save_document(output_path)
                saved_path = self.controller.session.file_path if self.controller.session else output_path
                self.statusBar().showMessage(tr("status.saved", saved_path))
                self.logger.info(f"User saved document successfully")

                self.setWindowTitle(f"{tr('app.title')} - {os.path.basename(saved_path)}")

                # Update last directory in config
                self.last_directory = os.path.dirname(saved_path)
                set_config_value(self.config, "last_directory", value=self.last_directory)
                save_config(self.config)  # Save immediately for crash safety
                return True
            except Exception as e:
                self.logger.error(f"Failed to save file: {e}")
                # Controller emits error_occurred, but we catch here to return False?
                # Controller implementation re-raises exception.
                QMessageBox.critical(self, tr("dialog.error"), tr("error.cannot_save", e))
                return False
        
        self.statusBar().showMessage(tr("status.cancelled_save"))
        return False

    def closeEvent(self, event):
        if self.controller.session and self.controller.session.modified:
            reply = QMessageBox.question(self, tr("dialog.save_changes.title"),
                                         tr("dialog.save_changes.message"),
                                         QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Save:
                if not self.save_file_as():
                    event.ignore()
                    return
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
        
        # Save window geometry
        set_config_value(self.config, "window", "x", value=self.geometry().x())
        set_config_value(self.config, "window", "y", value=self.geometry().y())
        set_config_value(self.config, "window", "width", value=self.geometry().width())
        set_config_value(self.config, "window", "height", value=self.geometry().height())
        save_config(self.config)

        # Close document properly
        self.controller.close_document()
        event.accept()

    def _toggle_history_panel(self, checked: bool):
        self.history_dock.setVisible(checked)
        set_config_value(self.config, "ui", "history_panel_visible", value=checked)
        save_config(self.config)

    def _on_page_spinbox_changed(self, value: int):
        """Handle page jump from spinbox."""
        if not self.controller.session:
            return
        target_index = value - 1  # SpinBox is 1-indexed, viewer is 0-indexed
        if target_index != self.viewer.current_page_index:
            self.viewer.current_page_index = target_index
            self.viewer.page_changed.emit(target_index)
            self.viewer.request_render()

    def _update_status_bar_page_info(self):
        if self.controller.session and self.viewer.current_page_index != -1:
            page_num = self.viewer.current_page_index + 1
            total = self.controller.session.doc.page_count
            zoom_pct = int(self.viewer.zoom_level * 100)
            self._status_page_info.setText(tr("status.page_info", page_num, total, zoom_pct))

            # Sync page spinbox (block signals to avoid recursion)
            self.page_spinbox.blockSignals(True)
            self.page_spinbox.setMaximum(total)
            self.page_spinbox.setValue(page_num)
            self.page_spinbox.blockSignals(False)
        else:
            self._status_page_info.setText("")
            self.page_spinbox.blockSignals(True)
            self.page_spinbox.setMinimum(1)
            self.page_spinbox.setMaximum(1)
            self.page_spinbox.setValue(1)
            self.page_spinbox.blockSignals(False)

    def _update_status_bar_font_info(self):
        """Update the font info label in status bar."""
        if self.current_replacement_font_path:
            font_name = os.path.basename(self.current_replacement_font_path)
            self._status_font_info.setText(tr("status.current_font", font_name))
        else:
            self._status_font_info.setText(tr("status.font_default"))

    # --- Drag & Drop support ---
    def dragEnterEvent(self, event):
        """Accept drag events for PDF files."""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith('.pdf'):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        """Handle dropped PDF files."""
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith('.pdf'):
                self.logger.info(f"PDF file dropped: {file_path}")
                if self.controller.load_document(file_path):
                    self.last_directory = os.path.dirname(file_path)
                    set_config_value(self.config, "last_directory", value=self.last_directory)
                    save_config(self.config)
                break  # Only open the first PDF

    def _apply_styles(self):
        # Explicit text color alongside background to avoid white-on-white
        # on Windows dark mode (OS provides light foreground without our override)
        self.setStyleSheet("""
        QMainWindow { background: #f7f8fa; color: #1a1a1a; }
        QMenuBar { background: #f0f2f5; color: #1a1a1a; }
        QMenuBar::item:selected { background: #d0d4da; }
        QMenu { background: #ffffff; color: #1a1a1a; }
        QMenu::item:selected { background: #0078d4; color: #ffffff; }
        QToolBar { spacing: 6px; padding: 4px 6px; background: #f0f2f5; border: 1px solid #e0e2e6; color: #1a1a1a; }
        QToolBar QToolButton { color: #1a1a1a; }
        QStatusBar { background: #f7f8fa; color: #1a1a1a; }
        QStatusBar QLabel { color: #1a1a1a; }
        QDockWidget { color: #1a1a1a; }
        QDockWidget::title { font-weight: bold; padding: 4px; background: #f0f2f5; color: #1a1a1a; }
        QListWidget { padding: 4px; background: #ffffff; color: #1a1a1a; }
        QListWidget::item:alternate { background: #f5f6f8; }
        QSpinBox { background: #ffffff; color: #1a1a1a; border: 1px solid #ccc; padding: 2px; }
        QLabel { color: #1a1a1a; }
        """)
