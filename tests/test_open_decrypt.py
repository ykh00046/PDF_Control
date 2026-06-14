"""Tests for opening encrypted PDFs + removing protection (pdf-open-decrypt PDCA)."""
import fitz
import pytest

from app.document_session import DocumentSession
from app.encryption import (
    EncryptedPDFError,
    EncryptionSettings,
    IncorrectPassword,
    PasswordRequired,
)
from app.pdf_engine import open_document, save_document_copy

# ── open_document: password handling ────────────────────────────────

def test_open_encrypted_without_password_raises(encrypted_pdf):
    with pytest.raises(PasswordRequired):
        open_document(str(encrypted_pdf))


def test_open_encrypted_wrong_password_raises(encrypted_pdf):
    with pytest.raises(IncorrectPassword):
        open_document(str(encrypted_pdf), password="nope")


def test_open_encrypted_correct_password_succeeds(encrypted_pdf):
    doc = open_document(str(encrypted_pdf), password="open123")
    try:
        # Accessing page text would raise on an unauthenticated handle.
        assert "Secret content" in doc[0].get_text()
    finally:
        doc.close()


def test_open_plain_with_password_is_ignored(simple_pdf):
    """A plain PDF opens normally even if a password is passed."""
    doc = open_document(str(simple_pdf), password="irrelevant")
    try:
        assert doc.page_count == 1
    finally:
        doc.close()


def test_open_plain_without_password_backward_compatible(simple_pdf):
    doc = open_document(str(simple_pdf))
    try:
        assert doc.page_count == 1
    finally:
        doc.close()


def test_password_exceptions_share_base():
    assert issubclass(PasswordRequired, EncryptedPDFError)
    assert issubclass(IncorrectPassword, EncryptedPDFError)


# ── DocumentSession integration ─────────────────────────────────────

def test_session_opens_encrypted_with_password(encrypted_pdf):
    session = DocumentSession(str(encrypted_pdf), password="open123")
    try:
        assert session.is_encrypted is True
        assert session.doc.page_count == 1
        assert "Secret content" in session.doc[0].get_text()
    finally:
        session.close()


def test_session_encrypted_without_password_raises(encrypted_pdf):
    with pytest.raises(PasswordRequired):
        DocumentSession(str(encrypted_pdf))


def test_session_plain_is_not_encrypted(simple_pdf):
    session = DocumentSession(str(simple_pdf))
    try:
        assert session.is_encrypted is False
    finally:
        session.close()


# ── save_document_copy: read encrypted source ───────────────────────

def test_save_copy_reads_encrypted_source(encrypted_pdf, tmp_path):
    """A protected source can be copied to a plain output (decrypt)."""
    out = str(tmp_path / "decrypted.pdf")
    save_document_copy(str(encrypted_pdf), out, [], password="open123")

    doc = fitz.open(out)
    try:
        assert not doc.needs_pass  # plain output
        assert "Secret content" in doc[0].get_text()
    finally:
        doc.close()


def test_save_copy_encrypted_source_wrong_password_raises(encrypted_pdf, tmp_path):
    out = str(tmp_path / "fail.pdf")
    with pytest.raises(IncorrectPassword):
        save_document_copy(str(encrypted_pdf), out, [], password="wrong")


# ── Remove protection (decrypt) round-trip via session ──────────────

def test_session_decrypt_round_trip(encrypted_pdf, tmp_path):
    """Open encrypted → plain save → reopen without password, content kept."""
    session = DocumentSession(str(encrypted_pdf), password="open123")
    try:
        out = str(tmp_path / "removed.pdf")
        session.save_document(out, encryption=None)  # plain save == decrypt

        # Session rebinds to the now-plain output.
        assert session.is_encrypted is False
        assert session.file_path == out

        doc = fitz.open(out)
        try:
            assert not doc.needs_pass
            assert "Secret content" in doc[0].get_text()
        finally:
            doc.close()
    finally:
        session.close()


def test_encrypted_delete_then_decrypt_save(encrypted_pdf, tmp_path):
    """save-integrity + decrypt: a page deleted on an encrypted doc must be
    gone from the plain output (not resurrected by re-opening the source)."""
    session = DocumentSession(str(encrypted_pdf), password="open123")
    try:
        before = session.doc.page_count
        session.insert_blank_page()  # ensure >= 2 pages so a delete is valid
        session.delete_pages([0])
        expected = before  # +1 inserted, -1 deleted
        out = str(tmp_path / "enc_pm.pdf")
        session.save_document(out, encryption=None)  # decrypt

        doc = fitz.open(out)
        try:
            assert not doc.needs_pass
            assert doc.page_count == expected
        finally:
            doc.close()
    finally:
        session.close()


def test_encrypted_reencrypt_after_page_mgmt(encrypted_pdf, tmp_path):
    """Page-management change + re-encrypt: change persists, output protected."""
    session = DocumentSession(str(encrypted_pdf), password="open123")
    try:
        session.insert_blank_page()
        expected = session.doc.page_count
        out = str(tmp_path / "enc_pm_re.pdf")
        session.save_document(out, encryption=EncryptionSettings(user_password="new456"))

        doc = fitz.open(out)
        try:
            assert doc.needs_pass
            assert doc.authenticate("new456") > 0
            assert doc.page_count == expected
        finally:
            doc.close()
    finally:
        session.close()


def test_session_re_encrypt_after_open(encrypted_pdf, tmp_path):
    """Open encrypted → save with a NEW password → session stays readable + encrypted."""
    session = DocumentSession(str(encrypted_pdf), password="open123")
    try:
        out = str(tmp_path / "reencrypted.pdf")
        session.save_document(out, encryption=EncryptionSettings(user_password="new456"))

        assert session.is_encrypted is True
        assert session.doc[0].get_text()  # authenticated rebind, no raise

        doc = fitz.open(out)
        try:
            assert doc.needs_pass
            assert doc.authenticate("open123") == 0  # old password no longer works
            assert doc.authenticate("new456") > 0
        finally:
            doc.close()
    finally:
        session.close()
