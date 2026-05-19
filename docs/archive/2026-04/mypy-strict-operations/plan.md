# Plan: mypy-strict-operations

> **Summary**: Apply `mypy --strict` to `app/operations_service.py` to prevent type-contract drift like the one that silently broke 3 smoke tests.
>
> **Author**: Claude (bkit)
> **Created**: 2026-04-14
> **Status**: 📋 Planned

---

## 1. Problem Statement

On 2026-04-14, a latent bug was discovered in `app/operations_service.py`:

- `_calculate_font_sizes` was annotated `-> Dict[int, float]`
- Caller `_insert_replacement_text` consumed it as `Dict[int, Dict]`, calling `.get("fontsize")` on each value
- Python's runtime type check is nonexistent, so the bug only surfaced when `RedactReplace` was used with `fontsize != 0`
- 3 smoke tests failed with `AttributeError: 'float' object has no attribute 'get'`
- Additionally, `from app.model import _calculate_estimated_fontsize` referenced a non-existent symbol — only caught at runtime in the same code path

A static type checker would have caught both issues immediately.

---

## 2. Objective

Run `mypy --strict` on `app/operations_service.py` (and its imported symbols from `app/model.py`, `app/pdf_engine.py`) as part of the test suite, and fix all reported type errors.

---

## 3. Goals

1. **Prevent future contract mismatches** in the critical operations pipeline.
2. **Document actual contracts** via precise type hints (TypedDict for the metadata shape).
3. **Incremental scope**: don't boil the ocean — target one module, expand later.
4. **CI-visible**: fail the pytest run if mypy reports errors on the scoped module.

---

## 4. Scope

### In Scope
- `app/operations_service.py` — full `--strict` compliance
- Symbols it imports from `app/model.py` and `app/pdf_engine.py` — annotate at least the signatures that cross the boundary
- A `TypedDict` (or dataclass) for the font metadata shape currently passed as `Dict`
- pytest integration via `subprocess.run(["mypy", ...])` or the `pytest-mypy` plugin
- `mypy.ini` or `pyproject.toml` mypy config

### Out of Scope
- Typing the whole `app/` package
- PySide6 / PyMuPDF stubs completeness (use `--ignore-missing-imports` for those)
- Strict mode for `app/ui.py` (heavy Qt surface area)

---

## 5. Proposed Approach

1. Install `mypy` as a dev dependency
2. Add `mypy.ini` targeting `app/operations_service.py` with `strict = True` and `ignore_missing_imports = True` for PyMuPDF/PySide6
3. Replace `Dict[int, Dict]` with a proper `TypedDict`:
   ```python
   class TextMetadata(TypedDict):
       fontsize: float
       color: Tuple[float, float, float]
       font_flags: int
       fontname: str
   ```
4. Fix whatever mypy reports
5. Add `tests/test_mypy.py` that shells out to mypy and asserts exit code 0

---

## 6. Acceptance Criteria

- [ ] `mypy app/operations_service.py` reports 0 errors
- [ ] `TextMetadata` TypedDict defined and used
- [ ] `_calculate_font_sizes` return type correctly annotated as `Dict[int, TextMetadata]`
- [ ] `tests/test_mypy.py` passes
- [ ] `mypy.ini` or `[tool.mypy]` section committed
- [ ] `requirements.txt` or dev dependency file updated

---

## 7. Dependencies / Prerequisites

- `mypy` package (dev-only)
- Python 3.13 is already in use — mypy supports this

---

## 8. Risks

- **Transitive type errors**: annotating `_calculate_font_sizes` properly may ripple through `_insert_replacement_text` and `_insert_text_with_autofit`, both ~80 LOC. Estimate 20–30 additional type fixes.
- **PyMuPDF has no type stubs**: forces `Any` or manual stubs at the boundary. Accept `Any` for `fitz.Page`, `fitz.Rect`.
- **pytest-mypy plugin drift**: prefer subprocess invocation for stability.

---

## 9. Rough Effort

~2–4 hours. Most time on transitive type fixes.

---

## 10. Next Step

`/pdca design mypy-strict-operations`
