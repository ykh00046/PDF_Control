"""PDF encryption settings and save-option builder.

Pure, side-effect-free policy helpers so encryption behavior is unit-testable
without a GUI or a real document. Consumed by
:func:`app.pdf_engine.save_document_copy`.

Encryption is a *save-time* concern, orthogonal to the operation/history model;
it never becomes an :class:`~app.operations.base.Operation`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import fitz

# Permission bits surfaced in the UI, mapped to PyMuPDF constants.
PERM_PRINT: int = fitz.PDF_PERM_PRINT
PERM_COPY: int = fitz.PDF_PERM_COPY
PERM_MODIFY: int = fitz.PDF_PERM_MODIFY
PERM_ANNOTATE: int = fitz.PDF_PERM_ANNOTATE

# Permissions always granted regardless of the UI toggles. Keeping these on
# preserves accessibility (screen readers), page assembly, form filling, and
# high-quality printing so a protected file stays usable.
_BASE_PERMS: int = (
    fitz.PDF_PERM_ACCESSIBILITY
    | fitz.PDF_PERM_ASSEMBLE
    | fitz.PDF_PERM_FORM
    | fitz.PDF_PERM_PRINT_HQ
)

# AES-256 is the strongest method PyMuPDF exposes.
ENCRYPT_METHOD: int = fitz.PDF_ENCRYPT_AES_256


@dataclass
class EncryptionSettings:
    """User-chosen protection policy for a single save.

    An "inactive" policy (no passwords and every permission allowed) produces
    empty save kwargs so the caller transparently performs a normal,
    unencrypted save — never silently encrypting an unprotected document.
    """

    user_password: str = ""
    owner_password: str = ""
    allow_print: bool = True
    allow_copy: bool = True
    allow_modify: bool = True
    allow_annotate: bool = True

    def is_active(self) -> bool:
        """True when any protection (a password or a restriction) is requested."""
        all_allowed = (
            self.allow_print
            and self.allow_copy
            and self.allow_modify
            and self.allow_annotate
        )
        return bool(self.user_password or self.owner_password) or not all_allowed

    def permission_flags(self) -> int:
        """Combine the always-granted base permissions with the UI toggles."""
        perms = _BASE_PERMS
        if self.allow_print:
            perms |= PERM_PRINT
        if self.allow_copy:
            perms |= PERM_COPY
        if self.allow_modify:
            perms |= PERM_MODIFY
        if self.allow_annotate:
            perms |= PERM_ANNOTATE
        return perms

    def unlock_password(self) -> str:
        """Password that re-opens the saved file (owner preferred over user)."""
        return self.owner_password or self.user_password

    def save_kwargs(self) -> Dict[str, Any]:
        """PyMuPDF ``Document.save`` kwargs for this policy.

        Returns an empty mapping when the policy is inactive so the caller
        falls back to a normal save.
        """
        if not self.is_active():
            return {}
        return {
            "encryption": ENCRYPT_METHOD,
            # Always give the document an owner credential; fall back to the
            # user password so an owner-less, user-protected file still has one.
            "owner_pw": self.owner_password or self.user_password,
            "user_pw": self.user_password,
            "permissions": self.permission_flags(),
        }
