# System Architecture Specification: IT Project Lifecycle Copilot

## 1. Tech Stack & Constraints
- **Backend:** Python 3.11+, Flask 3.x
- **Database Abstraction:** Dual-driver (`db.py`) supporting Google Cloud Firestore in production and local SQLite for offline testing.
- **Frontend Styling:** Tailwind CSS (via CDN), Alpine.js 3.x (reactive UI state), Chart.js (financial charts).
- **Deployment Target:** Google Cloud Run (Containerized via Dockerfile exposing port 8080).
- **Cost Policy:** 100% Free Tier compliant. No paid third-party APIs.

## 2. Data Models (Firestore Collections & SQLite Tables)
- **collection: opportunities**
  - fields: `id` (string), `client_name` (string), `stage` (enum: RFI, RFP, Proposal, Won, Lost), `solution_summary` (string), `estimated_cost` (float), `created_at` (timestamp)
- **collection: projects**
  - fields: `id` (string), `project_name` (string), `health` (enum: Green, Amber, Red), `budget_burn` (float), `schedule_variance_days` (int), `updated_at` (timestamp)
- **collection: timesheets**
  - fields: `id` (string), `project_id` (string), `resource_name` (string), `week_ending` (string), `hours_logged` (float), `billable_rate` (float)
- **collection: invoices**
  - fields: `id` (string), `project_id` (string), `invoice_amount` (float), `status` (enum: Issued, Paid, Overdue), `issue_date` (string)

# Lifecycle Rules & Data Mapping

## Rule 1: Opportunity-to-Project Promotion (Auto-Flow)
- When an Opportunity's `stage` transitions to `Won`:
  1. Automatically generate a new record in `projects`.
  2. Map fields from Opportunity to Project:
     - `project_name` = `opportunity.client_name` + " - " + `opportunity.opportunity_name`
     - `opportunity_id` = `opportunity.id` (foreign key / lineage reference)
     - `baseline_budget` = `opportunity.estimated_cost`
     - `proposed_architecture` = `opportunity.solution_summary`
     - `health` = "Green" (default on creation)
     - `schedule_variance_days` = 0
     - `budget_burn` = 0.0
  3. Mark `opportunity.promoted_to_project` = `true` to avoid duplicate promotions.

## Rule 2: Standalone Project Creation
- A user can create a Project directly without an `opportunity_id`.
- Fields for Standalone Project:
  - `project_name` (required)
  - `client_name` (required)
  - `baseline_budget` (required)
  - `opportunity_id` = `null` (indicates direct entry / non-bid delivery)
  - `health` = "Green"
  - `schedule_variance_days` = 0