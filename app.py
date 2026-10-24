"""
app.py — IT Project Lifecycle Copilot
Flask application with Firestore (or SQLite fallback) backend.
"""

import os
from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
import db

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN VIEW
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html", use_firestore=db.USE_FIRESTORE)


# ══════════════════════════════════════════════════════════════════════════════
# SEED ROUTE
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/seed")
def seed():
    try:
        result = db.seed_data()
        return jsonify({"status": "success", "seeded": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════════
# OPPORTUNITIES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/opportunities", methods=["GET"])
def get_opportunities():
    return jsonify(db.get_all_opportunities())


@app.route("/api/opportunities", methods=["POST"])
def create_opportunity():
    data = request.get_json(force=True)
    opp = db.create_opportunity(data)
    return jsonify(opp), 201


@app.route("/api/opportunities/<opp_id>", methods=["PATCH"])
def update_opportunity(opp_id):
    data = request.get_json(force=True)
    db.update_opportunity(opp_id, data)
    return jsonify({"status": "success"})


@app.route("/api/opportunities/<opp_id>/promote", methods=["POST"])
def promote_opportunity(opp_id):
    project, error = db.promote_opportunity(opp_id)
    if error:
        return jsonify({"status": "error", "message": error}), 400
    return jsonify({
        "status": "success",
        "project_id": project["id"],
        "message": "Opportunity promoted to active project.",
        "project": project,
    })


# ══════════════════════════════════════════════════════════════════════════════
# EMPLOYEES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/employees", methods=["GET"])
def get_employees():
    return jsonify(db.get_all_employees())


@app.route("/api/employees", methods=["POST"])
def create_employee():
    data = request.get_json(force=True)
    emp = db.create_employee(data)
    return jsonify(emp), 201


# ══════════════════════════════════════════════════════════════════════════════
# CONTACTS
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/contacts", methods=["GET"])
def get_contacts():
    client = request.args.get("client")
    return jsonify(db.get_all_contacts(client_name=client))


@app.route("/api/contacts", methods=["POST"])
def create_contact():
    data = request.get_json(force=True)
    contact = db.create_contact(data)
    return jsonify(contact), 201


# ══════════════════════════════════════════════════════════════════════════════
# PROJECTS
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/projects", methods=["GET"])
def get_projects():
    return jsonify(db.get_all_projects())


@app.route("/api/projects", methods=["POST"])
def create_project():
    data = request.get_json(force=True)
    project = db.create_project(data)
    return jsonify(project), 201


@app.route("/api/projects/<proj_id>", methods=["PATCH"])
def update_project(proj_id):
    data = request.get_json(force=True)
    db.update_project(proj_id, data)
    return jsonify({"status": "success"})


# ══════════════════════════════════════════════════════════════════════════════
# TIMESHEETS
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/timesheets", methods=["GET"])
def get_timesheets():
    return jsonify(db.get_all_timesheets())


@app.route("/api/timesheets", methods=["POST"])
def create_timesheet():
    data = request.get_json(force=True)
    ts = db.create_timesheet(data)
    return jsonify(ts), 201


# ══════════════════════════════════════════════════════════════════════════════
# INVOICES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/invoices", methods=["GET"])
def get_invoices():
    return jsonify(db.get_all_invoices())


@app.route("/api/invoices", methods=["POST"])
def create_invoice():
    data = request.get_json(force=True)
    inv = db.create_invoice(data)
    return jsonify(inv), 201


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY KPIs
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/api/kpis")
def get_kpis():
    opportunities = db.get_all_opportunities()
    projects = db.get_all_projects()
    timesheets = db.get_all_timesheets()
    invoices = db.get_all_invoices()

    pipeline_value = sum(o.get("estimated_cost", 0) for o in opportunities if o.get("stage") not in ("Won", "Lost"))
    active_revenue = sum(p.get("baseline_budget", 0) for p in projects)
    total_hours = sum(t.get("hours_logged", 0) for t in timesheets)
    outstanding = sum(i.get("invoice_amount", 0) for i in invoices if i.get("status") in ("Issued", "Overdue"))

    return jsonify({
        "pipeline_value": pipeline_value,
        "active_revenue": active_revenue,
        "total_hours": total_hours,
        "outstanding_invoices": outstanding,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
