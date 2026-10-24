# Feature: Opportunity Edit, Client Contacts & Team Assignment

## Summary
Extends the Opportunity Pipeline tab to support full editing of any existing opportunity
(including stage advancement), capturing key client-side contacts per company, and assigning
internal team members (drawn from the `employees` table) to each opportunity. Also fixes the
**budget burn bug**: previously, submitting a timesheet against a project did not reflect in the
Project Execution tab's burn bar — `timesheet_burn` is now computed dynamically from the
`timesheets` collection and overlaid on top of any manually set `budget_burn`.

## Scope
**IN scope:**
- Edit any opportunity field (client name, opp name, stage, cost, summary, team members)
- Stage can be manually advanced using a dropdown (RFI → RFP → Proposal; Won only via Promote button)
- `contacts` collection/table: store client-side contacts linked by `client_name`
- Per-opportunity "Contacts" button opens a modal filtered to that opportunity's client
- Add / view contacts from within the modal
- `team_member_ids` field on `opportunities`: array of employee IDs assigned to this opportunity
- Team member checkboxes populated from `employees` table in the edit modal
- Bug fix: `get_all_projects()` now returns `timesheet_burn` (computed) and `total_burn` fields
- Project burn bar uses `total_burn = budget_burn + timesheet_burn`

**OUT of scope:**
- Deleting opportunities or contacts
- Contact editing (future feature)
- Notifications when stage changes

## Data Model Changes

### Modified: `opportunities`
| New Field | Type | Notes |
|---|---|---|
| `team_member_ids` | JSON array (Firestore) / TEXT JSON string (SQLite) | Employee IDs assigned to this opp; default `[]` |

### New collection/table: `contacts`
| Field | Type | Notes |
|---|---|---|
| `id` | string (UUID4) | Primary key |
| `client_name` | string | Links to `opportunities.client_name` (denormalised) |
| `contact_name` | string | Full name |
| `role` | string | e.g. "CTO", "Procurement Lead" |
| `email` | string | |
| `phone` | string | |
| `created_at` | ISO 8601 timestamp | UTC |

### Modified: `projects` API response only (no schema change)
- `timesheet_burn` (float): computed as `SUM(hours_logged × billable_rate)` for timesheets with matching `project_id`
- `total_burn` (float): `budget_burn + timesheet_burn`

## API Changes
| Method | Route | Action |
|---|---|---|
| `PATCH` | `/api/opportunities/<id>` | Partial update of any opportunity fields (including stage) |
| `GET` | `/api/contacts` | List all contacts; optional `?client=<name>` filter |
| `POST` | `/api/contacts` | Create a new client contact |

## UI Changes
**Tab 0 — Opportunity Pipeline:**
- Opportunities table gets two new icon buttons per row:
  - ✏️ **Edit** → opens pre-populated Edit Opportunity modal
  - 👤 **Contacts** → opens Contacts modal filtered to that client
- Edit Opportunity modal: all fields + stage select + team member checkboxes
- Contacts modal: list of contacts for the client + inline add-contact form

**Tab 1 — Project Execution:**
- Budget burn progress bar now uses `proj.total_burn` (not `proj.budget_burn` alone)
- Tooltip / label shows breakdown: "Timesheet: $X + Other: $Y"

## Acceptance Criteria
- [ ] Edit button opens modal pre-filled with opportunity's current values
- [ ] Saving edit calls PATCH /api/opportunities/<id> and refreshes the table without reload
- [ ] Stage dropdown in edit modal contains all 5 stages; saving a stage change reflects immediately in the pill
- [ ] Team member checkboxes are populated from the employees list
- [ ] Contacts button opens modal showing only contacts for that client
- [ ] Adding a contact via the modal form calls POST /api/contacts and appends to the list
- [ ] Budget burn bar on project cards reflects timesheet entries (timesheet_burn included)
- [ ] `total_burn` label shows both components when both are non-zero
