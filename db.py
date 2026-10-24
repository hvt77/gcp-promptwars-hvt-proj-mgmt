"""
db.py — Dual-Driver Database Abstraction Layer
Checks for Firestore credentials; falls back to SQLite if not found.
"""

import os
import sqlite3
import uuid
from datetime import datetime, timezone

# ─── Driver Detection ──────────────────────────────────────────────────────────

def _detect_firestore():
    """Return True if Firestore credentials are available."""
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return True
    # Check GCP metadata server (running on Cloud Run / GCE)
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://metadata.google.internal/computeMetadata/v1/project/project-id",
            headers={"Metadata-Flavor": "Google"}
        )
        with urllib.request.urlopen(req, timeout=1) as resp:
            return resp.status == 200
    except Exception:
        return False

USE_FIRESTORE = _detect_firestore()

# ─── SQLite Helpers ────────────────────────────────────────────────────────────

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "database.sqlite")

def _get_sqlite_conn():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _init_sqlite():
    conn = _get_sqlite_conn()
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS opportunities (
            id TEXT PRIMARY KEY,
            client_name TEXT NOT NULL,
            opportunity_name TEXT NOT NULL,
            stage TEXT NOT NULL DEFAULT 'RFI',
            solution_summary TEXT,
            estimated_cost REAL DEFAULT 0.0,
            promoted_to_project INTEGER DEFAULT 0,
            team_member_ids TEXT DEFAULT '[]',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            project_name TEXT NOT NULL,
            client_name TEXT NOT NULL,
            opportunity_id TEXT,
            health TEXT NOT NULL DEFAULT 'Green',
            baseline_budget REAL DEFAULT 0.0,
            budget_burn REAL DEFAULT 0.0,
            schedule_variance_days INTEGER DEFAULT 0,
            proposed_architecture TEXT,
            risks TEXT,
            scope_changes TEXT,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS timesheets (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            resource_name TEXT NOT NULL,
            week_ending TEXT NOT NULL,
            hours_logged REAL DEFAULT 0.0,
            billable_rate REAL DEFAULT 0.0
        );

        CREATE TABLE IF NOT EXISTS invoices (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            invoice_number TEXT,
            invoice_amount REAL DEFAULT 0.0,
            status TEXT NOT NULL DEFAULT 'Issued',
            issue_date TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS employees (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT,
            department TEXT,
            default_billable_rate REAL DEFAULT 0.0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS contacts (
            id TEXT PRIMARY KEY,
            client_name TEXT NOT NULL,
            contact_name TEXT NOT NULL,
            role TEXT,
            email TEXT,
            phone TEXT,
            created_at TEXT NOT NULL
        );
    """)
    # Migrate existing opportunities table if team_member_ids column missing
    try:
        cur.execute("ALTER TABLE opportunities ADD COLUMN team_member_ids TEXT DEFAULT '[]'")
        conn.commit()
    except Exception:
        pass
    conn.commit()
    conn.close()

# ─── Firestore Client ──────────────────────────────────────────────────────────

_firestore_client = None

def _get_fs():
    global _firestore_client
    if _firestore_client is None:
        from google.cloud import firestore
        project_id = os.environ.get("GCP_PROJECT_ID")
        _firestore_client = firestore.Client(project=project_id) if project_id else firestore.Client()
    return _firestore_client


# ─── Utility ───────────────────────────────────────────────────────────────────

def _now_str():
    return datetime.now(timezone.utc).isoformat()

def _new_id():
    return str(uuid.uuid4())

def _row_to_dict(row):
    return dict(row) if row else None

def _rows_to_list(rows):
    return [dict(r) for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# OPPORTUNITIES
# ══════════════════════════════════════════════════════════════════════════════

def get_all_opportunities():
    if USE_FIRESTORE:
        docs = _get_fs().collection("opportunities").order_by("created_at", direction="DESCENDING").stream()
        return [{"id": d.id, **d.to_dict()} for d in docs]
    else:
        import json as _json
        conn = _get_sqlite_conn()
        rows = conn.execute("SELECT * FROM opportunities ORDER BY created_at DESC").fetchall()
        conn.close()
        result = _rows_to_list(rows)
        for r in result:
            if isinstance(r.get("team_member_ids"), str):
                try:
                    r["team_member_ids"] = _json.loads(r["team_member_ids"])
                except Exception:
                    r["team_member_ids"] = []
        return result


def create_opportunity(data: dict):
    import json as _json
    opp_id = _new_id()
    record = {
        "id": opp_id,
        "client_name": data.get("client_name", ""),
        "opportunity_name": data.get("opportunity_name", ""),
        "stage": data.get("stage", "RFI"),
        "solution_summary": data.get("solution_summary", ""),
        "estimated_cost": float(data.get("estimated_cost", 0)),
        "promoted_to_project": False,
        "team_member_ids": data.get("team_member_ids", []),
        "created_at": _now_str(),
    }
    if USE_FIRESTORE:
        _get_fs().collection("opportunities").document(opp_id).set(record)
    else:
        conn = _get_sqlite_conn()
        conn.execute(
            "INSERT INTO opportunities VALUES (:id,:client_name,:opportunity_name,:stage,"
            ":solution_summary,:estimated_cost,:promoted_to_project,:team_member_ids,:created_at)",
            {**record, "promoted_to_project": 0, "team_member_ids": _json.dumps(record["team_member_ids"])}
        )
        conn.commit()
        conn.close()
    return record


def update_opportunity(opp_id: str, data: dict):
    import json as _json
    if USE_FIRESTORE:
        update = {k: v for k, v in data.items()}
        _get_fs().collection("opportunities").document(opp_id).update(update)
    else:
        if "team_member_ids" in data and isinstance(data["team_member_ids"], list):
            data = {**data, "team_member_ids": _json.dumps(data["team_member_ids"])}
        conn = _get_sqlite_conn()
        fields = ", ".join(f"{k}=:{k}" for k in data.keys())
        conn.execute(f"UPDATE opportunities SET {fields} WHERE id=:id", {**data, "id": opp_id})
        conn.commit()
        conn.close()


def promote_opportunity(opp_id: str):
    """Promote opportunity to Won stage and auto-create a Project."""
    if USE_FIRESTORE:
        fs = _get_fs()
        opp_ref = fs.collection("opportunities").document(opp_id)
        opp = opp_ref.get()
        if not opp.exists:
            return None, "Opportunity not found"
        opp_data = opp.to_dict()
        if opp_data.get("promoted_to_project"):
            return None, "Already promoted"
        # Mark Won + promoted
        opp_ref.update({"stage": "Won", "promoted_to_project": True})
        # Create project
        project = _build_project_from_opp({**opp_data, "id": opp_id})
        proj_id = project["id"]
        fs.collection("projects").document(proj_id).set(project)
        return project, None
    else:
        conn = _get_sqlite_conn()
        row = conn.execute("SELECT * FROM opportunities WHERE id=?", (opp_id,)).fetchone()
        if not row:
            conn.close()
            return None, "Opportunity not found"
        opp_data = dict(row)
        if opp_data.get("promoted_to_project"):
            conn.close()
            return None, "Already promoted"
        conn.execute("UPDATE opportunities SET stage='Won', promoted_to_project=1 WHERE id=?", (opp_id,))
        project = _build_project_from_opp(opp_data)
        conn.execute(
            "INSERT INTO projects VALUES (:id,:project_name,:client_name,:opportunity_id,:health,"
            ":baseline_budget,:budget_burn,:schedule_variance_days,:proposed_architecture,:risks,:scope_changes,:updated_at)",
            project
        )
        conn.commit()
        conn.close()
        return project, None


def _build_project_from_opp(opp: dict) -> dict:
    return {
        "id": _new_id(),
        "project_name": f"{opp.get('client_name','')} - {opp.get('opportunity_name','')}",
        "client_name": opp.get("client_name", ""),
        "opportunity_id": opp.get("id"),
        "health": "Green",
        "baseline_budget": float(opp.get("estimated_cost", 0)),
        "budget_burn": 0.0,
        "schedule_variance_days": 0,
        "proposed_architecture": opp.get("solution_summary", ""),
        "risks": "",
        "scope_changes": "",
        "updated_at": _now_str(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# PROJECTS
# ══════════════════════════════════════════════════════════════════════════════

def _compute_timesheet_burn(project_id: str) -> float:
    """Compute SUM(hours_logged * billable_rate) for a project from timesheets."""
    if USE_FIRESTORE:
        docs = _get_fs().collection("timesheets").where("project_id", "==", project_id).stream()
        return sum(d.to_dict().get("hours_logged", 0) * d.to_dict().get("billable_rate", 0) for d in docs)
    else:
        conn = _get_sqlite_conn()
        row = conn.execute(
            "SELECT COALESCE(SUM(hours_logged * billable_rate), 0) FROM timesheets WHERE project_id=?",
            (project_id,)
        ).fetchone()
        conn.close()
        return float(row[0]) if row else 0.0


def get_all_projects():
    if USE_FIRESTORE:
        docs = _get_fs().collection("projects").order_by("updated_at", direction="DESCENDING").stream()
        projects = [{"id": d.id, **d.to_dict()} for d in docs]
    else:
        conn = _get_sqlite_conn()
        rows = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC").fetchall()
        conn.close()
        projects = _rows_to_list(rows)
    for p in projects:
        ts_burn = _compute_timesheet_burn(p["id"])
        p["timesheet_burn"] = ts_burn
        p["total_burn"] = float(p.get("budget_burn", 0)) + ts_burn
    return projects


def create_project(data: dict):
    proj_id = _new_id()
    record = {
        "id": proj_id,
        "project_name": data.get("project_name", ""),
        "client_name": data.get("client_name", ""),
        "opportunity_id": data.get("opportunity_id", None),
        "health": data.get("health", "Green"),
        "baseline_budget": float(data.get("baseline_budget", 0)),
        "budget_burn": float(data.get("budget_burn", 0)),
        "schedule_variance_days": int(data.get("schedule_variance_days", 0)),
        "proposed_architecture": data.get("proposed_architecture", ""),
        "risks": data.get("risks", ""),
        "scope_changes": data.get("scope_changes", ""),
        "updated_at": _now_str(),
    }
    if USE_FIRESTORE:
        _get_fs().collection("projects").document(proj_id).set(record)
    else:
        conn = _get_sqlite_conn()
        conn.execute(
            "INSERT INTO projects VALUES (:id,:project_name,:client_name,:opportunity_id,:health,"
            ":baseline_budget,:budget_burn,:schedule_variance_days,:proposed_architecture,:risks,:scope_changes,:updated_at)",
            record
        )
        conn.commit()
        conn.close()
    return record


def update_project(proj_id: str, data: dict):
    data["updated_at"] = _now_str()
    if USE_FIRESTORE:
        _get_fs().collection("projects").document(proj_id).update(data)
    else:
        conn = _get_sqlite_conn()
        fields = ", ".join(f"{k}=:{k}" for k in data.keys())
        conn.execute(f"UPDATE projects SET {fields} WHERE id=:id", {**data, "id": proj_id})
        conn.commit()
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# TIMESHEETS
# ══════════════════════════════════════════════════════════════════════════════

def get_all_timesheets():
    if USE_FIRESTORE:
        docs = _get_fs().collection("timesheets").stream()
        return [{"id": d.id, **d.to_dict()} for d in docs]
    else:
        conn = _get_sqlite_conn()
        rows = conn.execute("SELECT * FROM timesheets ORDER BY week_ending DESC").fetchall()
        conn.close()
        return _rows_to_list(rows)


def create_timesheet(data: dict):
    ts_id = _new_id()
    record = {
        "id": ts_id,
        "project_id": data.get("project_id", ""),
        "resource_name": data.get("resource_name", ""),
        "week_ending": data.get("week_ending", ""),
        "hours_logged": float(data.get("hours_logged", 0)),
        "billable_rate": float(data.get("billable_rate", 0)),
    }
    if USE_FIRESTORE:
        _get_fs().collection("timesheets").document(ts_id).set(record)
    else:
        conn = _get_sqlite_conn()
        conn.execute(
            "INSERT INTO timesheets VALUES (:id,:project_id,:resource_name,:week_ending,:hours_logged,:billable_rate)",
            record
        )
        conn.commit()
        conn.close()
    return record


# ══════════════════════════════════════════════════════════════════════════════
# INVOICES
# ══════════════════════════════════════════════════════════════════════════════

def get_all_invoices():
    if USE_FIRESTORE:
        docs = _get_fs().collection("invoices").stream()
        return [{"id": d.id, **d.to_dict()} for d in docs]
    else:
        conn = _get_sqlite_conn()
        rows = conn.execute("SELECT * FROM invoices ORDER BY issue_date DESC").fetchall()
        conn.close()
        return _rows_to_list(rows)


def create_invoice(data: dict):
    inv_id = _new_id()
    record = {
        "id": inv_id,
        "project_id": data.get("project_id", ""),
        "invoice_number": data.get("invoice_number", f"INV-{inv_id[:8].upper()}"),
        "invoice_amount": float(data.get("invoice_amount", 0)),
        "status": data.get("status", "Issued"),
        "issue_date": data.get("issue_date", datetime.now().strftime("%Y-%m-%d")),
    }
    if USE_FIRESTORE:
        _get_fs().collection("invoices").document(inv_id).set(record)
    else:
        conn = _get_sqlite_conn()
        conn.execute(
            "INSERT INTO invoices VALUES (:id,:project_id,:invoice_number,:invoice_amount,:status,:issue_date)",
            record
        )
        conn.commit()
        conn.close()
    return record


# ══════════════════════════════════════════════════════════════════════════════
# EMPLOYEES
# ══════════════════════════════════════════════════════════════════════════════

def get_all_employees():
    if USE_FIRESTORE:
        docs = _get_fs().collection("employees").order_by("name").stream()
        return [{"id": d.id, **d.to_dict()} for d in docs]
    else:
        conn = _get_sqlite_conn()
        rows = conn.execute("SELECT * FROM employees ORDER BY name").fetchall()
        conn.close()
        return _rows_to_list(rows)


def create_employee(data: dict):
    emp_id = _new_id()
    record = {
        "id": emp_id,
        "name": data.get("name", ""),
        "role": data.get("role", ""),
        "department": data.get("department", ""),
        "default_billable_rate": float(data.get("default_billable_rate", 0)),
        "created_at": _now_str(),
    }
    if USE_FIRESTORE:
        _get_fs().collection("employees").document(emp_id).set(record)
    else:
        conn = _get_sqlite_conn()
        conn.execute(
            "INSERT INTO employees VALUES (:id,:name,:role,:department,:default_billable_rate,:created_at)",
            record
        )
        conn.commit()
        conn.close()
    return record


# ══════════════════════════════════════════════════════════════════════════════
# CONTACTS
# ══════════════════════════════════════════════════════════════════════════════

def get_all_contacts(client_name: str = None):
    if USE_FIRESTORE:
        q = _get_fs().collection("contacts")
        if client_name:
            q = q.where("client_name", "==", client_name)
        docs = q.stream()
        return [{"id": d.id, **d.to_dict()} for d in docs]
    else:
        conn = _get_sqlite_conn()
        if client_name:
            rows = conn.execute("SELECT * FROM contacts WHERE client_name=? ORDER BY created_at DESC", (client_name,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM contacts ORDER BY created_at DESC").fetchall()
        conn.close()
        return _rows_to_list(rows)


def create_contact(data: dict):
    c_id = _new_id()
    record = {
        "id": c_id,
        "client_name": data.get("client_name", ""),
        "contact_name": data.get("contact_name", ""),
        "role": data.get("role", ""),
        "email": data.get("email", ""),
        "phone": data.get("phone", ""),
        "created_at": _now_str(),
    }
    if USE_FIRESTORE:
        _get_fs().collection("contacts").document(c_id).set(record)
    else:
        conn = _get_sqlite_conn()
        conn.execute(
            "INSERT INTO contacts VALUES (:id,:client_name,:contact_name,:role,:email,:phone,:created_at)",
            record
        )
        conn.commit()
        conn.close()
    return record


# ══════════════════════════════════════════════════════════════════════════════
# SEED DATA
# ══════════════════════════════════════════════════════════════════════════════

def seed_data():
    """Populate sample data for demo/testing."""
    # ── Employees ──
    emp_alice = create_employee({"name": "Alice Chen",  "role": "Cloud Architect",    "department": "Delivery",  "default_billable_rate": 185})
    emp_bob   = create_employee({"name": "Bob Ramesh",  "role": "Backend Engineer",   "department": "Delivery",  "default_billable_rate": 160})
    emp_david = create_employee({"name": "David Osei",  "role": "Data Engineer",      "department": "Platform",  "default_billable_rate": 175})
    emp_priya = create_employee({"name": "Priya Nair",  "role": "DevOps Engineer",    "department": "Platform",  "default_billable_rate": 155})

    # ── Opportunities ──
    opp1 = create_opportunity({
        "client_name": "Accenture Federal",
        "opportunity_name": "Cloud Migration Platform",
        "stage": "RFP",
        "solution_summary": "Multi-cloud migration using GKE + Anthos with zero-downtime cutover strategy.",
        "estimated_cost": 485000.0,
        "team_member_ids": [emp_alice["id"], emp_bob["id"]],
    })
    opp2 = create_opportunity({
        "client_name": "Deutsche Bank",
        "opportunity_name": "Real-Time Risk Analytics",
        "stage": "Proposal",
        "solution_summary": "BigQuery-powered streaming risk dashboard with sub-second latency via Pub/Sub + Dataflow.",
        "estimated_cost": 320000.0,
        "team_member_ids": [emp_david["id"], emp_priya["id"]],
    })

    # ── Active Projects (direct creation) ──
    proj1 = create_project({
        "project_name": "HSBC - Core Banking Modernisation",
        "client_name": "HSBC",
        "health": "Amber",
        "baseline_budget": 750000.0,
        "budget_burn": 312500.0,
        "schedule_variance_days": -5,
        "proposed_architecture": "Microservices migration on GCP using Cloud Run + Spanner for ACID transactions.",
        "risks": "Legacy COBOL dependency; vendor lock-in risk on payment gateway.",
        "scope_changes": "Added PCI-DSS compliance module (+$45k).",
    })
    proj2 = create_project({
        "project_name": "Telstra - IoT Data Platform",
        "client_name": "Telstra",
        "health": "Green",
        "baseline_budget": 560000.0,
        "budget_burn": 168000.0,
        "schedule_variance_days": 2,
        "proposed_architecture": "Pub/Sub ingestion → Dataflow transformation → BigQuery analytics warehouse.",
        "risks": "Network partition handling for edge devices in remote regions.",
        "scope_changes": "",
    })

    # ── Timesheets ──
    for proj, entries in [
        (proj1, [
            ("Alice Chen", "2026-10-17", 40, 185),
            ("Bob Ramesh", "2026-10-17", 38, 160),
            ("Alice Chen", "2026-10-10", 40, 185),
        ]),
        (proj2, [
            ("David Osei", "2026-10-17", 36, 175),
            ("Priya Nair", "2026-10-17", 40, 155),
        ]),
    ]:
        for (res, week, hrs, rate) in entries:
            create_timesheet({
                "project_id": proj["id"],
                "resource_name": res,
                "week_ending": week,
                "hours_logged": hrs,
                "billable_rate": rate,
            })

    # ── Invoices ──
    for proj, invs in [
        (proj1, [
            ("INV-HSBC-001", 187500.0, "Paid", "2026-08-01"),
            ("INV-HSBC-002", 125000.0, "Issued", "2026-10-01"),
        ]),
        (proj2, [
            ("INV-TLS-001", 140000.0, "Paid", "2026-09-15"),
            ("INV-TLS-002", 100000.0, "Overdue", "2026-09-30"),
        ]),
    ]:
        for (inv_num, amount, status, date) in invs:
            create_invoice({
                "project_id": proj["id"],
                "invoice_number": inv_num,
                "invoice_amount": amount,
                "status": status,
                "issue_date": date,
            })

    return {"opportunities": 2, "projects": 2, "timesheets": 5, "invoices": 4, "employees": 4}


# ─── Initialise SQLite on import ───────────────────────────────────────────────
if not USE_FIRESTORE:
    _init_sqlite()
