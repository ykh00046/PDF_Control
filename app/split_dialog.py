"""Split dialog for :class:`app.page_manager_dialog.PageManagerDialog`.

Collects how the document should be divided (single pages / every N pages /
custom ranges) and where to write the output files. The dialog only gathers
settings — group computation and file writing are handled by the caller via
:func:`app.page_split.compute_split_groups` and ``controller.split_document``,
mirroring the crop / text-export dialog convention.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.page_split import SplitMode


class SplitDialog(QDialog):
    """Collects split options (mode + parameters + output directory)."""

    def __init__(self, page_count: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._page_count = max(1, page_count)
        self.setWindowTitle(tr("split.title"))
        self.setMinimumWidth(420)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        # --- Mode selection ---
        self.mode_single = QRadioButton(tr("split.mode.single"))
        self.mode_every_n = QRadioButton(tr("split.mode.every_n"))
        self.mode_ranges = QRadioButton(tr("split.mode.ranges"))
        self.mode_single.setChecked(True)
        self._mode_group = QButtonGroup(self)
        for button in (self.mode_single, self.mode_every_n, self.mode_ranges):
            self._mode_group.addButton(button)

        # every_n spin box (enabled only with that mode)
        self.every_n_spin = QSpinBox()
        self.every_n_spin.setRange(1, self._page_count)
        self.every_n_spin.setValue(1)
        self.every_n_spin.setEnabled(False)
        self.mode_every_n.toggled.connect(self.every_n_spin.setEnabled)
        every_n_row = QHBoxLayout()
        every_n_row.addWidget(self.mode_every_n)
        every_n_row.addWidget(self.every_n_spin)

        # ranges line edit (enabled only with that mode)
        self.ranges_edit = QLineEdit()
        self.ranges_edit.setPlaceholderText(tr("split.ranges.placeholder"))
        self.ranges_edit.setEnabled(False)
        self.mode_ranges.toggled.connect(self.ranges_edit.setEnabled)
        ranges_row = QHBoxLayout()
        ranges_row.addWidget(self.mode_ranges)
        ranges_row.addWidget(self.ranges_edit)

        mode_box = QVBoxLayout()
        mode_box.addWidget(self.mode_single)
        mode_box.addLayout(every_n_row)
        mode_box.addLayout(ranges_row)
        mode_container = QWidget()
        mode_container.setLayout(mode_box)
        form.addRow(tr("split.mode.label"), mode_container)

        # --- Output directory ---
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText(tr("split.output_dir.label"))
        browse_button = QPushButton(tr("split.browse"))
        browse_button.clicked.connect(self._choose_directory)
        out_row = QHBoxLayout()
        out_row.addWidget(self.output_edit)
        out_row.addWidget(browse_button)
        out_container = QWidget()
        out_container.setLayout(out_row)
        form.addRow(tr("split.output_dir.label"), out_container)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        buttons.button(QDialogButtonBox.Ok).setText(tr("split.ok"))
        buttons.button(QDialogButtonBox.Cancel).setText(tr("split.cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _choose_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, tr("split.output_dir.label"), self.output_edit.text())
        if directory:
            self.output_edit.setText(directory)

    def get_settings(self) -> dict:
        """Return the chosen split settings.

        Keys: ``mode`` (:class:`SplitMode`), ``every_n`` (int|None),
        ``ranges_spec`` (str|None), ``output_dir`` (str).
        """
        if self.mode_every_n.isChecked():
            mode = SplitMode.EVERY_N
        elif self.mode_ranges.isChecked():
            mode = SplitMode.RANGES
        else:
            mode = SplitMode.SINGLE
        return {
            "mode": mode,
            "every_n": self.every_n_spin.value() if mode == SplitMode.EVERY_N else None,
            "ranges_spec": self.ranges_edit.text() if mode == SplitMode.RANGES else None,
            "output_dir": self.output_edit.text().strip(),
        }
