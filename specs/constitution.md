# Project Constitution — IT Project Lifecycle Copilot
> **Status: AUTHORITATIVE & STABLE**
> This document is the single source of truth for this project. Read it at the start of every
> session before writing or modifying any code. Do not contradict anything in this document
> without explicit user approval. New features are specified in `specs/features/*.md` and must
> remain consistent with the rules, models, and constraints defined here.

---

## 1. Project Identity

| Property | Value |
|---|---|
| **Application Name** | IT Project Lifecycle Copilot |
| **Target User** | IT Engineering Director |
| **Purpose** | Manage the full IT project lifecycle — from RFP/Opportunity Tracking through Project Execution, Weekly Timesheets, and Invoicing — in a single executive dashboard. |
| **Deployment Target** | Google Cloud Run (containerised, port 8080) |
| **Primary Database** | Google Cloud Firestore |
| **Fallback Database** | Local SQLite (`database.sqlite`) — activated automatically when Firestore credentials are absent |
| **Cost Policy** | **100% Free Tier compliant.** No paid third-party APIs, no paid SaaS services, no external databases outside Firestore and local SQLite. |

---

## 2. Tech Stack — FROZEN

These choices are fixed. Do not substitute, add, or remove without explicit user approval.

### Backend
- **Runtime:** Python 3.11+
- **Framework:** Flask 3.x
- **WSGI Server (prod):** Gunicorn (single worker, 8 threads, `--timeout 0`)
- **DB Abstraction:** `db.py` — dual-driver module (Firestore / SQLite, auto-detected)
- **Config:** `python-dotenv` for local `.env` loading

### Frontend
- **CSS Framework:** Tailwind CSS via CDN (`https://cdn.tailwindcss.com`) — **no build step**
- **Reactivity:** Alpine.js 3.x via CDN (`defer` loaded)
- **Charts:** Chart.js 4.x via CDN
- **Fonts:** Google Fonts — Inter (weights 300–800)
- **No React, Vue, or any other JS framework.** Keep the frontend in a single `templates/index.html`.

### Infrastructure
- **Container:** Dockerfile — base image `python:3.11-slim`, exposes port 8080
- **Cloud:** Google Cloud Run (managed, serverless)
- **No Cloud SQL, no Redis, no external message queues.**

---

## 3. Repository Structure

```
/
├── app.py                  # Flask app — routes only, no DB logic
├── db.py                   # All database operations — Firestore + SQLite dual-driver
├── requirements.txt        # Pinned Python dependencies
├── Dockerfile              # Cloud Run container definition
├── .env.example            # Documented environment variables (never commit .env)
├── database.sqlite         # Auto-created locally (gitignored)
├── templates/
│   └── index.html          # Single-page dashboard — all tabs, all UI
└── specs/
    ├── constitution.md     # THIS FILE — master source of truth
    ├── system-architecture.md   # Original spec (superseded by this document)
    ├── api-endpoints..md        # Original spec (superseded by this document)
    ├── ui-layout.md             # Original spec (currently empty)
    └── features/           # One .md file per new feature, added over time
```

> **Rule:** `app.py` must never contain direct SQL or Firestore SDK calls. All data access goes
> through `db.py`. This enforces the dual-driver abstraction cleanly.

---

## 4. Database Driver Detection — INVARIANT

`db.py` detects which driver to use at **import time** using this exact priority order:

1. **Check `GOOGLE_APPLICATION_CREDENTIALS`** env var → if set and non-empty, use Firestore.
2. **Probe GCP Metadata Server** at `http://metadata.google.internal/computeMetadata/v1/project/project-id` with `Metadata-Flavor: Google` header and a 1-second timeout → if HTTP 200, use Firestore (running on Cloud Run/GCE).
3. **Otherwise** → use SQLite, auto-creating `database.sqlite` with `_init_sqlite()`.

The boolean `db.USE_FIRESTORE` is set once at module load. It is passed to `templates/index.html`
via Flask's `render_template` to display the correct indicator badge in the UI.

---

## 5. Data Models — CANONICAL SCHEMA

These are the authoritative field definitions. Both Firestore collections and SQLite tables must
mirror this schema exactly. New features that require new fields must add them to both drivers.

### 5.1 `opportunities` collection / table

| Field | Type | Notes |
|---|---|---|
| `id` | string (UUID4) | Primary key |
| `client_name` | string | Required |
| `opportunity_name` | string | Required |
| `stage` | enum | `RFI` · `RFP` · `Proposal` · `Won` · `Lost` |
| `solution_summary` | string | Architecture / approach description |
| `estimated_cost` | float | Estimated deal value in USD |
| `promoted_to_project` | boolean | `false` by default; set `true` after promotion to prevent duplicates |
| `created_at` | ISO 8601 timestamp string | UTC, set on creation |

### 5.2 `projects` collection / table

| Field | Type | Notes |
|---|---|---|
| `id` | string (UUID4) | Primary key |
| `project_name` | string | Derived on promotion: `"<client_name> - <opportunity_name>"` |
| `client_name` | string | Required |
| `opportunity_id` | string \| null | Foreign key to `opportunities.id`; `null` for standalone projects |
| `health` | enum | `Green` · `Amber` · `Red` |
| `baseline_budget` | float | Total approved budget in USD |
| `budget_burn` | float | Amount spent to date |
| `schedule_variance_days` | integer | Negative = ahead, positive = behind |
| `proposed_architecture` | string | Inherited from opportunity or entered directly |
| `risks` | string | Free-text risk log |
| `scope_changes` | string | Free-text scope change notes |
| `updated_at` | ISO 8601 timestamp string | UTC, updated on every write |

### 5.3 `timesheets` collection / table

| Field | Type | Notes |
|---|---|---|
| `id` | string (UUID4) | Primary key |
| `project_id` | string | Foreign key to `projects.id` |
| `resource_name` | string | Full name of the resource |
| `week_ending` | string | Date string in `YYYY-MM-DD` format |
| `hours_logged` | float | Hours worked in that week |
| `billable_rate` | float | USD per hour |

### 5.4 `invoices` collection / table

| Field | Type | Notes |
|---|---|---|
| `id` | string (UUID4) | Primary key |
| `project_id` | string | Foreign key to `projects.id` |
| `invoice_number` | string | User-provided or auto-generated `INV-<8-char-id>` |
| `invoice_amount` | float | Invoice value in USD |
| `status` | enum | `Issued` · `Paid` · `Overdue` |
| `issue_date` | string | Date string in `YYYY-MM-DD` format |

---

## 6. Lifecycle Rules — INVARIANT

### Rule 1: Opportunity → Project Promotion
Triggered by `POST /api/opportunities/<id>/promote`.

1. Verify opportunity exists; return `400` if not found.
2. Check `promoted_to_project == false`; return `400` with message `"Already promoted"` if true.
3. Set `opportunity.stage = "Won"` and `opportunity.promoted_to_project = true`.
4. Auto-create a new `projects` record with the following field mapping:

   | Project Field | Source |
   |---|---|
   | `project_name` | `opportunity.client_name + " - " + opportunity.opportunity_name` |
   | `client_name` | `opportunity.client_name` |
   | `opportunity_id` | `opportunity.id` |
   | `baseline_budget` | `opportunity.estimated_cost` |
   | `proposed_architecture` | `opportunity.solution_summary` |
   | `health` | `"Green"` (hardcoded default) |
   | `schedule_variance_days` | `0` |
   | `budget_burn` | `0.0` |

5. Return `{ "status": "success", "project_id": "<new_id>", "message": "Opportunity promoted to active project.", "project": { ...full project record } }`.
6. **UI behaviour:** On success, the frontend auto-navigates to the Execution tab (`activeTab = 1`).

### Rule 2: Standalone Project Creation
Triggered by `POST /api/projects` with no `opportunity_id` in the body.

- Required fields: `project_name`, `client_name`, `baseline_budget`
- `opportunity_id` defaults to `null`
- `health` defaults to `"Green"`, `schedule_variance_days` to `0`, `budget_burn` to `0.0`

---

## 7. API Contract — COMPLETE ROUTE TABLE

All JSON endpoints return `Content-Type: application/json`. Error responses use `{ "status": "error", "message": "..." }`.

| Method | Route | Description |
|---|---|---|
| `GET` | `/` | Render `templates/index.html` (passes `use_firestore` bool) |
| `GET` | `/api/seed` | Populate demo data (additive; idempotent per session) |
| `GET` | `/api/kpis` | Return 4 aggregate KPI values |
| `GET` | `/api/opportunities` | List all opportunities, ordered by `created_at DESC` |
| `POST` | `/api/opportunities` | Create opportunity; body: all `opportunities` fields except `id`, `promoted_to_project`, `created_at` |
| `POST` | `/api/opportunities/<id>/promote` | Promote opportunity → project (see Lifecycle Rule 1) |
| `GET` | `/api/projects` | List all projects, ordered by `updated_at DESC` |
| `POST` | `/api/projects` | Create project (standalone or from promotion pipeline) |
| `PATCH` | `/api/projects/<id>` | Partial update of any project fields |
| `GET` | `/api/timesheets` | List all timesheets, ordered by `week_ending DESC` |
| `POST` | `/api/timesheets` | Log a timesheet entry |
| `GET` | `/api/invoices` | List all invoices, ordered by `issue_date DESC` |
| `POST` | `/api/invoices` | Record an invoice |

### `/api/kpis` Response Shape
```json
{
  "pipeline_value":       "<sum of estimated_cost for non-Won/Lost opportunities>",
  "active_revenue":       "<sum of baseline_budget across all projects>",
  "total_hours":          "<sum of hours_logged across all timesheets>",
  "outstanding_invoices": "<sum of invoice_amount where status is Issued or Overdue>"
}
```

---

## 8. UI Architecture & Design System

### 8.1 Structure
- **Single file:** `templates/index.html` — all HTML, CSS (via Tailwind), and JavaScript (Alpine.js).
- **No separate JS files, no separate CSS files** unless a feature spec explicitly requires it.
- **One Alpine.js root component** defined as `x-data="app()"` on `<body>`. All state lives here.
- **All API calls use `fetch()`** — no jQuery, no Axios. Forms never do a full page reload.

### 8.2 Design Language — FROZEN
| Token | Value |
|---|---|
| Background | `#0b1120` (slate-950) |
| Surface (cards) | `rgba(255,255,255,0.04)` with `backdrop-filter: blur(12px)` — glassmorphism |
| Border | `rgba(255,255,255,0.08)` |
| Primary accent | Indigo-to-violet gradient `#6366f1 → #8b5cf6` |
| Success / Paid | Emerald `#10b981` / `#34d399` |
| Warning / Amber | Amber `#f59e0b` / `#fbbf24` |
| Danger / Overdue | Red `#ef4444` / `#f87171` |
| Body text | `#e2e8f0` (slate-200) |
| Muted text | `#94a3b8` / `#64748b` (slate-400/500) |
| Font | Inter (Google Fonts), weights 300–800 |

### 8.3 Component Conventions
- **KPI cards** — 4 across the top, always live-updated via `/api/kpis` after every write.
- **Status pills** — `text-xs font-semibold px-2.5 py-1 rounded-full` with coloured bg/border matching the design token table above.
- **Tables** — class `data-table`; `th` uppercase tracking-widest 0.72rem; `td` 0.845rem with hover row highlight.
- **Forms** — class `form-input` (dark glass input) + class `form-label`; submit via Alpine `@submit.prevent`.
- **Primary button** — class `btn-primary` (indigo-violet gradient, hover lift + shadow).
- **Toast notifications** — single `#toast` element, shown by calling `this.toast(msg, type)` in Alpine. Auto-dismisses after 3.2 s.
- **Modals** — `.modal-overlay` full-screen fixed backdrop + `.modal-box` centred panel; close on backdrop click (`@click.self`).
- **Charts** — Chart.js instances stored on `this.budgetChart` / `this.invoiceChart`; always `.destroy()` before re-drawing.

### 8.4 The 4-Tab Layout

| Tab Index | Emoji | Label | Contents |
|---|---|---|---|
| `0` | 🎯 | Opportunity Pipeline | RFP form + pipeline stage bar + opportunities table with Promote button |
| `1` | 🚀 | Project Execution | Project health cards grid + direct-create modal + Budget vs. Burn bar chart |
| `2` | ⏱ | Timesheets | Log hours form + timesheet log table + billable total footer |
| `3` | 💰 | Financials | Record invoice form + gross margin summary cards + invoice register table + revenue doughnut chart |

---

## 9. Seed Data Contract

`GET /api/seed` (implemented in `db.py::seed_data()`) must always create:

| Entity | Count | Records |
|---|---|---|
| Opportunities | 2 | "Accenture Federal — Cloud Migration Platform" (RFP, $485k) · "Deutsche Bank — Real-Time Risk Analytics" (Proposal, $320k) |
| Projects | 2 | "HSBC — Core Banking Modernisation" (Amber, $750k budget, $312.5k burn) · "Telstra — IoT Data Platform" (Green, $560k budget, $168k burn) |
| Timesheets | 5 | Entries for Alice Chen, Bob Ramesh (on HSBC) and David Osei, Priya Nair (on Telstra) |
| Invoices | 4 | 2 per project — HSBC: INV-HSBC-001 (Paid), INV-HSBC-002 (Issued) · Telstra: INV-TLS-001 (Paid), INV-TLS-002 (Overdue) |

Seed is **additive** (not idempotent) — calling it twice doubles records. This is acceptable for a demo tool. If idempotency is needed, add a feature spec.

---

## 10. Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Optional | Absolute path to GCP service account JSON key. If set, activates Firestore driver. |
| `GCP_PROJECT_ID` | Optional | GCP project ID. Passed to `firestore.Client(project=...)`. Auto-detected on Cloud Run if omitted. |
| `FLASK_SECRET_KEY` | Recommended | Flask session secret. Must be changed in production. |
| `PORT` | Auto (Cloud Run) | Port to bind. Defaults to `8080`. |

---

## 11. What This Document Does NOT Govern

The following are intentionally left to individual feature specs (`specs/features/*.md`):

- Specific UI copy, labels, placeholder text
- Business logic for features not yet built (approvals, notifications, exports, auth, etc.)
- Any third-party integration not already in the stack
- Visual polish tweaks (spacing, font sizes) that don't break the design token contract
