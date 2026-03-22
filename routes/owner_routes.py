import json
import os

from flask import Blueprint, jsonify, redirect, request, url_for, flash, render_template
from flask_jwt_extended import jwt_required, get_jwt_identity
from models.user import User
from models.document import DocumentVersion

owner_bp = Blueprint("owner", __name__, url_prefix="/owner")


def _get_owner_or_redirect():
    """Return (user, None) for valid Owner, or (None, redirect_response)."""
    user = User.query.get(get_jwt_identity())
    if user is None:
        flash("Session expired. Please log in again.")
        return None, redirect(url_for("auth.login"))
    if user.role != "Owner":
        flash("This section is for professional users.")
        return None, redirect(url_for("document.dashboard"))
    return user, None


def _owner_project(uid):
    """Return the Project assigned to this owner, or None."""
    from models.project import Project
    return Project.query.filter_by(owner_id=uid).first()


@owner_bp.route("/")
@jwt_required()
def owner_home():
    user, err = _get_owner_or_redirect()
    if err:
        return err
    project = _owner_project(user.id)
    buildiq_url = os.getenv("BUILDIQ_URL", "http://localhost:8000")
    return render_template("owner_home.html", user=user, project=project,
                           buildiq_url=buildiq_url)


@owner_bp.route("/ask")
@jwt_required()
def ask():
    user, err = _get_owner_or_redirect()
    if err:
        return err
    buildiq_url = os.getenv("BUILDIQ_URL", "http://localhost:8000")
    return render_template("owner_ask.html", user=user, buildiq_url=buildiq_url)


@owner_bp.route("/save-compliance", methods=["POST"])
@jwt_required()
def save_compliance():
    """Store the owner's last compliance payload to a shared file so MoM can read it."""
    data = request.get_json(silent=True) or {}
    if data:
        path = os.path.join(os.path.dirname(__file__), '..', 'instance', 'last_compliance.json')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(os.path.abspath(path), 'w') as f:
            json.dump(data, f)
    return jsonify({'ok': True})


@owner_bp.route("/documents")
@jwt_required()
def documents():
    user, err = _get_owner_or_redirect()
    if err:
        return err
    from models.document import Document
    project = _owner_project(user.id)
    if project:
        docs = Document.query.filter_by(project_id=project.id)\
                             .order_by(Document.created_at.desc()).all()
    else:
        docs = Document.query.order_by(Document.created_at.desc()).all()
    return render_template("owner_documents.html", user=user, docs=docs,
                           project=project)
