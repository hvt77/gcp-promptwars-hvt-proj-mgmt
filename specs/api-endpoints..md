# API Endpoints Specification

## Web Routes (HTML Views)
- `GET /` : Main dashboard containing tabs for Pipeline, Execution, Timesheets, and Financials.
- `GET /api/seed` : Populates mock data for demonstration and testing.

## REST Endpoints (JSON Operations)
- `POST /api/opportunities` : Create a new RFI/RFP opportunity.
- `POST /api/projects` : Update project delivery health metrics.
- `POST /api/timesheets` : Submit weekly resource hours.
- `POST /api/invoices` : Record new invoice and payment status.

## REST Endpoints (Lifecycle Operations)

- `POST /api/opportunities/<id>/promote`
  - Action: Changes stage to `Won` and creates a linked Project record with inherited budget & architecture.
  - Response: `{ "status": "success", "project_id": "<new_project_id>", "message": "Opportunity promoted to active project." }`

- `POST /api/projects`
  - Action: Creates a project directly (standalone) or accepts payloads from the promotion pipeline.
  - Body params: `project_name`, `client_name`, `baseline_budget`, `opportunity_id` (optional).