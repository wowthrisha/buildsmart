from flask import Blueprint, render_template, jsonify, request, redirect, url_for
from flask_jwt_extended import jwt_required, get_jwt_identity
from services.compliance_service import ComplianceService

compliance_bp = Blueprint("compliance", __name__, url_prefix="/compliance")


def _current_user():
    from models.user import User
    return User.query.get(get_jwt_identity())


# ── GET /compliance/<project_id> ─────────────────────────────────────────────
@compliance_bp.route("/<int:project_id>")
@jwt_required()
def compliance_report(project_id):
    """Returns full compliance JSON for a project."""
    report = ComplianceService.check_project_compliance(project_id)
    return jsonify(report)


# ── GET /compliance/missing/<project_id> ─────────────────────────────────────
@compliance_bp.route("/missing/<int:project_id>")
@jwt_required()
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
@jwt_required()
def dashboard(project_id):
    """Renders the compliance dashboard HTML page."""
    report = ComplianceService.check_project_compliance(project_id)
    user = _current_user()
    return render_template("compliance_dashboard.html", report=report,
                           project_id=project_id, user=user)


# ── GET /api/compliance/<project_id>  (aliased for frontend fetch()) ──────────
@compliance_bp.route("/api/<int:project_id>")
@jwt_required()
def api_compliance(project_id):
    """Alias used by the dashboard's fetch('/api/compliance/<id>') call."""
    report = ComplianceService.check_project_compliance(project_id)
    return jsonify(report)


# ── GET /compliance/static/<project_id> ──────────────────────────────────────
@compliance_bp.route("/static/<int:project_id>")
@jwt_required()
def compliance_static(project_id):
    """Renders the static readiness tracker preview page."""
    from models.compliance_models import ComplianceRequirement
    from models.project import Project
    project = Project.query.get_or_404(project_id)
    requirements = ComplianceRequirement.query.filter_by(project_id=project_id).all()
    user = _current_user()
    return render_template("compliance_static.html",
                           project=project,
                           requirements=requirements,
                           user=user)