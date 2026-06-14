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
from app.handlers import (
    DialogHandlerMixin,
    EditHandlerMixin,
    FileHandlerMixin,
    StateUpdateMixin,
)
from app.i18n import load_translations, tr
from app.logger import get_logger, setup_logger
from app.ui_menu import MenuBuilder, ShortcutBuilder
from app.ui_statusbar import StatusBarManager
from app.ui_toolbar import ToolbarBuilder
from app.viewer import PDFViewer


class MainWindow(
    QMainWindow,
    FileHandlerMixin,
    EditHandlerMixin,
    DialogHandlerMixin,
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
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.viewer = PDFViewer(self)
        self.viewer.setBackgroundBrush(QColor(245, 245, 245))
        layout.addWidget(self.viewer)
        self.viewer.selection_made.connect(self.handle_selection_made)
        self.viewer.page_changed.connect(self._handle_page_changed)
        self.viewer.render_started.connect(lambda: self.statusBar().showMessage(tr("status.rendering")))
        self.viewer.render_finished.connect(lambda: self.statusBar().showMessage(tr("status.render_ready")))
        self.viewer.render_finished.connect(self._update_status_bar_page_info)

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

    # ------------------------------------------------------------------ docks
    def _setup_dock_widgets(self) -> None:
        # Operation History Dock
        self.history_dock = QDockWidget(tr("history_panel.title"), self)
        self.history_list_widget = QListWidget()
        self.history_list_widget.setAlternatingRowColors(True)
        self.history_dock.setWidget(self.history_list_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.history_dock)

        self.history_dock.setVisible(get_config_value(self.config, "ui", "history_panel_visible", default=True))
        # Keep toggle action (created later) in sync with dock visibility.
        self.history_dock.visibilityChanged.connect(
            lambda visible: hasattr(self, "toggle_history_action") and self.toggle_history_action.setChecked(visible)
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
        # Explicit text color alongside background to avoid white-on-white on
        # Windows dark mode (OS provides light foreground without our override).
        self.setStyleSheet(
            """
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
            """
        )
