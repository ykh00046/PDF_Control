# PDF Encryption / Password Protection — Plan

> **Status**: ✅ Approved
> **Level**: Starter
> **Created**: 2026-06-08
> **PDCA**: pdf-encryption

## Problem

PDF Control can edit and restructure documents but cannot **control access** to
the output. "PDF Control" implies access control: users need to protect saved
PDFs with passwords and restrict printing/copying/modifying. This is a top
real-world need (legal, HR, finance documents) and is currently missing.

## Goal

Add an **"Encrypt & Save As…"** flow that saves the current document with:

- A **user password** (open/read) and/or **owner password** (permission owner).
- **Permission restrictions**: allow/deny print, copy, modify, annotate.
- AES-256 encryption (PyMuPDF native).

## Scope

### In Scope
- Pure, testable encryption-policy module (`app/encryption.py`).
- Save-path integration (`pdf_engine` → `document_session` → `controller`).
- A dedicated dialog (`app/encryption_dialog.py`) + Tools/File menu action.
- i18n (en/ko), config defaults, unit tests, mypy-strict gate, docs.

### Out of Scope
- Decryption / removing existing protection (future cycle).
- Certificate/public-key encryption.
- Per-page or partial encryption.
- Changing the existing plain "Save As…" behavior.

## Success Criteria

1. Saving with a user password produces a file that requires that password to open.
2. Permission flags are honored (e.g. deny-copy reflected in saved doc perms).
3. After an encrypted save the in-app session keeps working (re-bind succeeds via
   `authenticate`).
4. No regression: existing plain save path unchanged; full suite green.
5. `app/encryption.py` passes mypy `--strict` (added to the strict-leaf gate).

## Risks

- **Re-open after save**: `save_document()` reloads the file; an encrypted file
  needs authentication before page access. Mitigation: authenticate the reloaded
  handle with the owner/user password.
- **Empty passwords + full permissions** = no-op; must not silently encrypt.

## Related
- Design: [pdf-encryption.design.md](../../02-design/features/pdf-encryption.design.md)
- Analysis: [pdf-encryption.analysis.md](../../03-analysis/features/pdf-encryption.analysis.md)
- Report: [pdf-encryption.report.md](../../04-report/features/pdf-encryption.report.md)
