# Changelog

## [Unreleased]

- Fixed: text export's "page range" option now works — entering a range like "1-3, 5, 7-9" exports exactly those pages. Previously selecting the range option silently exported only the current page.
- Added text watermarks: Tools → "Add Watermark..." (Ctrl+Shift+W) overlays semi-transparent, diagonal text (e.g. "CONFIDENTIAL", "DRAFT") on the current page or every page, with adjustable text, size, color, opacity, and angle.
- Improved: saving now shows a wait cursor and a "Saving..." status so a large document's save no longer looks like the app has frozen.
- Fixed (data loss): page changes — deleting, rotating, moving, duplicating, merging, or reordering pages — were silently discarded when you saved (the save re-read the original file and applied only text edits). Saving now writes the document exactly as you see it, with both page changes and text edits. Encrypted save/decrypt is unaffected.
- Improved: text replacement now keeps the original typeface even when that font is NOT installed on your system — the font embedded in the PDF itself is reused for the replacement. (Subset-embedded fonts, which only contain the glyphs the document already used, safely fall back to a standard font.)
- Improved: text replacement now matches the original much more closely — the replacement is rendered in the document's own typeface when that font is installed on the system (previously everything fell back to Helvetica/Times/Courier approximations, and batch replace was always Helvetica), sits exactly on the original text's baseline, and keeps the original font size even when the selection box is drawn larger than the text.
- Changed: unsaved edits (text replace/delete, crop, section removal) now survive page reordering — moving, duplicating, merging, or drag-reordering pages remaps the pending edit history onto the pages it belonged to instead of silently discarding it. The redo stack is still cleared (page indices change), matching the existing delete-page behavior.
- Changed: removed the staged progress dialog from "Remove Section" — adding the operation completes instantly (the heavy rendering already runs asynchronously in the preview worker), so the 25/50/75% progress steps did not correspond to any real work.
- Internal: unified the controller's error handling into a single guard (user-validation rejections vs internal failures now log at the correct level), decomposed the largest text-layout function, and promoted the document/session/engine core modules to the mypy strict gate.
- Internal: added GitHub Actions CI (windows-latest), pinned all dependency versions in `requirements.txt` (including previously-missing test dependencies), and tidied the repository root (legacy documents archived, scratch scripts moved to `scripts/`).
- Fixed: per-replacement word-wrap choice ("긴 텍스트 줄바꿈" checkbox) was ignored in the preview (but applied on save) because the render worker dropped the `wrap` field when rebuilding operations. Preview and save now match again.
- Security: the source password for an encrypted PDF is no longer written to the temporary render job file on disk; it is now sent to the render worker over an in-memory stdin pipe, so it can no longer linger in the temp directory after a crash.
- Fixed: the mypy gate (2 tests) failed on Korean Windows because of a non-ASCII character in `mypy.ini`; the file is now ASCII-only with a guard comment.
- Added opening of password-protected PDFs: when you open (or drag-and-drop) an encrypted PDF, a password prompt appears and retries on an incorrect password. Editing, preview, and saving then work as usual.
- Added "Remove Protection (Decrypt)…" (File menu, Ctrl+Alt+D): saves a currently-open encrypted document as a plain, unencrypted PDF. The action is a no-op with a status hint when the document is not protected.
- Added PDF encryption / password protection: File → "Encrypt & Save As…" (Ctrl+Alt+S) saves the document with AES-256 encryption, a user password (to open) and/or owner password (permissions), plus toggles to allow or deny printing, copying, modifying, and annotating. Leaving everything unset falls back to a normal unencrypted save; the existing "Save As…" is unchanged.
- Added text export: save the whole document or the current page as a `.txt` or `.md` file (Tools → Export Text…, Ctrl+Shift+T). Markdown output adds `## Page N` headers. Source document is never modified.
- Added page management advanced operations: duplicate, extract (save selected pages as a new PDF), and merge (insert another PDF).
- Added document split and batch merge: split a document into multiple PDFs by single page, every N pages, or custom ranges (e.g. `1-3, 5, 7-9`) via Page Manager → Split; merge now accepts several PDFs at once, inserted in the selected order. Splitting never modifies the source document.
- Rebound saved sessions to the saved document and unified preview/save operation paths.
- Moved preview rendering to a subprocess-based worker and added a PDF engine boundary.
- Switched Windows packaging to PyInstaller onedir mode for the render-worker architecture.
- Added build documentation, build script, and release checklist documentation.
- Added frozen smoke and release automation scripts plus a PyMuPDF licensing decision note.
