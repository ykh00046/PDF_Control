"""Status bar construction and runtime updates for MainWindow.

Owns three persistent widgets (font info label, warning indicator button,
page info label) and the methods that refresh them in response to viewer
and controller signals.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMessageBox, QStyle, QToolButton

from app.i18n import tr

if TYPE_CHECKING:
    from app.ui import MainWindow


class StatusBarManager:
    """Builds and maintains the MainWindow status bar."""

    def __init__(self, window: "MainWindow") -> None:
        self._win = window
        self._font_info: QLabel | None = None
        self._warning_indicator: QToolButton | None = None
        self._page_info: QLabel | None = None

    # ------------------------------------------------------------------ build
    def build(self) -> None:
        win = self._win
        win.statusBar().showMessage(tr("status.ready"))

        # Current font indicator
        self._font_info = QLabel("")
        self._font_info.setStyleSheet("color: #555; margin-right: 10px;")
        win.statusBar().addPermanentWidget(self._font_info)
        self.update_font_info()

        # Text-fit warning indicator (hidden when no warnings)
        self._warning_indicator = QToolButton(win)
        self._warning_indicator.setAutoRaise(True)
        self._warning_indicator.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self._warning_indicator.setIcon(
            win.style().standardIcon(QStyle.SP_MessageBoxWarning)
        )
        self._warning_indicator.setVisible(False)
        self._warning_indicator.clicked.connect(self.show_warning_details)
        win.statusBar().addPermanentWidget(self._warning_indicator)

        self._page_info = QLabel("")
        win.statusBar().addPermanentWidget(self._page_info)
        self.update_page_info()

    # -------------------------------------------------------------- updates
    def refresh_warning_indicator(self) -> None:
        """Sync the warning widget with the session preview-warning cache."""
        if self._warning_indicator is None:
            return
        win = self._win
        session = win.controller.session if win.controller else None
        if session is None or not session.last_preview_warnings:
            self._warning_indicator.setVisible(False)
            return
        total = sum(
            1
            for ws in session.last_preview_warnings.values()
            for w in ws
            if w.get("severity") in ("warn", "error")
        )
        if total == 0:
            self._warning_indicator.setVisible(False)
            return
        has_error = session.has_blocking_warnings()
        icon_enum = (
            QStyle.SP_MessageBoxCritical
            if has_error
            else QStyle.SP_MessageBoxWarning
        )
        self._warning_indicator.setIcon(win.style().standardIcon(icon_enum))
        self._warning_indicator.setText(tr("warn.indicator.label", total))
        self._warning_indicator.setToolTip(tr("warn.indicator.tooltip"))
        self._warning_indicator.setVisible(True)

    def show_warning_details(self) -> None:
        """Modal listing of all cached preview warnings."""
        win = self._win
        session = win.controller.session if win.controller else None
        if session is None or not session.last_preview_warnings:
            return
        lines = []
        for page_idx, ws in sorted(session.last_preview_warnings.items()):
            for w in ws:
                code = w.get("code", "")
                detail = w.get("detail", {}) or {}
                if code == "text.shrunk":
                    lines.append(
                        tr(
                            "warn.code.text.shrunk",
                            page_idx + 1,
                            detail.get("fontsize_from", 0),
                            detail.get("fontsize_to", 0),
                        )
                    )
                elif code == "text.overflow":
                    lines.append(tr("warn.code.text.overflow", page_idx + 1))
                else:
                    lines.append(f"p{page_idx + 1}: {code}")
        QMessageBox.information(
            win,
            tr("warn.details.title"),
            "\n".join(lines) if lines else tr("warn.details.none"),
        )

    def update_page_info(self) -> None:
        if self._page_info is None:
            return
        win = self._win
        if win.controller.session and win.viewer.current_page_index != -1:
            page_num = win.viewer.current_page_index + 1
            total = win.controller.session.doc.page_count
            zoom_pct = int(win.viewer.zoom_level * 100)
            self._page_info.setText(
                tr("status.page_info", page_num, total, zoom_pct)
            )

            # Sync page spinbox (block signals to avoid recursion)
            win.page_spinbox.blockSignals(True)
            win.page_spinbox.setMaximum(total)
            win.page_spinbox.setValue(page_num)
            win.page_spinbox.blockSignals(False)
        else:
            self._page_info.setText("")
            win.page_spinbox.blockSignals(True)
            win.page_spinbox.setMinimum(1)
            win.page_spinbox.setMaximum(1)
            win.page_spinbox.setValue(1)
            win.page_spinbox.blockSignals(False)

    def update_font_info(self) -> None:
        """Update the font info label."""
        if self._font_info is None:
            return
        win = self._win
        if win.current_replacement_font_path:
            font_name = os.path.basename(win.current_replacement_font_path)
            self._font_info.setText(tr("status.current_font", font_name))
        else:
            self._font_info.setText(tr("status.font_default"))

    # -------------------------------------------------------------- helpers
    def hide_warning_indicator(self) -> None:
        if self._warning_indicator is not None:
            self._warning_indicator.setVisible(False)
