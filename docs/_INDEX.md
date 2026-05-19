# PDF Control - Document Index

> **Purpose**: Track all PDCA documents for the PDF Control project
>
> **Last Updated**: 2026-04-21

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

### Design (02-design/)

| Feature | Document | Status | Last Updated |
| ------- | -------- | ------ | ------------ |
| -       | -        | -      | -            |

### Analysis (03-analysis/)

| Feature                | Document                                                                    | Status         | Last Updated |
| ---------------------- | --------------------------------------------------------------------------- | -------------- | ------------ |
| Current State Analysis | [current-state.analysis.md](03-analysis/features/current-state.analysis.md) | 🔄 In Progress | 2026-01-30   |

### Report (04-report/)

| Feature                 | Document                                       | Status         | Last Updated |
| ----------------------- | ---------------------------------------------- | -------------- | ------------ |
| Source Boundary Review  | [source-boundary.report.md](04-report/source-boundary.report.md) | 🔄 In Progress | 2026-03-31   |

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
