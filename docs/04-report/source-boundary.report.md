# Source and Artifact Boundary Report

> Purpose: define which directories in `PDF_Control` are source-of-truth and which are disposable runtime, test, or build artifacts.
>
> Reviewed: 2026-03-31

---

## Summary

The product source lives in tracked code and documentation paths such as `app/`, `tests/`, `scripts/`, and `docs/`.

The working tree also contains multiple generated paths:

- runtime app data in `.appdata/`
- test workspaces under `logs/pytest_tmp/`
- ad hoc review/build outputs under `logs/`
- PyInstaller outputs under `build/` and `dist/`
- Python caches under `__pycache__/`, `app/__pycache__/`, and `tests/__pycache__/`

Current code already routes normal development-time config/log writes to `.appdata/` through `app/path_helper.py`, and frozen builds to the platform app-data directory. The root-level `logs/` tree exists primarily because tests intentionally create workspace-local fixtures there and past manual review/build runs were not cleaned up.

## Boundary Rules

### Source of truth

Keep and review these paths as product source:

- `app/`
- `tests/`
- `scripts/`
- `docs/`
- top-level entry/config files such as `main.py`, `pdf_control.spec`, `requirements*.txt`, `pytest.ini`, `README.md`

### Disposable generated artifacts

Treat these paths as generated and safe to recreate:

- `.appdata/`
- `.pytest_cache/`
- `.pytest_tmp/`
- `__pycache__/`
- `build/`
- `dist/`
- `logs/`

### Special case: `logs/`

`logs/` is not product source even though tests use it intentionally.

- `tests/conftest.py` creates `logs/pytest_tmp/<case>/...` as a workspace-local temporary area.
- manual review assets and smoke-test outputs also appear under `logs/`.
- none of these files should be treated as canonical inputs to the product.

## Risks Observed

- README and `CLAUDE.md` still described `logs/` as the primary application log location, which no longer matches runtime behavior.
- No ignore file existed at the project root, so generated files accumulate and can be mistaken for maintained assets.
- Existing `build/`, `dist/`, and `logs/` contents make source review noisier and increase the chance of accidental packaging of stale artifacts.

## Narrow Cleanup Plan

1. Add a root `.gitignore` that excludes runtime, test, cache, and build outputs.
2. Update human-facing docs to distinguish product source from generated artifacts.
3. When convenient, remove existing generated directories from the working tree and regenerate only what is needed for builds or test investigation.

## Expected Steady State

- development logs/config: `.appdata/`
- frozen app logs/config: platform app-data directory
- test-only temporary data: `logs/pytest_tmp/`
- packaged binaries: `dist/`
- intermediate PyInstaller state: `build/`
- repository review surface: source files and docs only
