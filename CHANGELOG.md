# Changelog

## [Unreleased]

- Added PDF encryption / password protection: File → "Encrypt & Save As…" (Ctrl+Alt+S) saves the document with AES-256 encryption, a user password (to open) and/or owner password (permissions), plus toggles to allow or deny printing, copying, modifying, and annotating. Leaving everything unset falls back to a normal unencrypted save; the existing "Save As…" is unchanged.
- Added text export: save the whole document or the current page as a `.txt` or `.md` file (Tools → Export Text…, Ctrl+Shift+T). Markdown output adds `## Page N` headers. Source document is never modified.
- Added page management advanced operations: duplicate, extract (save selected pages as a new PDF), and merge (insert another PDF).
- Added document split and batch merge: split a document into multiple PDFs by single page, every N pages, or custom ranges (e.g. `1-3, 5, 7-9`) via Page Manager → Split; merge now accepts several PDFs at once, inserted in the selected order. Splitting never modifies the source document.
- Rebound saved sessions to the saved document and unified preview/save operation paths.
- Moved preview rendering to a subprocess-based worker and added a PDF engine boundary.
- Switched Windows packaging to PyInstaller onedir mode for the render-worker architecture.
- Added build documentation, build script, and release checklist documentation.
- Added frozen smoke and release automation scripts plus a PyMuPDF licensing decision note.
