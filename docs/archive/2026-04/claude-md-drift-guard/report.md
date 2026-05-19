# Report: claude-md-drift-guard

**Status**: Completed
**Date**: 2026-04-14
**Phase**: PDCA Report

## Goal

Prevent CLAUDE.md "Known Issues" from silently drifting out of sync with the codebase by detecting items that have already been resolved but remain listed as current.

## Implementation Summary

Registry-based drift detection: `docs/_resolved.yml` is the source of truth for resolved issues (slug + evidence file:line). A script parses CLAUDE.md's `### Current Issues` subsection, slugifies each title, and cross-checks against the registry.

## Files Changed

- `docs/_resolved.yml` (new) — 4 resolved entries with file:line evidence
- `scripts/check_claude_md_drift.py` (new) — parser + drift detector, exit codes 0/1/2
- `tests/test_claude_md_drift.py` (new) — 8 unit tests covering slugify, parser, drift detection, and real CLAUDE.md consistency

## Test Results

- 8/8 drift tests passing
- Full regression: 93/93 passing
- Real CLAUDE.md consistency check green

## Key Findings

- Regex `(?=^##\s|\Z)` required to handle EOF when `Known Issues` is the last section
- Slug-based matching decouples doc wording from code markers — titles can be rephrased without breaking the check
- Registry approach (vs. inline code markers) keeps evidence auditable in one file

## Acceptance Criteria

- [x] Detects resolved items still listed in CLAUDE.md
- [x] Exits 1 on drift, 0 on clean, 2 on parse error
- [x] Unit tests cover slugify, parser, detector
- [x] Real CLAUDE.md passes the check
