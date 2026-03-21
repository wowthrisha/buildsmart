from flask import Blueprint, render_template, jsonify, request
from services.compliance_service import ComplianceService

compliance_bp = Blueprint("compliance", __name__, url_prefix="/compliance")


# ── GET /compliance/<project_id> ─────────────────────────────────────────────
@compliance_bp.route("/<int:project_id>")
def compliance_report(project_id):
    """Returns full compliance JSON for a project."""
    report = ComplianceService.check_project_compliance(project_id)
    return jsonify(report)


# ── GET /compliance/missing/<project_id> ─────────────────────────────────────
@compliance_bp.route("/missing/<int:project_id>")
def missing_documents(project_id):
    """Returns only the list of missing/outdated document types."""
    ComplianceService.seed_compliance_requirements(project_id)
    missing = ComplianceService.get_missing_documents(project_id)
    return jsonify({"project_id": project_id, "missing": missing})


# ── POST /compliance/seed-demo ────────────────────────────────────────────────
@compliance_bp.route("/seed-demo", methods=["POST"])
def seed_demo():
    """
    Seeds compliance requirements for a given project_id.
    Expects JSON body: { "project_id": <int> }
    """
    data = request.get_json(silent=True) or {}
    project_id = data.get("project_id")
    if not project_id:
        return jsonify({"error": "project_id is required"}), 400
    ComplianceService.seed_compliance_requirements(project_id)
    return jsonify({"success": True, "project_id": project_id})


# ── GET /compliance/dashboard/<project_id> ────────────────────────────────────
@compliance_bp.route("/dashboard/<int:project_id>")
def dashboard(project_id):
    """Renders the compliance dashboard HTML page."""
    report = ComplianceService.check_project_compliance(project_id)
    return render_template("compliance_dashboard.html", report=report, project_id=project_id)


# ── GET /api/compliance/<project_id>  (aliased for frontend fetch()) ──────────
@compliance_bp.route("/api/<int:project_id>")
def api_compliance(project_id):
    """Alias used by the dashboard's fetch('/api/compliance/<id>') call."""
    report = ComplianceService.check_project_compliance(project_id)
    return jsonify(report)