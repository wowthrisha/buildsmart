from flask import Blueprint, request, redirect, render_template, url_for, send_file, jsonify, flash, abort
from extensions import db
from models.document import Document, DocumentVersion, DocumentLog
from models.user import User
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import safe_join
import os

document_bp = Blueprint("document", __name__)


def sync_compliance(document, project_id):
    """
    After any upload, auto-link the document to its ComplianceRequirement
    if the document_type matches a required document.
    """
    try:
        from models.compliance_models import ComplianceRequirement, REQUIRED_DOCUMENT_TYPES
        from services.compliance_service import ComplianceService

        if not document.document_type:
            return

        # Seed requirements first (idempotent)
        ComplianceService.seed_compliance_requirements(project_id)

        # Find matching requirement and link it
        req = ComplianceRequirement.query.filter_by(
            project_id=project_id,
            document_type=document.document_type
        ).first()

        if req:
            req.document_id = document.id
            document.is_outdated = False
            db.session.commit()
    except Exception as e:
        print(f"Compliance sync error: {e}")


@document_bp.route("/")
def home():
    return redirect(url_for("document.dashboard"))


@document_bp.route("/dashboard")
@jwt_required()
def dashboard():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    if user.role == "Owner":
        flash("This section is for professional users. You have been redirected.")
        return redirect(url_for("owner.owner_home"))

    documents = Document.query.order_by(Document.created_at.desc()).all()
    logs = DocumentLog.query.order_by(DocumentLog.timestamp.desc()).limit(10).all()

    active_submissions = len(documents)
    pending_approvals = sum(1 for d in documents if d.current_version == 1)

    return render_template("dashboard.html",
                           documents=documents,
                           logs=logs,
                           active_submissions=active_submissions,
                           pending_approvals=pending_approvals,
                           user=user)


@document_bp.route("/upload", methods=["POST"])
@jwt_required()
def upload_document():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    title       = request.form.get("title", "")
    description = request.form.get("description", "")
    doc_type    = request.form.get("document_type", "").strip() or None
    project_id  = int(request.form.get("project_id", 1))
    file        = request.files.get("file")

    if file:
        os.makedirs("uploads", exist_ok=True)
        filepath = os.path.join("uploads", file.filename)
        file.save(filepath)

        doc = Document(
            title=title,
            description=description,
            current_version=1,
            created_by=user.username,
            project_id=project_id,
            document_type=doc_type,
            is_outdated=False,
        )
        db.session.add(doc)
        db.session.commit()

        db.session.add(DocumentVersion(
            document_id=doc.id,
            version_number=1,
            file_path=filepath,
            uploaded_by=user.username
        ))
        db.session.add(DocumentLog(
            document_id=doc.id,
            action="Uploaded initial version",
            performed_by=user.username
        ))
        db.session.commit()

        # Auto-sync compliance
        sync_compliance(doc, project_id)

    # Redirect back to compliance dashboard if came from there
    next_url = request.form.get("next") or url_for("document.dashboard")
    return redirect(next_url)


@document_bp.route("/compliance-upload", methods=["POST"])
@jwt_required()
def compliance_upload():
    """
    Dedicated upload endpoint called from the compliance checklist.
    Accepts document_type and project_id, saves file, links to compliance.
    """
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    doc_type   = request.form.get("document_type", "").strip()
    project_id = int(request.form.get("project_id", 1))
    next_url   = request.form.get("next", "")
    file       = request.files.get("file")

    if not file or not doc_type:
        return redirect(next_url or url_for("compliance.dashboard", project_id=project_id))

    os.makedirs("uploads", exist_ok=True)
    filepath = os.path.join("uploads", file.filename)
    file.save(filepath)

    # Check if a document of this type already exists for the project
    existing = Document.query.filter_by(
        project_id=project_id,
        document_type=doc_type
    ).first()

    if existing:
        # Upload a new version
        latest = DocumentVersion.query.filter_by(
            document_id=existing.id
        ).order_by(DocumentVersion.id.desc()).first()
        new_version = (latest.version_number + 1) if latest else 2

        existing.current_version = new_version
        existing.is_outdated = False
        db.session.add(DocumentVersion(
            document_id=existing.id,
            version_number=new_version,
            file_path=filepath,
            uploaded_by=user.username
        ))
        db.session.add(DocumentLog(
            document_id=existing.id,
            action=f"Re-uploaded version {new_version} via Compliance Tracker",
            performed_by=user.username
        ))
        db.session.commit()
        sync_compliance(existing, project_id)
    else:
        # Create new document
        doc = Document(
            title=doc_type,
            description=f"Uploaded via Compliance Tracker",
            current_version=1,
            created_by=user.username,
            project_id=project_id,
            document_type=doc_type,
            is_outdated=False,
        )
        db.session.add(doc)
        db.session.commit()
        db.session.add(DocumentVersion(
            document_id=doc.id,
            version_number=1,
            file_path=filepath,
            uploaded_by=user.username
        ))
        db.session.add(DocumentLog(
            document_id=doc.id,
            action="Uploaded via Compliance Tracker",
            performed_by=user.username
        ))
        db.session.commit()
        sync_compliance(doc, project_id)

    return redirect(next_url or url_for("compliance.dashboard", project_id=project_id))


@document_bp.route("/repository")
@jwt_required()
def repository():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    return render_template("repository.html", documents=Document.query.all(), user=user)


@document_bp.route("/versions/<int:document_id>")
@jwt_required()
def view_versions(document_id):
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    doc = Document.query.get(document_id)
    versions = DocumentVersion.query.filter_by(document_id=document_id).all()
    return render_template("versions.html", versions=versions, document=doc, user=user)


@document_bp.route("/upload-version/<int:doc_id>", methods=["POST"])
@jwt_required()
def upload_new_version(doc_id):
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)

    file = request.files["file"]
    latest = DocumentVersion.query.filter_by(
        document_id=doc_id
    ).order_by(DocumentVersion.id.desc()).first()
    new_version = int(latest.version_number) + 1 if latest else 1

    os.makedirs("uploads", exist_ok=True)
    filepath = os.path.join("uploads", file.filename)
    file.save(filepath)

    db.session.add(DocumentVersion(
        document_id=doc_id,
        version_number=new_version,
        file_path=filepath,
        uploaded_by=user.username
    ))
    doc = Document.query.get(doc_id)
    doc.current_version = new_version
    doc.is_outdated = False
    db.session.add(DocumentLog(
        document_id=doc_id,
        action=f"Uploaded version {new_version}",
        performed_by=user.username
    ))
    db.session.commit()

    # Auto-sync compliance if this doc has a type and project
    if doc.project_id and doc.document_type:
        sync_compliance(doc, doc.project_id)

    return redirect(url_for("document.view_versions", document_id=doc_id))


@document_bp.route("/download/<int:version_id>")
@jwt_required()
def download_file(version_id):
    version = DocumentVersion.query.get_or_404(version_id)
    upload_dir = os.path.abspath('uploads')
    safe_path = safe_join(upload_dir, os.path.basename(version.file_path))
    if not safe_path or not os.path.exists(safe_path):
        abort(404)
    return send_file(safe_path, as_attachment=True)


@document_bp.route("/logs")
@jwt_required()
def logs():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if user.role == "Owner":
        return redirect(url_for("owner.owner_home"))
    logs = DocumentLog.query.order_by(DocumentLog.timestamp.desc()).all()
    return render_template("logs.html", logs=logs, user=user)


@document_bp.route("/compare/<int:v1_id>/<int:v2_id>")
@jwt_required()
def compare_versions(v1_id, v2_id):
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    v1 = DocumentVersion.query.get(v1_id)
    v2 = DocumentVersion.query.get(v2_id)
    return render_template("compare.html", v1=v1, v2=v2, user=user)


@document_bp.route("/profile")
@jwt_required()
def profile():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    return render_template("profile.html", user=user)