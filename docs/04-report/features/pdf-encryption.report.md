# PDF Encryption / Password Protection — Completion Report

> **Status**: ✅ Approved (Completed)
> **PDCA**: pdf-encryption
> **Date**: 2026-06-08
> **Match Rate**: 100% · **Tests**: 191 passed (+14)

## Summary

Added password protection + permission control to PDF Control's save path.
Users can now File → **"Encrypt & Save As…"** (Ctrl+Alt+S) to produce an
AES-256 encrypted PDF with a user password (open), an owner password
(permissions), and toggles for print / copy / modify / annotate.

## What Shipped

| Layer | Change |
|-------|--------|
| Policy | `app/encryption.py` — pure, mypy-strict `EncryptionSettings` |
| Engine | `pdf_engine.save_document_copy(encryption=)` |
| Session | `document_session.save_document(encryption=)` + authenticate re-bind |
| Controller | `controller.save_document(encryption=)` |
| UI | `app/encryption_dialog.py`, File menu action, `_commit_save` (DRY) |
| Config | `ENCRYPTION_DEFAULT_ALLOW_*` |
| i18n | `dialog.encrypt.*`, `menu.file.save_encrypted`, `status.saved_encrypted` (en/ko) |
| Tests | `tests/test_encryption.py` (14), strict gate + leaf list |
| Docs | plan / design / analysis / report + CHANGELOG + CLAUDE.md |

## PDCA Cycle

- **Plan / Design**: scoped as a save-time policy, orthogonal to operations/history.
- **Do**: implemented module + save-path threading + dialog + i18n.
- **Check**: gap analysis 100%; 2 PyMuPDF quirks found & handled (int `needs_pass`,
  owner-auth permission bypass).
- **QA**: full suite 191 ✅, mypy strict ✅, i18n parity ✅, drift-guard ✅,
  headless dialog smoke ✅.
- **Act**: no iteration needed (≥90%).

## Design Decisions

- **Not an `Operation`**: encryption is save-time, so it bypasses the rect-based
  per-page history model — zero coupling, zero regression surface.
- **`is_active()` no-op guard**: never silently encrypts; inactive policy → normal save.
- **Owner-password fallback**: `owner_pw = owner or user` so every protected file
  has a usable owner credential.
- **Backward compatibility**: all new params keyword-optional (`None`), existing
  "Save As…" untouched.

## Verification Notes (interpreter)

The project test interpreter is Python 3.13
(`...\Python313\python.exe`, has `pytest-qt` + `mypy`). The hermes venv lacks
those, so UI/mypy tests must run under 3.13. Full run there: **191 passed**.

## Follow-ups (future cycles)

- Decrypt / remove protection from an already-encrypted file.
- Open-time password prompt when loading an encrypted PDF.
- `typing-legacy-core`: bring `document_session` / `pdf_engine` onto strict gate.
