"""Dialog for configuring password protection and permissions before saving.

Returns an :class:`~app.encryption.EncryptionSettings`; the actual save-time
encryption is handled by the save path (see ``app.encryption``).
"""
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.config import (
    ENCRYPTION_DEFAULT_ALLOW_ANNOTATE,
    ENCRYPTION_DEFAULT_ALLOW_COPY,
    ENCRYPTION_DEFAULT_ALLOW_MODIFY,
    ENCRYPTION_DEFAULT_ALLOW_PRINT,
)
from app.encryption import EncryptionSettings
from app.i18n import tr


class EncryptionDialog(QDialog):
    """Collects passwords and permission toggles for an encrypted save."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle(tr("dialog.encrypt.title"))
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("dialog.encrypt.hint")))

        # ── Passwords ──────────────────────────────────────────────
        pw_group = QGroupBox(tr("dialog.encrypt.passwords"))
        grid = QGridLayout()

        self.user_pw = QLineEdit()
        self.user_pw_confirm = QLineEdit()
        self.owner_pw = QLineEdit()
        self.owner_pw_confirm = QLineEdit()
        for field in (self.user_pw, self.user_pw_confirm,
                      self.owner_pw, self.owner_pw_confirm):
            field.setEchoMode(QLineEdit.Password)

        grid.addWidget(QLabel(tr("dialog.encrypt.user_pw")), 0, 0)
        grid.addWidget(self.user_pw, 0, 1)
        grid.addWidget(QLabel(tr("dialog.encrypt.confirm")), 1, 0)
        grid.addWidget(self.user_pw_confirm, 1, 1)
        grid.addWidget(QLabel(tr("dialog.encrypt.owner_pw")), 2, 0)
        grid.addWidget(self.owner_pw, 2, 1)
        grid.addWidget(QLabel(tr("dialog.encrypt.confirm")), 3, 0)
        grid.addWidget(self.owner_pw_confirm, 3, 1)
        pw_group.setLayout(grid)
        layout.addWidget(pw_group)

        # ── Permissions ────────────────────────────────────────────
        perm_group = QGroupBox(tr("dialog.encrypt.permissions"))
        perm_layout = QVBoxLayout()
        self.allow_print = QCheckBox(tr("dialog.encrypt.perm_print"))
        self.allow_copy = QCheckBox(tr("dialog.encrypt.perm_copy"))
        self.allow_modify = QCheckBox(tr("dialog.encrypt.perm_modify"))
        self.allow_annotate = QCheckBox(tr("dialog.encrypt.perm_annotate"))
        self.allow_print.setChecked(ENCRYPTION_DEFAULT_ALLOW_PRINT)
        self.allow_copy.setChecked(ENCRYPTION_DEFAULT_ALLOW_COPY)
        self.allow_modify.setChecked(ENCRYPTION_DEFAULT_ALLOW_MODIFY)
        self.allow_annotate.setChecked(ENCRYPTION_DEFAULT_ALLOW_ANNOTATE)
        for box in (self.allow_print, self.allow_copy,
                    self.allow_modify, self.allow_annotate):
            perm_layout.addWidget(box)
        perm_group.setLayout(perm_layout)
        layout.addWidget(perm_group)

        # ── Buttons ────────────────────────────────────────────────
        button_layout = QHBoxLayout()
        ok_button = QPushButton(tr("dialog.encrypt.save"))
        cancel_button = QPushButton(tr("dialog.encrypt.cancel"))
        ok_button.clicked.connect(self._on_accept)
        cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

    def _on_accept(self):
        """Validate password/confirm pairs before accepting."""
        if self.user_pw.text() != self.user_pw_confirm.text() or \
                self.owner_pw.text() != self.owner_pw_confirm.text():
            QMessageBox.warning(
                self,
                tr("dialog.encrypt.title"),
                tr("dialog.encrypt.mismatch"),
            )
            return
        self.accept()

    def get_settings(self) -> EncryptionSettings:
        """Build an :class:`EncryptionSettings` from the current widget state."""
        return EncryptionSettings(
            user_password=self.user_pw.text(),
            owner_password=self.owner_pw.text(),
            allow_print=self.allow_print.isChecked(),
            allow_copy=self.allow_copy.isChecked(),
            allow_modify=self.allow_modify.isChecked(),
            allow_annotate=self.allow_annotate.isChecked(),
        )
