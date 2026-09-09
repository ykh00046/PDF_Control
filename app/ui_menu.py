"""Menu bar + keyboard shortcut construction for MainWindow.

``MenuBuilder.build()`` populates the menu bar and attaches the ``QAction``
instances (``undo_action``, ``delete_action``, ``zoom_in_action``, etc.) to
the window so the toolbar can reuse them -- menu and toolbar therefore
always show the same label, tooltip, shortcut and enabled state.

Menu layout (reviewed 2026-09-09):

* File  -- open / recent / close | save / save as / encrypt / decrypt | exit
* Edit  -- undo / redo | delete / replace selection | find / next / prev /
           batch find-replace | replacement font
* View  -- zoom | panels
* Tools -- page crop / section removal | text & image watermark |
           page manager | text export
* Help  -- shortcuts & usage (F1) | view logs

``ShortcutBuilder.build()`` registers the global keys that have no menu
entry (Page Up/Down page navigation).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut

from app.i18n import tr
from app.icons import icon

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
        self._apply_icons()

    def _apply_icons(self) -> None:
        """Attach theme-tinted line icons to the actions toolbars reuse."""
        win = self._win
        for action, name in (
            (win.open_action, "open"),
            (win.save_action, "save"),
            (win.close_action, "close"),
            (win.undo_action, "undo"),
            (win.redo_action, "redo"),
            (win.delete_action, "delete"),
            (win.replace_action, "replace"),
            (win.find_action, "find"),
            (win.batch_replace_action, "batch"),
            (win.zoom_in_action, "zoom-in"),
            (win.zoom_out_action, "zoom-out"),
            (win.fit_to_width_action, "fit-width"),
            (win.toggle_thumbnails_action, "pages"),
            (win.toggle_history_action, "history"),
        ):
            action.setIcon(icon(name))

    @staticmethod
    def _action(
        win: "MainWindow",
        key: str,
        slot,
        shortcut: str | None = None,
        tooltip_key: str | None = None,
        icon_text_key: str | None = None,
    ):
        """Create a QAction with i18n label (+ optional shortcut / tooltip).

        ``icon_text_key`` gives the short label toolbars display; without it
        a toolbar would show the menu text including its mnemonic ("저장(S)").
        """
        action = QAction(tr(key), win)
        if shortcut:
            action.setShortcut(shortcut)
        if tooltip_key:
            action.setToolTip(tr(tooltip_key))
            action.setStatusTip(tr(tooltip_key))
        if icon_text_key:
            action.setIconText(tr(icon_text_key))
        action.triggered.connect(slot)
        return action

    # --------------------------------------------------------------- File
    def _build_file_menu(self) -> None:
        win = self._win
        file_menu = win.file_menu = win.menuBar().addMenu(tr("menu.file"))

        win.open_action = self._action(
            win, "menu.file.open", win.open_file, "Ctrl+O", "toolbar.open.tooltip", "toolbar.open"
        )
        file_menu.addAction(win.open_action)

        # "Open Recent" is rebuilt every time it is shown so it always
        # reflects the persisted list (no stale entries after Save As).
        win.recent_menu = file_menu.addMenu(tr("menu.file.open_recent"))
        win.recent_menu.aboutToShow.connect(win._populate_recent_menu)
        win._populate_recent_menu()

        win.close_action = self._action(win, "menu.file.close", win.close_file, "Ctrl+W")
        file_menu.addAction(win.close_action)

        file_menu.addSeparator()

        win.save_action = self._action(
            win, "menu.file.save", win.save_file, "Ctrl+S", "toolbar.save.tooltip", "toolbar.save"
        )
        file_menu.addAction(win.save_action)
        file_menu.addAction(self._action(win, "menu.file.save_as", win.save_file_as, "Ctrl+Shift+S"))
        file_menu.addAction(self._action(win, "menu.file.save_encrypted", win.save_file_encrypted, "Ctrl+Alt+S"))
        file_menu.addAction(self._action(win, "menu.file.remove_protection", win.save_file_decrypted, "Ctrl+Alt+D"))

        file_menu.addSeparator()
        file_menu.addAction(self._action(win, "menu.file.exit", win.close, "Ctrl+Q"))

    # --------------------------------------------------------------- Edit
    def _build_edit_menu(self) -> None:
        win = self._win
        edit_menu = win.edit_menu = win.menuBar().addMenu(tr("menu.edit"))

        win.undo_action = self._action(win, "menu.edit.undo", win.undo_operation, "Ctrl+Z")
        win.undo_action.setEnabled(False)
        edit_menu.addAction(win.undo_action)

        win.redo_action = self._action(win, "menu.edit.redo", win.redo_operation, "Ctrl+Y")
        win.redo_action.setEnabled(False)
        edit_menu.addAction(win.redo_action)

        edit_menu.addSeparator()

        # Selection actions: shared with the toolbar (same QAction objects).
        win.delete_action = self._action(
            win,
            "menu.edit.delete_selection",
            win.delete_selection,
            "Delete",
            "toolbar.delete.tooltip",
            "toolbar.delete",
        )
        edit_menu.addAction(win.delete_action)
        win.replace_action = self._action(
            win,
            "menu.edit.replace_selection",
            win.replace_selection,
            "Ctrl+R",
            "toolbar.replace.tooltip",
            "toolbar.replace",
        )
        edit_menu.addAction(win.replace_action)

        edit_menu.addSeparator()

        win.find_action = self._action(
            win, "menu.edit.find", win.show_find_bar, "Ctrl+F", "toolbar.find.tooltip", "toolbar.find"
        )
        edit_menu.addAction(win.find_action)
        edit_menu.addAction(self._action(win, "menu.edit.find_next", win.find_next, "F3"))
        edit_menu.addAction(self._action(win, "menu.edit.find_prev", win.find_prev, "Shift+F3"))
        win.batch_replace_action = self._action(win, "menu.edit.batch_replace", win.open_batch_replace_dialog, "Ctrl+H")
        edit_menu.addAction(win.batch_replace_action)

        edit_menu.addSeparator()
        edit_menu.addAction(self._action(win, "menu.edit.select_font", win.select_replacement_font))

    # --------------------------------------------------------------- View
    def _build_view_menu(self) -> None:
        win = self._win
        view_menu = win.view_menu = win.menuBar().addMenu(tr("menu.view"))

        win.zoom_in_action = self._action(win, "menu.view.zoom_in", win.viewer.zoom_in, "Ctrl++")
        view_menu.addAction(win.zoom_in_action)
        win.zoom_out_action = self._action(win, "menu.view.zoom_out", win.viewer.zoom_out, "Ctrl+-")
        view_menu.addAction(win.zoom_out_action)
        win.fit_to_width_action = self._action(win, "menu.view.fit_to_width", win.viewer.fit_to_width, "Ctrl+0")
        view_menu.addAction(win.fit_to_width_action)

        view_menu.addSeparator()

        win.toggle_thumbnails_action = QAction(tr("menu.view.thumbnails_toggle"), win, checkable=True)
        win.toggle_thumbnails_action.setChecked(win.thumbnail_dock.isVisible())
        win.toggle_thumbnails_action.toggled.connect(win._toggle_thumbnail_panel)
        view_menu.addAction(win.toggle_thumbnails_action)

        win.toggle_history_action = QAction(tr("menu.view.history_toggle"), win, checkable=True)
        win.toggle_history_action.setChecked(win.history_dock.isVisible())
        win.toggle_history_action.toggled.connect(win._toggle_history_panel)
        view_menu.addAction(win.toggle_history_action)

    # --------------------------------------------------------------- Tools
    def _build_tools_menu(self) -> None:
        win = self._win
        tools_menu = win.tools_menu = win.menuBar().addMenu(tr("menu.tools"))

        tools_menu.addAction(self._action(win, "menu.tools.crop_page", win.open_crop_dialog, "Ctrl+Shift+C"))
        tools_menu.addAction(
            self._action(win, "menu.tools.remove_section", win.open_remove_section_dialog, "Ctrl+Shift+X")
        )

        tools_menu.addSeparator()
        tools_menu.addAction(self._action(win, "menu.tools.watermark", win.open_watermark_dialog, "Ctrl+Shift+W"))
        tools_menu.addAction(
            self._action(win, "menu.tools.image_watermark", win.open_image_watermark_dialog, "Ctrl+Shift+I")
        )

        tools_menu.addSeparator()
        tools_menu.addAction(self._action(win, "menu.tools.page_manager", win.open_page_manager_dialog, "Ctrl+Shift+P"))

        tools_menu.addSeparator()
        tools_menu.addAction(self._action(win, "menu.tools.export_text", win.open_text_export_dialog, "Ctrl+Shift+T"))

    # --------------------------------------------------------------- Help
    def _build_help_menu(self) -> None:
        win = self._win
        help_menu = win.help_menu = win.menuBar().addMenu(tr("menu.help"))
        help_menu.addAction(self._action(win, "menu.help.shortcuts", win.show_help, "F1"))
        help_menu.addSeparator()
        help_menu.addAction(self._action(win, "menu.help.view_logs", win.view_logs))


class ShortcutBuilder:
    """Registers the global keyboard shortcuts not bound to menu items."""

    def __init__(self, window: "MainWindow") -> None:
        self._win = window

    def build(self) -> None:
        win = self._win

        page_up_shortcut = QShortcut(QKeySequence(Qt.Key_PageUp), win)
        page_up_shortcut.activated.connect(win.viewer.prev_page)

        page_down_shortcut = QShortcut(QKeySequence(Qt.Key_PageDown), win)
        page_down_shortcut.activated.connect(win.viewer.next_page)

        win.logger.info("Keyboard shortcuts initialized: PageUp/Down (menu actions carry the rest)")
