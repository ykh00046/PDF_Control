"""MainWindow — orchestrator for the PDF Control desktop app.

The window itself owns only:

* infrastructure setup (logger, config, i18n, controller, viewer)
* dock widget layout
* the global stylesheet

Menu, toolbar, status bar, keyboard shortcuts, and all event handler logic
live in dedicated modules:

* :mod:`app.ui_menu` — :class:`MenuBuilder`, :class:`ShortcutBuilder`
* :mod:`app.ui_toolbar` — :class:`ToolbarBuilder`
* :mod:`app.ui_statusbar` — :class:`StatusBarManager`
* :mod:`app.handlers` — handler mixins inherited by MainWindow below
"""

from __future__ import annotations

from typing import Optional

import fitz
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDockWidget,
    QInputDialog,  # noqa: F401  re-exported for tests that patch ``app.ui.QInputDialog``
    QListWidget,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from app.config import get_config_value, load_config
from app.controller import EditorController
from app.find_bar import FindBar
from app.handlers import (
    DialogHandlerMixin,
    EditHandlerMixin,
    FileHandlerMixin,
    SearchHandlerMixin,
    StateUpdateMixin,
)
from app.i18n import load_translations, tr
from app.logger import get_logger, setup_logger
from app.theme import LIGHT_THEME, build_stylesheet
from app.thumbnail_panel import ThumbnailSidebar
from app.ui_menu import MenuBuilder, ShortcutBuilder
from app.ui_statusbar import StatusBarManager
from app.ui_toolbar import ToolbarBuilder
from app.ui_widgets import EmptyState, apply_dock_chrome
from app.viewer import PDFViewer


class MainWindow(
    QMainWindow,
    FileHandlerMixin,
    EditHandlerMixin,
    DialogHandlerMixin,
    SearchHandlerMixin,
    StateUpdateMixin,
):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()

        # --- Infrastructure ------------------------------------------------
        setup_logger()
        self.logger = get_logger()
        self.logger.info("MainWindow initialized")

        self.config = load_config()
        self.logger.info("Configuration loaded")

        load_translations()
        self.logger.info("Translations loaded")

        self.setWindowTitle(tr("app.title"))

        window_x = get_config_value(self.config, "window", "x", default=100)
        window_y = get_config_value(self.config, "window", "y", default=100)
        window_width = get_config_value(self.config, "window", "width", default=1200)
        window_height = get_config_value(self.config, "window", "height", default=800)
        self.setGeometry(window_x, window_y, window_width, window_height)

        # --- Controller ----------------------------------------------------
        self.controller = EditorController()
        self.controller.document_loaded.connect(self.on_document_loaded)
        self.controller.document_closed.connect(self.on_document_closed)
        self.controller.history_changed.connect(self._update_history_panel)
        self.controller.history_changed.connect(self._update_edit_action_states)
        self.controller.operation_applied.connect(self.on_operation_applied)
        self.controller.error_occurred.connect(self.on_error_occurred)

        self.last_selected_rect: Optional[fitz.Rect] = None
        self.last_directory: str = get_config_value(self.config, "last_directory", default="")
        self.current_replacement_font_path: Optional[str] = None

        # --- Central viewer ------------------------------------------------
        central_widget = QWidget(self)
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.viewer = PDFViewer(self)
        self.viewer.setBackgroundBrush(QColor(LIGHT_THEME.bg_app))
        self.viewer.setFrameShape(PDFViewer.Shape.NoFrame)
        layout.addWidget(self.viewer)

        # Empty state replaces the blank canvas until a document is open.
        self.empty_state = EmptyState(self)
        self.empty_state.open_requested.connect(self.open_file)
        layout.addWidget(self.empty_state)
        self.viewer.hide()
        self.controller.document_loaded.connect(lambda _path: self._show_canvas(True))
        self.controller.document_closed.connect(lambda: self._show_canvas(False))
        self.viewer.selection_made.connect(self.handle_selection_made)
        self.viewer.page_changed.connect(self._handle_page_changed)
        self.viewer.render_started.connect(lambda: self.statusBar().showMessage(tr("status.rendering")))
        self.viewer.render_finished.connect(lambda: self.statusBar().showMessage(tr("status.render_ready")))
        self.viewer.render_finished.connect(self._update_status_bar_page_info)

        # --- Find bar (hidden until Ctrl+F) --------------------------------
        self._search_hits = []
        self._search_current = -1
        self.find_bar = FindBar(self)
        self.find_bar.hide()
        layout.addWidget(self.find_bar)
        self.find_bar.search_requested.connect(self._on_find_query)
        self.find_bar.next_requested.connect(self.find_next)
        self.find_bar.prev_requested.connect(self.find_prev)
        self.find_bar.closed.connect(self._on_find_bar_closed)
        self.viewer.page_changed.connect(self._apply_search_highlights)
        self.controller.document_loaded.connect(self._reset_search)
        self.controller.document_closed.connect(self._reset_search)

        # --- UI assembly ---------------------------------------------------
        self._setup_dock_widgets()

        # StatusBarManager must exist before MenuBuilder (View menu reads
        # history_dock visibility) and before ToolbarBuilder (which calls
        # _update_status_bar_page_info via _update_edit_action_states).
        self.statusbar_manager = StatusBarManager(self)

        MenuBuilder(self).build()
        ToolbarBuilder(self).build()
        self.statusbar_manager.build()
        ShortcutBuilder(self).build()

        self._apply_styles()
        self.setAcceptDrops(True)

    def _show_canvas(self, has_document: bool) -> None:
        """Swap between the viewer and the empty-state placeholder."""
        self.viewer.setVisible(has_document)
        self.empty_state.setVisible(not has_document)

    # ------------------------------------------------------------------ docks
    def _setup_dock_widgets(self) -> None:
        # Operation History Dock
        self.history_dock = QDockWidget(tr("history_panel.title"), self)
        apply_dock_chrome(self.history_dock, tr("history_panel.title"))
        self.history_list_widget = QListWidget()
        self.history_list_widget.setAlternatingRowColors(True)
        self.history_list_widget.setFrameShape(QListWidget.Shape.NoFrame)
        self.history_dock.setWidget(self.history_list_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.history_dock)

        self.history_dock.setVisible(get_config_value(self.config, "ui", "history_panel_visible", default=True))
        # Keep toggle action (created later) in sync with dock visibility.
        self.history_dock.visibilityChanged.connect(
            lambda visible: hasattr(self, "toggle_history_action") and self.toggle_history_action.setChecked(visible)
        )

        # Page Thumbnail Sidebar
        self.thumbnail_dock = QDockWidget(tr("thumbnail_panel.title"), self)
        apply_dock_chrome(self.thumbnail_dock, tr("thumbnail_panel.title"))
        self.thumbnail_panel = ThumbnailSidebar()
        self.thumbnail_panel.setFrameShape(ThumbnailSidebar.Shape.NoFrame)
        self.thumbnail_dock.setWidget(self.thumbnail_panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.thumbnail_dock)
        self.thumbnail_panel.page_selected.connect(self._go_to_page)

        self.thumbnail_dock.setVisible(get_config_value(self.config, "ui", "thumbnail_panel_visible", default=True))
        self.thumbnail_dock.visibilityChanged.connect(
            lambda visible: hasattr(self, "toggle_thumbnails_action")
            and self.toggle_thumbnails_action.setChecked(visible)
        )

    # --------------------------------------------------- Qt event overrides
    # ``closeEvent`` / ``dragEnterEvent`` / ``dropEvent`` exist on
    # ``QMainWindow`` already, so Python MRO would resolve to the Qt defaults
    # over the mixin overrides. Explicit delegation forces our handlers.
    def closeEvent(self, event) -> None:
        FileHandlerMixin.closeEvent(self, event)

    def dragEnterEvent(self, event) -> None:
        FileHandlerMixin.dragEnterEvent(self, event)

    def dropEvent(self, event) -> None:
        FileHandlerMixin.dropEvent(self, event)

    # --------------------------------------------------------- statusbar shims
    # Thin delegates preserved on MainWindow so that ``connect(self.method)``
    # bookkeeping and the legacy private-method API remain stable.
    def _refresh_warning_indicator(self) -> None:
        self.statusbar_manager.refresh_warning_indicator()

    def _show_warning_details(self) -> None:
        self.statusbar_manager.show_warning_details()

    def _update_status_bar_page_info(self) -> None:
        self.statusbar_manager.update_page_info()

    def _update_status_bar_font_info(self) -> None:
        self.statusbar_manager.update_font_info()

    # --------------------------------------------------------------- styles
    def _apply_styles(self) -> None:
        # Single source of truth for colors/spacing/typography: app/theme.py.
        # The app forces a light theme; every popup surface pins a light
        # background so dark text survives Windows dark mode (see theme.py).
        self.setStyleSheet(build_stylesheet(LIGHT_THEME))
