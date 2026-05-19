# Report: mypy-strict-operations

**Status**: Completed
**Date**: 2026-04-14
**Phase**: PDCA Report

## Goal

Block the class of type-contract regressions that silently broke 3 smoke tests on 2026-04-14 (`_calculate_font_sizes` returning `Dict[int, float]` while `_insert_replacement_text` expected `Dict[int, TextMetadata]`) by enforcing mypy `--strict` on `app/operations_service.py` at CI time.

## Implementation Summary

Scoped strict mode via `mypy.ini` using `follow_imports = silent` so only `app/operations_service.py` is strictly checked; other app modules remain permissive until their own PDCA cycles. A subprocess-based pytest runner makes the check CI-visible.

## Files Changed

- `mypy.ini` (new) — global permissive + `[mypy-app.operations_service]` strict override
- `app/operations_service.py` — TypedDict `TextMetadata`, typed generics (`List[Any]`, `Dict[int, X]`), TypedDict construction in `_calculate_font_sizes`, float-typed binary-search bounds
- `tests/test_mypy.py` (new) — subprocess runner, 60s timeout, asserts exit code 0

## Test Results

- mypy: `Success: no issues found in 1 source file` (16 errors → 0)
- `test_operations_service_passes_mypy_strict` passing
- Full regression: 93/93 passing in 8.43s

## Key Findings

- `follow_imports = silent` is the key knob for incremental strict-mode adoption — scopes errors without ignoring call-site contracts
- TypedDict catches shape drift at the return-type boundary, which was exactly the root cause of the 04-14 incident
- An unused `type: ignore` was flagged by `warn_unused_ignores` after the underlying bug was fixed — good signal that the ignore was masking a real issue

## Acceptance Criteria

- [x] mypy strict passes on `app/operations_service.py`
- [x] Pytest enforcement at CI time
- [x] Other modules unaffected
- [x] Root-cause type mismatch fixed (TypedDict contract)
