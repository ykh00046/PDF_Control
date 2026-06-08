# PDF Encryption — Gap Analysis

> **Status**: ✅ Approved
> **PDCA**: pdf-encryption
> **Match Rate**: 100%

## Design vs Implementation

| Design item | Implemented | Evidence |
|-------------|-------------|----------|
| Pure `EncryptionSettings` (is_active / permission_flags / unlock_password / save_kwargs) | ✅ | `app/encryption.py` |
| AES-256 + base perms preserved | ✅ | `ENCRYPT_METHOD`, `_BASE_PERMS` |
| `save_document_copy(encryption=)` merge | ✅ | `app/pdf_engine.py:67` |
| `session.save_document(encryption=)` + authenticate re-bind | ✅ | `app/document_session.py:124` |
| `controller.save_document(encryption=)` pass-through | ✅ | `app/controller.py:72` |
| Dialog (passwords + confirm + 4 perms + mismatch guard) | ✅ | `app/encryption_dialog.py` |
| File menu "Encrypt & Save As…" (Ctrl+Alt+S) | ✅ | `app/ui_menu.py` |
| DRY shared save (`_commit_save`) | ✅ | `app/handlers/file_handlers.py` |
| i18n en/ko parity | ✅ | `test_i18n_validation` green |
| Config defaults | ✅ | `app/config.py` `ENCRYPTION_DEFAULT_*` |
| Strict gate + tests | ✅ | `mypy.ini`, `tests/test_mypy.py`, `tests/test_encryption.py` |

## Success Criteria

1. User-password file requires the password to open — ✅ `test_user_password_round_trip`.
2. Permission flags honored (deny-copy) — ✅ `test_deny_copy_round_trip`.
3. Session keeps working after encrypted save — ✅ `test_session_reopens_after_encrypted_save`.
4. Plain save unchanged / backward compatible — ✅ `test_no_encryption_arg_is_backward_compatible`.
5. `app/encryption.py` mypy `--strict` clean — ✅.

## Findings During Implementation

- **needs_pass is int (0/1), not bool** — tests use truthiness, not `is True`.
- **Owner auth bypasses restrictions** — permission round-trip must inspect the
  file as a *reader* (no owner authenticate), else the owner sees full perms.
- **Empty user password (owner-only)** ⇒ file opens without prompt but with
  reduced reader permissions — expected PDF behavior, documented in tests.

## Result

191 tests pass (was 177). Match rate 100% → proceed to Report (no iterate needed).
