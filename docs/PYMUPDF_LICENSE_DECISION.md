# PyMuPDF Distribution Decision

This note is a release-decision aid, not legal advice.

Last verified: 2026-03-23

Official references:

- https://pymupdf.io/
- https://pymupdf.readthedocs.io/en/latest/about.html

## Current Engineering Read

According to the official PyMuPDF site and documentation, PyMuPDF is offered under an open-source AGPL path and a commercial licensing path through Artifex.

## What This Means For Release Planning

1. Internal-only use

- Still requires checking the official license terms against the actual deployment model.
- Do not assume internal use is automatically cleared.

2. Open-source distribution

- Align the repository license, source-distribution model, and dependency obligations before release.
- Do not ship public binaries while the repository still has no finalized license file.

3. Closed-source or customer distribution

- Treat PyMuPDF licensing as a release blocker until the commercial-vs-open-source path is explicitly approved.

## Required Decision Before Public Release

- Decide whether this project is staying internal, becoming open-source, or shipping as a closed-source binary.
- Add the repository `LICENSE` file only after that decision is made.
- Record the outcome in the release notes or release checklist.
