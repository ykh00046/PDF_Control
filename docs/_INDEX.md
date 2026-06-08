# PDF Control - Document Index

> **Purpose**: Track all PDCA documents for the PDF Control project
>
> **Last Updated**: 2026-06-08

---

## Legend

| Status         | Meaning            | Claude Behavior      |
| -------------- | ------------------ | -------------------- |
| ✅ Approved    | Use as reference   | Follow as-is         |
| 🔄 In Progress | Being written      | Notify of changes    |
| ⏸️ On Hold     | Temporarily paused | Request confirmation |
| ❌ Deprecated  | No longer valid    | Ignore               |

---

## PDCA Document Status

### Plan (01-plan/)

| Feature                 | Document                                                                          | Status         | Last Updated |
| ----------------------- | --------------------------------------------------------------------------------- | -------------- | ------------ |
| Project Status Analysis | [project-status.plan.md](01-plan/features/project-status.plan.md)                 | 🔄 In Progress | 2026-01-30   |
| Operations Restructure  | [operations-restructure.plan.md](01-plan/features/operations-restructure.plan.md) | 🔄 In Progress | 2026-04-21   |
| Page Advanced Ops       | [page-advanced-ops.plan.md](01-plan/features/page-advanced-ops.plan.md)           | ✅ Approved    | 2026-05-25   |
| R2 Quality Fixes        | [r2-quality-fixes.plan.md](01-plan/features/r2-quality-fixes.plan.md)             | ✅ Approved    | 2026-06-02   |
| Text Export             | [text-export.plan.md](01-plan/features/text-export.plan.md)                       | ✅ Approved    | 2026-06-02   |
| Text Wrap Replace       | [text-wrap-replace.plan.md](01-plan/features/text-wrap-replace.plan.md)           | ✅ Approved    | 2026-06-02   |
| Page Merge / Split      | [page-merge-split.plan.md](01-plan/features/page-merge-split.plan.md)             | ✅ Approved    | 2026-06-02   |
| PDF Encryption          | [pdf-encryption.plan.md](01-plan/features/pdf-encryption.plan.md)                 | ✅ Approved    | 2026-06-08   |

### Design (02-design/)

| Feature           | Document                                                                    | Status         | Last Updated |
| ----------------- | --------------------------------------------------------------------------- | -------------- | ------------ |
| Page Advanced Ops | [page-advanced-ops.design.md](02-design/features/page-advanced-ops.design.md) | ✅ Approved    | 2026-05-25   |
| R2 Quality Fixes  | [r2-quality-fixes.design.md](02-design/features/r2-quality-fixes.design.md)   | ✅ Approved    | 2026-06-02   |
| Text Export       | [text-export.design.md](02-design/features/text-export.design.md)             | ✅ Approved    | 2026-06-02   |
| Text Wrap Replace | [text-wrap-replace.design.md](02-design/features/text-wrap-replace.design.md) | ✅ Approved    | 2026-06-02   |
| Page Merge / Split | [page-merge-split.design.md](02-design/features/page-merge-split.design.md)  | ✅ Approved    | 2026-06-02   |
| PDF Encryption    | [pdf-encryption.design.md](02-design/features/pdf-encryption.design.md)       | ✅ Approved    | 2026-06-08   |

### Analysis (03-analysis/)

| Feature                | Document                                                                    | Status         | Last Updated |
| ---------------------- | --------------------------------------------------------------------------- | -------------- | ------------ |
| Current State Analysis | [current-state.analysis.md](03-analysis/features/current-state.analysis.md) | 🔄 In Progress | 2026-01-30   |
| Page Advanced Ops      | [page-advanced-ops.analysis.md](03-analysis/features/page-advanced-ops.analysis.md) | ✅ Approved    | 2026-05-25   |
| R2 Quality Fixes       | [r2-quality-fixes.analysis.md](03-analysis/features/r2-quality-fixes.analysis.md) | ✅ Approved    | 2026-06-02   |
| Text Export            | [text-export.analysis.md](03-analysis/features/text-export.analysis.md)           | ✅ Approved    | 2026-06-02   |
| Page Merge / Split     | [page-merge-split.analysis.md](03-analysis/features/page-merge-split.analysis.md) | ✅ Approved    | 2026-06-02   |
| PDF Encryption         | [pdf-encryption.analysis.md](03-analysis/features/pdf-encryption.analysis.md) | ✅ Approved    | 2026-06-08   |

### Report (04-report/)

| Feature                 | Document                                       | Status         | Last Updated |
| ----------------------- | ---------------------------------------------- | -------------- | ------------ |
| Source Boundary Review  | [source-boundary.report.md](04-report/source-boundary.report.md) | 🔄 In Progress | 2026-03-31   |
| Page Advanced Ops       | [page-advanced-ops.report.md](04-report/features/page-advanced-ops.report.md) | ✅ Approved    | 2026-05-25   |
| R2 Quality Fixes        | [r2-quality-fixes.report.md](04-report/features/r2-quality-fixes.report.md) | ✅ Approved    | 2026-06-02   |
| Text Export             | [text-export.report.md](04-report/features/text-export.report.md) | ✅ Approved    | 2026-06-02   |
| Page Merge / Split      | [page-merge-split.report.md](04-report/features/page-merge-split.report.md) | ✅ Approved    | 2026-06-02   |
| PDF Encryption          | [pdf-encryption.report.md](04-report/features/pdf-encryption.report.md) | ✅ Approved    | 2026-06-08   |

---

## Legacy Documents (To Be Migrated)

These documents exist but use legacy format. They should be gradually migrated to the new PDCA structure:

- `PROJECT_STATUS.md` → Migrate to `03-analysis/features/current-state.analysis.md`
- `IMPROVEMENT_PLAN.md` → Migrate to `01-plan/features/improvement.plan.md`
- `NEXT_STEPS.md` → Migrate to `01-plan/features/next-steps.plan.md`

---

## Quick Links

### Active Development

- [CLAUDE.md](../CLAUDE.md) - Project configuration and rules
- [Current State Analysis](03-analysis/features/current-state.analysis.md) - Project status analysis
- [Source Boundary Report](04-report/source-boundary.report.md) - Source vs generated artifact boundary

### Planning

- [Project Status Plan](01-plan/features/project-status.plan.md) - Analysis and improvement planning

---

## Document Conventions

### File Naming

- Format: `{feature-name}.{type}.md`
- Example: `text-replacement.design.md`
- Use lowercase with hyphens for multi-word names

### Cross-References

Always link related documents:

```markdown
## Related Documents

- Plan: [feature.plan.md](../01-plan/features/feature.plan.md)
- Design: [feature.design.md](../02-design/features/feature.design.md)
- Analysis: [feature.analysis.md](../03-analysis/features/feature.analysis.md)
```

### Version History

Track changes within each document:

```markdown
## Version History

| Version | Date       | Changes       | Author |
| ------- | ---------- | ------------- | ------ |
| 1.0     | 2026-01-30 | Initial draft | Claude |
```
