# PDF Encryption / Password Protection — Design

> **Status**: ✅ Approved
> **PDCA**: pdf-encryption
> **Plan**: [pdf-encryption.plan.md](../../01-plan/features/pdf-encryption.plan.md)

## Architecture

Encryption is a **save-time policy**, orthogonal to the operation/history model.
It threads through the existing save path; it does NOT become an `Operation`.

```
EncryptionDialog ──settings──▶ file_handlers.save_file_encrypted
        │                               │
        ▼                               ▼
  EncryptionSettings ───▶ controller.save_document(path, encryption=)
                                        │
                                        ▼
                       document_session.save_document(path, encryption=)
                                        │
                        ┌───────────────┴───────────────┐
                        ▼                                ▼
        pdf_engine.save_document_copy(...,      reloaded_doc.authenticate(
            encryption=)                            unlock_password)
                        │
                        ▼
        document.save(path, **encryption.save_kwargs())
```

## Module: `app/encryption.py` (pure, mypy-strict)

```python
@dataclass
class EncryptionSettings:
    user_password: str = ""
    owner_password: str = ""
    allow_print: bool = True
    allow_copy: bool = True
    allow_modify: bool = True
    allow_annotate: bool = True

    def is_active(self) -> bool        # any password OR any restriction
    def permission_flags(self) -> int  # _BASE_PERMS | toggled bits
    def unlock_password(self) -> str   # owner_pw or user_pw (re-open key)
    def save_kwargs(self) -> dict      # {} if inactive, else encryption kwargs
```

- **Method**: `fitz.PDF_ENCRYPT_AES_256` (=5).
- **Permission bits**: `PDF_PERM_PRINT` (4), `COPY` (16), `MODIFY` (8),
  `ANNOTATE` (32), toggled by the four `allow_*` flags.
- **Always-granted base perms**: `ACCESSIBILITY | ASSEMBLE | FORM | PRINT_HQ`
  so the file stays usable for screen-readers / form-fill regardless of UI.
- **`is_active()` guard**: empty passwords + all-allowed ⇒ `save_kwargs()` returns
  `{}` ⇒ falls back to the normal unencrypted save (no silent encryption).
- **`save_kwargs()`** sets `owner_pw = owner_password or user_password` so the
  document always has a usable owner credential.

## Save-path changes

- `pdf_engine.save_document_copy(..., encryption: EncryptionSettings | None = None)`
  builds `save_kwargs = {"garbage": 3, "deflate": True}` then
  `.update(encryption.save_kwargs())` when provided.
- `document_session.save_document(output_path, encryption=None)`: after
  `save_document_copy`, when `encryption and encryption.is_active()` it calls
  `reloaded_doc.authenticate(encryption.unlock_password())` before `_bind_document`
  so the live session can read pages again.
- `controller.save_document(output_path, encryption=None)`: pass-through.

All new params are **keyword-optional with `None` default** → 100% backward
compatible with existing callers and tests.

## UI: `app/encryption_dialog.py` + menu

- `EncryptionDialog(QDialog)`: user-password + confirm, owner-password + confirm,
  four permission checkboxes (default checked). `get_settings() -> EncryptionSettings`.
- Validation: password/confirm mismatch → inline warning, block OK.
- New **File ▸ "Encrypt & Save As…"** action (`menu.file.save_encrypted`),
  shortcut `Ctrl+Alt+S`. Handler `save_file_encrypted` reuses the blocking-warning
  guard, opens the dialog, then `QFileDialog` for the path.

## i18n keys (en + ko)

`menu.file.save_encrypted`, `dialog.encrypt.*` (title, user_pw, owner_pw,
confirm, perm_print, perm_copy, perm_modify, perm_annotate, mismatch, hint),
`status.saved_encrypted`.

## Config (`app/config.py`)

`ENCRYPTION_DEFAULT_ALLOW_PRINT/COPY/MODIFY/ANNOTATE = True` (single source for
dialog defaults).

## Testing (`tests/test_encryption.py`)

1. `is_active()` truth table (no-op vs password vs restriction).
2. `save_kwargs()` shape + permission bit math per toggle.
3. Round-trip: save with user_pw → `fitz.open` reports `needs_pass`,
   wrong pw fails `authenticate`, correct pw succeeds.
4. Permission round-trip: deny-copy → reopened doc `permissions` lacks COPY bit.
5. Inactive settings → unencrypted file opens without password.
6. `mypy --strict app/encryption.py` via the strict-leaf gate.

## Backward Compatibility / DRY / SRP

- Plain "Save As…" untouched.
- One policy object, one builder (`save_kwargs`) — no duplicated bit math.
- `encryption.py` has zero Qt/IO deps → unit-testable, strict-typed.
