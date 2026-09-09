"""Layout / naming guards from the 2026-09-09 screen review.

Menu and toolbar must expose the same actions, every primary edit action must
be reachable from the menu bar (not only via shortcut), dialog button rows
follow the Windows order (primary first, Cancel last), and the page manager
keeps all of its actions visible at the default width.
"""

import os

import fitz
import pytest
from PySide6.QtWidgets import QPushButton, QToolBar

from app.ui import MainWindow


@pytest.fixture
def pdf(tmp_path):
    path = tmp_path / "layout.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((50, 80), "layout", fontsize=12)
    doc.new_page()
    doc.save(path)
    doc.close()
    return os.path.abspath(path)


@pytest.fixture
def window(qtbot, pdf):
    win = MainWindow()
    qtbot.addWidget(win)
    win.controller.load_document(pdf)
    return win


def test_edit_menu_exposes_selection_find_and_batch(window):
    actions = {a.text(): a for a in window.edit_menu.actions() if not a.isSeparator()}
    assert window.delete_action.text() in actions
    assert window.replace_action.text() in actions
    assert window.find_action.text() in actions
    assert window.batch_replace_action.text() in actions
    assert window.delete_action.shortcut().toString() == "Del"
    assert window.replace_action.shortcut().toString() == "Ctrl+R"
    assert window.batch_replace_action.shortcut().toString() == "Ctrl+H"


def test_help_menu_has_f1_entry(window):
    shortcuts = [a.shortcut().toString() for a in window.help_menu.actions() if not a.isSeparator()]
    assert "F1" in shortcuts


def test_toolbar_reuses_menu_actions_with_short_labels(window):
    toolbars = window.findChildren(QToolBar)
    edit_bar = toolbars[0]
    acts = edit_bar.actions()
    for action in (
        window.open_action,
        window.save_action,
        window.delete_action,
        window.replace_action,
        window.find_action,
    ):
        assert action in acts
        # Toolbar label is the short icon text, never the mnemonic menu text.
        assert action.iconText() and "&" not in action.iconText()
        assert action.iconText() != action.text().replace("&", "")


def test_page_spinbox_shows_total(window):
    assert window.page_spinbox.suffix() == " / 2"
    window.controller.close_document()
    assert window.page_spinbox.suffix() == ""


def test_dialog_button_rows_primary_first(window, tmp_path):
    """Every dialog ends with [primary][Cancel] (Windows order)."""
    from app.crop_dialog import CropPreviewDialog
    from app.encryption_dialog import EncryptionDialog
    from app.image_watermark_dialog import ImageWatermarkDialog
    from app.remove_section_dialog import RemoveSectionDialog
    from app.split_dialog import SplitDialog
    from app.text_export_dialog import TextExportDialog
    from app.watermark_dialog import WatermarkDialog

    page = window.controller.session.doc[0]
    rect = fitz.Rect(50, 80, 400, 300)
    dialogs = [
        CropPreviewDialog(page, rect, window),
        RemoveSectionDialog(page, rect, window),
        WatermarkDialog(window),
        ImageWatermarkDialog(window),
        SplitDialog(2, window),
        TextExportDialog(window),
        EncryptionDialog(window),
    ]
    for dialog in dialogs:
        buttons = [b.text() for b in dialog.findChildren(QPushButton)]
        assert buttons[-1] == "취소" or buttons[-1].lower() == "cancel", (type(dialog).__name__, buttons)
        assert buttons[-2] not in ("취소", "Cancel"), (type(dialog).__name__, buttons)


def test_crop_dialog_opens(window):
    """Regression: QPen.Antialiasing raised AttributeError on open."""
    from app.crop_dialog import CropPreviewDialog

    dialog = CropPreviewDialog(window.controller.session.doc[0], fitz.Rect(50, 80, 400, 300), window)
    assert dialog is not None


def test_page_manager_uses_two_toolbars(window):
    from app.page_manager_dialog import PageManagerDialog

    dialog = PageManagerDialog(window.controller, window)
    bars = dialog.findChildren(QToolBar)
    assert len(bars) == 2
    visible_actions = [a for bar in bars for a in bar.actions() if not a.isSeparator()]
    for action in (dialog.duplicate_action, dialog.extract_action, dialog.merge_action, dialog.split_action):
        assert action in visible_actions
    # Short labels: the tooltip carries the detail.
    assert dialog.undo_action.text() != dialog.undo_action.toolTip()


def test_thumbnail_sidebar_single_column(window):
    panel = window.thumbnail_panel
    assert panel.gridSize().width() > 0
    assert not panel.isWrapping()
    assert panel.flow() == panel.Flow.TopToBottom
