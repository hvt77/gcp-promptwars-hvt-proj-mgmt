# Feature: Employee Management

## Summary
Introduces an `employees` collection/table to store the engineering company's own staff. Employees
are the shared source of truth for (a) team assignment on opportunities and (b) the resource name
dropdown on timesheets. Selecting an employee in the timesheet form auto-populates their default
billable rate. A "Team Directory" modal in the Timesheets tab lets the user add and view employees.

## Scope
**IN scope:**
- `employees` collection/table with name, role, department, default billable rate
- Timesheet form: `resource_name` text input replaced with `<select>` dropdown from employees
- Auto-fill `billable_rate` in timesheet form when an employee is selected
- "👥 Team Directory" button in the Timesheets tab header opens employee modal
- Employee modal: scrollable list of all employees + add-employee inline form
- Employees seeded alongside demo data (Alice Chen, Bob Ramesh, David Osei, Priya Nair)
- Employees list also drives the team member checkboxes in the Edit Opportunity modal (Feature 01)

**OUT of scope:**
- Employee editing or deletion
- Employee availability / capacity planning
- Authentication / employee login

## Data Model Changes

### New collection/table: `employees`
| Field | Type | Notes |
|---|---|---|
| `id` | string (UUID4) | Primary key |
| `name` | string | Full name; required |
| `role` | string | Job title e.g. "Cloud Architect" |
| `department` | string | e.g. "Delivery", "Platform" |
| `default_billable_rate` | float | USD per hour; pre-fills timesheet form |
| `created_at` | ISO 8601 timestamp | UTC |

## API Changes
| Method | Route | Action |
|---|---|---|
| `GET` | `/api/employees` | List all employees ordered by name |
| `POST` | `/api/employees` | Create a new employee |

## UI Changes
**Tab 2 — Timesheets:**
- "Resource Name" text input → `<select>` dropdown (options sourced from `/api/employees`)
- On employee selection: auto-fill the "Billable Rate" field with `employee.default_billable_rate`
- Header row gets "👥 Team Directory" button → opens Employee modal

**Employee modal:**
- Scrollable employee list (name, role, department, rate)
- Inline add-employee form at the bottom
- Submits via AJAX; new employee immediately appended to list and added to dropdown

## Acceptance Criteria
- [ ] `/api/employees` GET returns all employees in name order
- [ ] `/api/employees` POST creates and returns the new employee
- [ ] Timesheet form shows employee dropdown (not free-text input)
- [ ] Selecting employee auto-fills the billable rate field (editable override still possible)
- [ ] "Team Directory" button opens modal with employee list
- [ ] Adding employee via modal updates the dropdown immediately without page reload
- [ ] Seed data creates 4 employees matching existing seed timesheet resource names
