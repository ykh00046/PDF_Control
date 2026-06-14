"""Tests for PDF encryption / password protection (pdf-encryption PDCA)."""
import fitz

from app.config import (
    ENCRYPTION_DEFAULT_ALLOW_ANNOTATE,
    ENCRYPTION_DEFAULT_ALLOW_COPY,
    ENCRYPTION_DEFAULT_ALLOW_MODIFY,
    ENCRYPTION_DEFAULT_ALLOW_PRINT,
)
from app.document_session import DocumentSession
from app.encryption import (
    PERM_COPY,
    PERM_PRINT,
    EncryptionSettings,
)
from app.pdf_engine import save_document_copy

# ── Policy: is_active ───────────────────────────────────────────────

def test_default_settings_inactive():
    """No passwords + all permissions allowed ⇒ inactive (plain save)."""
    settings = EncryptionSettings()
    assert settings.is_active() is False
    assert settings.save_kwargs() == {}


def test_user_password_activates():
    assert EncryptionSettings(user_password="secret").is_active() is True


def test_owner_password_activates():
    assert EncryptionSettings(owner_password="admin").is_active() is True


def test_restriction_only_activates():
    """Disabling a permission alone is enough to require encryption."""
    settings = EncryptionSettings(allow_copy=False)
    assert settings.is_active() is True


# ── Policy: save_kwargs / permission math ───────────────────────────

def test_save_kwargs_shape():
    settings = EncryptionSettings(user_password="u", owner_password="o")
    kwargs = settings.save_kwargs()
    assert kwargs["encryption"] == fitz.PDF_ENCRYPT_AES_256
    assert kwargs["user_pw"] == "u"
    assert kwargs["owner_pw"] == "o"
    assert "permissions" in kwargs


def test_owner_pw_falls_back_to_user_pw():
    kwargs = EncryptionSettings(user_password="u").save_kwargs()
    assert kwargs["owner_pw"] == "u"


def test_unlock_password_prefers_owner():
    assert EncryptionSettings(user_password="u", owner_password="o").unlock_password() == "o"
    assert EncryptionSettings(user_password="u").unlock_password() == "u"


def test_permission_flags_toggle_bits():
    allowed = EncryptionSettings(allow_copy=True).permission_flags()
    denied = EncryptionSettings(allow_copy=False).permission_flags()
    assert allowed & PERM_COPY
    assert not (denied & PERM_COPY)
    # Printing untouched stays granted in both.
    assert allowed & PERM_PRINT and denied & PERM_PRINT


def test_config_defaults_all_allowed():
    assert ENCRYPTION_DEFAULT_ALLOW_PRINT
    assert ENCRYPTION_DEFAULT_ALLOW_COPY
    assert ENCRYPTION_DEFAULT_ALLOW_MODIFY
    assert ENCRYPTION_DEFAULT_ALLOW_ANNOTATE


# ── Round-trip via save_document_copy ───────────────────────────────

def test_user_password_round_trip(simple_pdf, tmp_path):
    out = str(tmp_path / "protected.pdf")
    save_document_copy(
        simple_pdf, out, [], encryption=EncryptionSettings(user_password="open123")
    )
    doc = fitz.open(out)
    assert doc.needs_pass  # int flag (1) on an encrypted file
    assert doc.authenticate("wrong") == 0
    assert doc.authenticate("open123") > 0
    doc.close()


def test_deny_copy_round_trip(simple_pdf, tmp_path):
    out = str(tmp_path / "nocopy.pdf")
    save_document_copy(
        simple_pdf, out, [],
        encryption=EncryptionSettings(owner_password="admin", allow_copy=False),
    )
    # Open as a regular reader (no owner auth): with only an owner password the
    # file opens directly, and reader permissions reflect the restrictions.
    # Authenticating as owner would bypass them, so we do NOT authenticate here.
    doc = fitz.open(out)
    assert not (doc.permissions & PERM_COPY)
    assert doc.permissions & PERM_PRINT
    doc.close()


def test_inactive_settings_save_unencrypted(simple_pdf, tmp_path):
    out = str(tmp_path / "plain.pdf")
    save_document_copy(simple_pdf, out, [], encryption=EncryptionSettings())
    doc = fitz.open(out)
    assert not doc.needs_pass
    doc.close()


def test_no_encryption_arg_is_backward_compatible(simple_pdf, tmp_path):
    out = str(tmp_path / "default.pdf")
    save_document_copy(simple_pdf, out, [])  # no encryption kwarg at all
    doc = fitz.open(out)
    assert not doc.needs_pass
    doc.close()


# ── Session integration: re-bind after encrypted save ───────────────

def test_session_reopens_after_encrypted_save(simple_pdf, tmp_path):
    """After saving encrypted, the live session must stay readable."""
    session = DocumentSession(simple_pdf)
    page_count = session.doc.page_count
    out = str(tmp_path / "session_protected.pdf")

    session.save_document(out, encryption=EncryptionSettings(user_password="pw"))

    # Re-bound handle is authenticated → pages accessible, no exception.
    assert session.doc.page_count == page_count
    assert session.file_path == out
    _ = session.doc[0].get_text()  # would raise if not authenticated
