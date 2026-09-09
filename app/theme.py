"""Design tokens + stylesheet builder (the app's design system).

Reference (design-system-first, per the "don't start with the prompt"
workflow): the app runs on Windows, so the visual baseline is Windows 11
Fluent -- layered neutral surfaces, one accent color, 4px control radius,
an 8px spacing grid, thin 1px borders and quiet hover states. Every color,
size and spacing used by the UI is a named token here; widgets never carry
ad-hoc hex values.

The app forces a light theme (see ``build_stylesheet``): under Windows dark
mode the OS supplies a dark palette, so each popup surface (QMenu,
QMessageBox, QDialog, QComboBox drop-down, QToolTip) must pin its light
background or the dark text disappears (dark-mode-ui-fix, 2026-07-21).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Tuple

StatusKind = Literal["muted", "info", "success", "warning", "error"]


@dataclass(frozen=True)
class Theme:
    """Named tokens for one theme variant."""

    # Surfaces (window -> layer -> card), lightest last
    bg_app: str = "#f3f3f3"
    bg_layer: str = "#fafafa"
    bg_surface: str = "#ffffff"
    bg_hover: str = "#eaeaea"
    bg_pressed: str = "#e0e0e0"
    bg_alt_row: str = "#f6f6f6"

    # Strokes
    border: str = "#e0e0e0"
    border_strong: str = "#c6c6c6"

    # Text -- #1a1a1a is part of the dark-mode contract guarded by tests
    text: str = "#1a1a1a"
    text_muted: str = "#5f6368"
    text_disabled: str = "#9d9d9d"

    # Accent (Windows 11 default blue)
    accent: str = "#0067c0"
    accent_hover: str = "#1975d1"
    accent_pressed: str = "#005a9e"
    accent_text: str = "#ffffff"
    accent_soft: str = "#e6f0fa"

    # Semantic status colors (text on the light surface)
    info: str = "#0067c0"
    success: str = "#0f7b0f"
    warning: str = "#9d5d00"
    warning_bg: str = "#fff4ce"
    warning_border: str = "#f2c94c"
    error: str = "#c42b1c"

    # Typography
    font_family: str = '"Segoe UI", "Malgun Gothic", "Apple SD Gothic Neo", sans-serif'
    font_size_pt: int = 10  # WinUI body text is 14px (~10.5pt); 9pt read as "legacy"
    font_size_small_pt: int = 9
    font_size_title_pt: int = 16

    # Geometry (px)
    radius: int = 4
    radius_panel: int = 6
    space_xs: int = 4
    space_sm: int = 8
    space_md: int = 12
    space_lg: int = 16
    control_height: int = 28

    # Viewer overlays: (r, g, b) + alpha for the drag selection and search hits
    selection_rgb: Tuple[int, int, int] = (0, 103, 192)
    selection_fill_alpha: int = 40
    highlight_rgb: Tuple[int, int, int] = (255, 214, 10)
    highlight_fill_alpha: int = 80
    highlight_current_rgb: Tuple[int, int, int] = (255, 140, 0)
    highlight_current_fill_alpha: int = 110


LIGHT_THEME = Theme()


def label_style(theme: Theme, kind: StatusKind, *, emphasis: bool = False) -> str:
    """Inline stylesheet for a status/info QLabel of the given semantic kind."""
    color = {
        "muted": theme.text_muted,
        "info": theme.info,
        "success": theme.success,
        "warning": theme.warning,
        "error": theme.error,
    }[kind]
    weight = "font-weight: 600;" if emphasis else ""
    return f"color: {color}; {weight}"


def callout_style(theme: Theme, kind: Literal["neutral", "warning"]) -> str:
    """Inline stylesheet for a boxed, word-wrapped message label."""
    if kind == "warning":
        return (
            f"background-color: {theme.warning_bg}; color: {theme.warning}; "
            f"border: 1px solid {theme.warning_border}; border-radius: {theme.radius}px; "
            f"padding: {theme.space_sm}px {theme.space_md}px;"
        )
    return (
        f"background-color: {theme.bg_layer}; color: {theme.text}; "
        f"border: 1px solid {theme.border}; border-radius: {theme.radius}px; "
        f"padding: {theme.space_sm}px {theme.space_md}px;"
    )


def invalid_field_style(theme: Theme) -> str:
    """Inline stylesheet marking an input as invalid."""
    return f"border: 1px solid {theme.error};"


def build_stylesheet(theme: Theme = LIGHT_THEME) -> str:
    """Render the application-wide QSS from tokens.

    Keep the rule shapes stable: ``tests/test_ui_styles.py`` asserts the
    presence of ``QMenu::item { padding:`` and the light-background popup
    surfaces.
    """
    t = theme
    input_common = (
        f"background: {t.bg_surface}; color: {t.text}; border: 1px solid {t.border_strong}; "
        f"border-radius: {t.radius}px; padding: {t.space_xs}px {t.space_sm}px; "
        f"min-height: {t.control_height - 2 * t.space_xs - 2}px;"
    )
    return f"""
        * {{ font-family: {t.font_family}; font-size: {t.font_size_pt}pt; }}
        QMainWindow {{ background: {t.bg_app}; color: {t.text}; }}
        QWidget#centralWidget {{ background: {t.bg_app}; }}
        QDialog {{ background: {t.bg_app}; color: {t.text}; }}

        QMenuBar {{ background: {t.bg_app}; color: {t.text}; padding: 2px {t.space_xs}px; }}
        QMenuBar::item {{ padding: {t.space_xs}px {t.space_sm}px; border-radius: {t.radius}px; }}
        QMenuBar::item:selected {{ background: {t.bg_hover}; }}
        QMenu {{
            background: {t.bg_surface}; color: {t.text};
            border: 1px solid {t.border}; border-radius: {t.radius_panel}px; padding: {t.space_xs}px;
        }}
        QMenu::item {{ padding: 6px 28px 6px 24px; border-radius: {t.radius}px; }}
        QMenu::item:selected {{ background: {t.accent}; color: {t.accent_text}; }}
        QMenu::item:disabled {{ color: {t.text_disabled}; }}
        QMenu::separator {{ height: 1px; background: {t.border}; margin: {t.space_xs}px {t.space_sm}px; }}

        QToolBar {{
            spacing: 2px; padding: {t.space_xs}px {t.space_sm}px;
            background: {t.bg_surface}; border: none; border-bottom: 1px solid {t.border}; color: {t.text};
        }}
        QToolBar::separator {{ width: 1px; background: {t.border}; margin: {t.space_sm}px {t.space_xs}px; }}
        QToolBar QToolButton {{
            color: {t.text}; background: transparent; border: 1px solid transparent;
            border-radius: {t.radius_panel}px; padding: {t.space_xs}px {t.space_sm}px;
            font-size: {t.font_size_small_pt}pt; min-width: 44px;
        }}
        QToolBar QToolButton:hover {{ background: {t.bg_hover}; }}
        QToolBar QToolButton:pressed {{ background: {t.bg_pressed}; }}
        QToolBar QToolButton:disabled {{ color: {t.text_disabled}; }}
        QToolBar QSpinBox {{ min-height: 24px; }}

        QStatusBar {{ background: {t.bg_layer}; color: {t.text_muted}; border-top: 1px solid {t.border}; }}
        QStatusBar QLabel {{ color: {t.text_muted}; padding: 0 {t.space_sm}px; }}
        QStatusBar QToolButton {{ color: {t.warning}; background: transparent; border: none; }}
        QStatusBar::item {{ border: none; }}

        QDockWidget {{ color: {t.text}; }}
        QWidget#dockTitle {{ background: {t.bg_layer}; border-bottom: 1px solid {t.border}; }}
        QLabel#dockTitleLabel {{ color: {t.text_muted}; font-weight: 600; font-size: {t.font_size_small_pt}pt; }}
        QToolButton#dockClose {{ border: none; padding: 2px; border-radius: {t.radius}px; }}
        QToolButton#dockClose:hover {{ background: {t.bg_hover}; }}

        QWidget#emptyState {{ background: {t.bg_app}; }}
        QWidget#emptyStateCard {{
            background: {t.bg_surface}; border: 1px solid {t.border}; border-radius: 12px;
        }}
        QLabel#emptyStateTitle {{ font-size: {t.font_size_title_pt}pt; font-weight: 600; color: {t.text}; }}
        QLabel#emptyStateHint {{ color: {t.text_muted}; }}
        QListWidget {{
            padding: {t.space_xs}px; background: {t.bg_surface}; color: {t.text};
            border: 1px solid {t.border}; border-radius: {t.radius}px; outline: none;
        }}
        QListWidget::item {{ padding: {t.space_xs}px; border-radius: {t.radius}px; }}
        QListWidget::item:alternate {{ background: {t.bg_alt_row}; }}
        QListWidget::item:hover {{ background: {t.bg_hover}; }}
        QListWidget::item:selected {{ background: {t.accent_soft}; color: {t.text}; border: 1px solid {t.accent}; }}
        QTableWidget {{
            background: {t.bg_surface}; color: {t.text}; gridline-color: {t.border}; border: 1px solid {t.border};
        }}
        QHeaderView::section {{
            background: {t.bg_layer}; color: {t.text_muted}; padding: {t.space_xs}px {t.space_sm}px;
            border: none; border-bottom: 1px solid {t.border}; font-weight: 600;
        }}

        QLabel {{ color: {t.text}; }}
        QMessageBox {{ background: {t.bg_app}; }}
        QMessageBox QLabel {{ color: {t.text}; }}
        QGroupBox {{
            color: {t.text}; border: 1px solid {t.border}; border-radius: {t.radius_panel}px;
            margin-top: {t.space_lg}px; padding: {t.space_md}px {t.space_xs}px {t.space_xs}px {t.space_xs}px;
            font-weight: 600;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin; subcontrol-position: top left;
            left: {t.space_sm}px; top: 0; padding: 0 {t.space_xs}px; background: {t.bg_app};
        }}

        QLineEdit, QTextEdit, QPlainTextEdit {{ {input_common} }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{ border: 1px solid {t.accent}; }}
        QLineEdit:disabled {{ color: {t.text_disabled}; background: {t.bg_layer}; }}
        QSpinBox, QDoubleSpinBox {{
            background: {t.bg_surface}; color: {t.text}; border: 1px solid {t.border_strong};
            border-radius: {t.radius}px; padding: 2px {t.space_xs}px;
        }}
        QSpinBox:focus, QDoubleSpinBox:focus {{ border: 1px solid {t.accent}; }}
        QComboBox {{ {input_common} }}
        QComboBox:focus {{ border: 1px solid {t.accent}; }}
        QComboBox QAbstractItemView {{
            background: {t.bg_surface}; color: {t.text}; border: 1px solid {t.border};
            selection-background-color: {t.accent}; selection-color: {t.accent_text};
            outline: none;
        }}
        QCheckBox {{ color: {t.text}; spacing: {t.space_sm}px; }}
        QRadioButton {{ color: {t.text}; spacing: {t.space_sm}px; }}
        QSlider::groove:horizontal {{ height: 4px; background: {t.border_strong}; border-radius: 2px; }}
        QSlider::handle:horizontal {{
            width: 16px; margin: -6px 0; background: {t.accent}; border-radius: 8px;
        }}
        QSlider::sub-page:horizontal {{ background: {t.accent}; border-radius: 2px; }}

        QPushButton {{
            background: {t.bg_surface}; color: {t.text}; border: 1px solid {t.border_strong};
            padding: {t.space_xs}px {t.space_lg}px; border-radius: {t.radius}px;
            min-height: {t.control_height - 2 * t.space_xs - 2}px;
        }}
        QPushButton:hover {{ background: {t.bg_hover}; }}
        QPushButton:pressed {{ background: {t.bg_pressed}; }}
        QPushButton:default {{ background: {t.accent}; color: {t.accent_text}; border-color: {t.accent}; }}
        QPushButton:default:hover {{ background: {t.accent_hover}; }}
        QPushButton:default:pressed {{ background: {t.accent_pressed}; }}
        QPushButton:disabled {{ color: {t.text_disabled}; background: {t.bg_layer}; border-color: {t.border}; }}

        QToolButton {{
            color: {t.text}; border: 1px solid transparent; border-radius: {t.radius}px; padding: {t.space_xs}px;
        }}
        QToolButton:hover {{ background: {t.bg_hover}; border-color: {t.border}; }}
        QToolButton:pressed {{ background: {t.bg_pressed}; }}
        QToolButton:disabled {{ color: {t.text_disabled}; }}

        QWidget#findBar {{ background: {t.bg_layer}; border-top: 1px solid {t.border}; }}

        QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
        QScrollBar::handle:vertical {{ background: {t.border_strong}; border-radius: 4px; min-height: 24px; }}
        QScrollBar::handle:vertical:hover {{ background: {t.text_disabled}; }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
        QScrollBar::handle:horizontal {{ background: {t.border_strong}; border-radius: 4px; min-width: 24px; }}
        QScrollBar::handle:horizontal:hover {{ background: {t.text_disabled}; }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

        QToolTip {{
            background: {t.bg_surface}; color: {t.text}; border: 1px solid {t.border};
            padding: {t.space_xs}px {t.space_sm}px; border-radius: {t.radius}px;
        }}
        QProgressBar {{
            border: 1px solid {t.border}; border-radius: {t.radius}px; background: {t.bg_surface}; text-align: center;
        }}
        QProgressBar::chunk {{ background: {t.accent}; border-radius: {t.radius}px; }}
    """
