# Release Checklist

This document is a practical release gate for Windows distribution.

It is not legal advice. It is a checklist for engineering readiness and for flagging items that need an explicit product or legal decision.

## Current Status

Verified locally on 2026-03-23:

- `PyInstaller` onedir build succeeds via `scripts/build_windows.ps1`
- frozen render worker smoke test succeeds with `--render-worker`
- frozen GUI executable launches and stays alive during a short smoke window
- release automation scripts exist for build, smoke, zip, and manifest generation

Still required before external release:

- clean-machine smoke test on a Windows system without the development environment
- code signing for the Windows executable
- explicit repository license file
- explicit PyMuPDF distribution decision

## Distribution Gates

1. Build

- Run `.\scripts\build_windows.ps1`
- Confirm `dist\PDF_Control\PDF_Control.exe` exists
- Preferred: run `.\scripts\release_windows.ps1` for the full local release path

2. Frozen Smoke Test

- Run `.\scripts\smoke_frozen.ps1`
- Launch the GUI executable
- Open a sample PDF
- Verify open/save, delete/replace, crop, remove-section, undo/redo
- Verify zoom repeatedly to confirm worker-based preview remains stable

3. Clean-Machine Validation

- Test on Windows with no local source checkout assumptions
- Confirm `%APPDATA%\PDF_Control\logs` and config creation
- Confirm translations load correctly from bundled resources

4. Code Signing

- Sign `dist\PDF_Control\PDF_Control.exe`
- Re-test after signing
- Record certificate identity and timestamping method used for release

5. Licensing Decision

- Add the repository license file before public distribution
- Confirm whether the planned distribution model is internal-only, open-source, or closed-source
- If closed-source distribution is required, treat PyMuPDF licensing as a release blocker until resolved
- See `docs/PYMUPDF_LICENSE_DECISION.md`

6. Release Artifacts

- Update `CHANGELOG.md`
- Package `dist\PDF_Control\` as a ZIP for distribution
- Include user-facing release notes if shipping beyond the dev team
