# Feature Specs

Each file in this directory describes **one discrete feature** to be added to the IT Project
Lifecycle Copilot. Files here are created either by the user (as a prompt brief) or auto-generated
by the AI after a feature discussion.

## Naming Convention

```
<NN>-<slug>.md

e.g.
  01-timesheet-approvals.md
  02-invoice-pdf-export.md
  03-manager-dashboard.md
```

The numeric prefix keeps files in creation order. Use two digits so they sort correctly.

## Required Sections in Each Feature Spec

```markdown
# Feature: <Name>

## Summary
One paragraph describing what this feature does and why it exists.

## Scope
- What is IN scope for this feature
- What is explicitly OUT of scope

## Data Model Changes
Any new fields or collections required (must remain consistent with constitution.md §5).

## API Changes
New or modified routes (must remain consistent with constitution.md §7).

## UI Changes
Which tab(s) are affected and what the new UI elements look like.

## Acceptance Criteria
- [ ] Bullet-point checklist of what "done" looks like
```

## Process

1. User describes a new feature in the chat.
2. AI creates `specs/features/NN-feature-name.md` capturing the agreed design.
3. AI implements against the spec, reading `specs/constitution.md` to stay compliant.
4. Spec file remains on disk as a permanent decision record.
5. Future sessions re-read relevant feature specs before touching related code.
