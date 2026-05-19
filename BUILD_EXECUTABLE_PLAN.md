# Build Executable Plan

## Goal

Produce a Windows distributable for the current architecture:

- PySide6 desktop UI
- PyMuPDF-based document engine
- subprocess-based preview renderer via `--render-worker`

## Packaging Decision

Use `PyInstaller` in `onedir` mode.

Why:

- The app now respawns itself as a preview worker.
- `onefile` would re-run PyInstaller bootstrap extraction for each preview worker launch.
- `onedir` keeps startup cost stable and makes worker debugging simpler.

## Required Inputs

- [pdf_control.spec](/C:/X/Tools/PDF_Control/pdf_control.spec)
- [requirements-build.txt](/C:/X/Tools/PDF_Control/requirements-build.txt)
- [scripts/build_windows.ps1](/C:/X/Tools/PDF_Control/scripts/build_windows.ps1)

## Packaging Checklist

1. Bundle `app/i18n/*.json`.
2. Include lazy-imported dialogs and render worker modules.
3. Exclude test modules from the frozen artifact.
4. Validate frozen `--render-worker` execution.
5. Run GUI smoke test on the frozen build.
6. Zip `dist/PDF_Control/` for distribution.

## Follow-up After Successful Build

1. Add code signing for Windows distribution.
2. Test on a clean machine without Python installed.
3. Document license handling for PyMuPDF before external release.
