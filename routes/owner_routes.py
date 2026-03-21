import os

from flask import Blueprint, redirect, url_for, flash, render_template
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


@owner_bp.route("/")
@jwt_required()
def owner_home():
    user, err = _get_owner_or_redirect()
    if err:
        return err
    buildiq_url = os.getenv("BUILDIQ_URL", "http://localhost:8000")
    return render_template("owner_home.html", user=user, buildiq_url=buildiq_url)


@owner_bp.route("/ask")
@jwt_required()
def ask():
    user, err = _get_owner_or_redirect()
    if err:
        return err
    buildiq_url = os.getenv("BUILDIQ_URL", "http://localhost:8000")
    return render_template("owner_ask.html", user=user, buildiq_url=buildiq_url)


@owner_bp.route("/documents")
@jwt_required()
def documents():
    user, err = _get_owner_or_redirect()
    if err:
        return err
    docs = DocumentVersion.query.filter_by(uploaded_by=user.username).order_by(
        DocumentVersion.uploaded_at.desc()
    ).all()
    return render_template("owner_documents.html", user=user, docs=docs)
