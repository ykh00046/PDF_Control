"""Menu bar + keyboard shortcut construction for MainWindow.

``MenuBuilder.build()`` populates the menu bar and attaches the ``QAction``
instances (``undo_action``, ``zoom_in_action``, etc.) to the window so the
toolbar can reuse them.

``ShortcutBuilder.build()`` registers the global keyboard shortcuts that are
not bound to menu entries (Del, Ctrl+R, Page Up/Down, F1).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut

from app.i18n import tr

if TYPE_CHECKING:
    from app.ui import MainWindow


class MenuBuilder:
    """Builds the MainWindow menu bar."""

    def __init__(self, window: "MainWindow") -> None:
        self._win = window

    def build(self) -> None:
        self._build_file_menu()
        self._build_edit_menu()
        self._build_view_menu()
        self._build_tools_menu()
        self._build_help_menu()

    # --------------------------------------------------------------- File
    def _build_file_menu(self) -> None:
        win = self._win
        file_menu = win.menuBar().addMenu(tr("menu.file"))

        open_action = QAction(tr("menu.file.open"), win)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(win.open_file)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_as_action = QAction(tr("menu.file.save_as"), win)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(win.save_file_as)
        file_menu.addAction(save_as_action)

        save_encrypted_action = QAction(tr("menu.file.save_encrypted"), win)
        save_encrypted_action.setShortcut("Ctrl+Alt+S")
        save_encrypted_action.triggered.connect(win.save_file_encrypted)
        file_menu.addAction(save_encrypted_action)

        remove_protection_action = QAction(tr("menu.file.remove_protection"), win)
        remove_protection_action.setShortcut("Ctrl+Alt+D")
        remove_protection_action.triggered.connect(win.save_file_decrypted)
        file_menu.addAction(remove_protection_action)

        file_menu.addSeparator()

        exit_action = QAction(tr("menu.file.exit"), win)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(win.close)
        file_menu.addAction(exit_action)

    # --------------------------------------------------------------- Edit
    def _build_edit_menu(self) -> None:
        win = self._win
        edit_menu = win.menuBar().addMenu(tr("menu.edit"))

        win.undo_action = QAction(tr("menu.edit.undo"), win)
        win.undo_action.setShortcut("Ctrl+Z")
        win.undo_action.triggered.connect(win.undo_operation)
        edit_menu.addAction(win.undo_action)
        win.undo_action.setEnabled(False)

        win.redo_action = QAction(tr("menu.edit.redo"), win)
        win.redo_action.setShortcut("Ctrl+Y")
        win.redo_action.triggered.connect(win.redo_operation)
        edit_menu.addAction(win.redo_action)
        win.redo_action.setEnabled(False)

        edit_menu.addSeparator()

        select_font_action = QAction(tr("menu.edit.select_font"), win)
        select_font_action.triggered.connect(win.select_replacement_font)
        edit_menu.addAction(select_font_action)

    # --------------------------------------------------------------- View
    def _build_view_menu(self) -> None:
        win = self._win
        view_menu = win.menuBar().addMenu(tr("menu.view"))

        win.zoom_in_action = QAction(tr("menu.view.zoom_in"), win)
        win.zoom_in_action.setShortcut("Ctrl++")
        win.zoom_in_action.triggered.connect(win.viewer.zoom_in)
        view_menu.addAction(win.zoom_in_action)

        win.zoom_out_action = QAction(tr("menu.view.zoom_out"), win)
        win.zoom_out_action.setShortcut("Ctrl+-")
        win.zoom_out_action.triggered.connect(win.viewer.zoom_out)
        view_menu.addAction(win.zoom_out_action)

        win.fit_to_width_action = QAction(tr("menu.view.fit_to_width"), win)
        win.fit_to_width_action.setShortcut("Ctrl+0")
        win.fit_to_width_action.triggered.connect(win.viewer.fit_to_width)
        view_menu.addAction(win.fit_to_width_action)

        win.toggle_history_action = QAction(
            tr("menu.view.history_toggle"), win, checkable=True
        )
        win.toggle_history_action.setChecked(win.history_dock.isVisible())
        win.toggle_history_action.toggled.connect(win._toggle_history_panel)
        view_menu.addAction(win.toggle_history_action)

    # --------------------------------------------------------------- Tools
    def _build_tools_menu(self) -> None:
        win = self._win
        tools_menu = win.menuBar().addMenu(tr("menu.tools"))

        batch_replace_action = QAction(tr("menu.tools.batch_replace"), win)
        batch_replace_action.triggered.connect(win.open_batch_replace_dialog)
        tools_menu.addAction(batch_replace_action)

        crop_page_action = QAction(tr("menu.tools.crop_page"), win)
        crop_page_action.setShortcut("Ctrl+Shift+C")
        crop_page_action.triggered.connect(win.open_crop_dialog)
        tools_menu.addAction(crop_page_action)

        remove_section_action = QAction(tr("menu.tools.remove_section"), win)
        remove_section_action.setShortcut("Ctrl+Shift+X")
        remove_section_action.triggered.connect(win.open_remove_section_dialog)
        tools_menu.addAction(remove_section_action)

        watermark_action = QAction(tr("menu.tools.watermark"), win)
        watermark_action.setShortcut("Ctrl+Shift+W")
        watermark_action.triggered.connect(win.open_watermark_dialog)
        tools_menu.addAction(watermark_action)

        tools_menu.addSeparator()

        page_manager_action = QAction(tr("menu.tools.page_manager"), win)
        page_manager_action.setShortcut("Ctrl+Shift+P")
        page_manager_action.triggered.connect(win.open_page_manager_dialog)
        tools_menu.addAction(page_manager_action)

        tools_menu.addSeparator()

        export_text_action = QAction(tr("menu.tools.export_text"), win)
        export_text_action.setShortcut("Ctrl+Shift+T")
        export_text_action.triggered.connect(win.open_text_export_dialog)
        tools_menu.addAction(export_text_action)

    # --------------------------------------------------------------- Help
    def _build_help_menu(self) -> None:
        win = self._win
        help_menu = win.menuBar().addMenu(tr("menu.help"))

        view_logs_action = QAction(tr("menu.help.view_logs"), win)
        view_logs_action.triggered.connect(win.view_logs)
        help_menu.addAction(view_logs_action)


class ShortcutBuilder:
    """Registers the global keyboard shortcuts not bound to menu items."""

    def __init__(self, window: "MainWindow") -> None:
        self._win = window

    def build(self) -> None:
        win = self._win

        delete_shortcut = QShortcut(QKeySequence(Qt.Key_Delete), win)
        delete_shortcut.activated.connect(win.delete_selection)

        replace_shortcut = QShortcut(QKeySequence("Ctrl+R"), win)
        replace_shortcut.activated.connect(win.replace_selection)

        page_up_shortcut = QShortcut(QKeySequence(Qt.Key_PageUp), win)
        page_up_shortcut.activated.connect(win.viewer.prev_page)

        page_down_shortcut = QShortcut(QKeySequence(Qt.Key_PageDown), win)
        page_down_shortcut.activated.connect(win.viewer.next_page)

        help_shortcut = QShortcut(QKeySequence(Qt.Key_F1), win)
        help_shortcut.activated.connect(win.show_help)

        win.logger.info(
            "Keyboard shortcuts initialized: Del, Ctrl+R, PageUp/Down, F1"
        )
