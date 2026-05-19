# Plan: claude-md-drift-guard

> **Summary**: Automated drift detection between CLAUDE.md Known Issues and the code's actual resolution state, enforced via pre-commit hook.
>
> **Author**: Claude (bkit)
> **Created**: 2026-04-14
> **Status**: 📋 Planned

---

## 1. Problem Statement

During the 2026-04-14 quality refinement review, CLAUDE.md listed **4 issues as open** that had already been fixed in code:

- Config default pollution (`app/config.py` uses `copy.deepcopy`)
- Preview temp document close leak (`app/pdf_engine.py` has `finally` block)
- RemoveSection memory guard (`app/model.py` has DPI auto-cap)
- Preview-Save logic divergence (`ApplyMode` enum unified both paths)

The drift existed silently — no tooling caught it. Future sessions will re-investigate already-solved problems, wasting time and eroding trust in the doc.

---

## 2. Objective

Detect when CLAUDE.md's `## Known Issues` section lists items that are already resolved in code, and block commits (or warn) until the doc is updated.

---

## 3. Goals

1. **Zero false positives** on the day of merge — drift check must not block legitimate work.
2. **Source of truth**: code-level `## Resolved` markers or explicit resolution comments, not CLAUDE.md.
3. **Low ceremony**: no new config files, no new runtime deps. Python + stdlib.
4. **Pre-commit integration** with `pre-commit` framework (or plain git hook).

---

## 4. Scope

### In Scope
- CLAUDE.md `## Known Issues & Risks` → `### Current Issues` subsection parser
- A convention for annotating resolved issues in code (e.g., `# RESOLVED(issue-slug): ...` comment or a `docs/_resolved.yml` registry)
- Check script: given both inputs, produce a diff report
- Pre-commit hook wiring + `scripts/check_claude_md_drift.py`

### Out of Scope
- General documentation linting
- Cross-file Markdown validation beyond CLAUDE.md
- Auto-fixing (manual update only)

---

## 5. Proposed Approach

**Option A — Registry file**: Maintain `docs/_resolved.yml` with entries like
```yaml
- slug: config-default-pollution
  resolved_at: 2025-12-30
  evidence: app/config.py:39
```
Check script compares CLAUDE.md issue titles (normalized to slugs) against registry; any overlap is a drift.

**Option B — Inline code markers**: Search codebase for `# RESOLVED: {slug}` comments. Same comparison logic.

**Recommendation**: Option A. Registry is easier to review, one place to edit, decouples issue tracking from code layout.

---

## 6. Acceptance Criteria

- [ ] `scripts/check_claude_md_drift.py` runs in < 1 second, prints clear diff
- [ ] Exit code 0 when clean, 1 when drift detected
- [ ] Pre-commit hook triggers on changes to `CLAUDE.md` or `docs/_resolved.yml`
- [ ] README or contributor doc explains how to resolve an issue (add to `_resolved.yml` + remove from CLAUDE.md)
- [ ] Retroactive registry entries for the 4 items from 2026-04-14 session
- [ ] Unit tests for the parser + drift detector

---

## 7. Dependencies / Prerequisites

- None external. Uses Python stdlib (`re`, `yaml` via pyyaml if chosen — PyYAML already transitively pulled by PyInstaller? Verify in Design phase).

---

## 8. Risks

- **Parser brittleness**: CLAUDE.md format may change. Mitigate with a strict section-header regex and a failing test if format drifts.
- **Slug collision**: Two different issues with similar titles. Mitigate by requiring unique slugs in registry.

---

## 9. Rough Effort

~1–2 hours implementation + tests. Low risk.

---

## 10. Next Step

`/pdca design claude-md-drift-guard`
