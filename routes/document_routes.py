from flask import Blueprint, request, redirect, render_template, url_for, send_file
from extensions import db
from models.document import Document, DocumentVersion, DocumentLog
from models.user import User
from flask_jwt_extended import jwt_required, get_jwt_identity
import os

document_bp = Blueprint("document", __name__)

@document_bp.route("/")
def home():
    return redirect(url_for("document.dashboard"))

@document_bp.route("/dashboard")
@jwt_required()
def dashboard():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    
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
    
    title = request.form["title"]
    description = request.form["description"]
    file = request.files["file"]
    if file:
        filepath = os.path.join("uploads", file.filename)
        file.save(filepath)
        doc = Document(title=title, description=description, current_version=1, created_by=user.username)
        db.session.add(doc)
        db.session.commit()
        db.session.add(DocumentVersion(document_id=doc.id, version_number=1, file_path=filepath, uploaded_by=user.username))
        db.session.add(DocumentLog(document_id=doc.id, action="Uploaded initial version", performed_by=user.username))
        db.session.commit()
    return redirect(url_for("document.dashboard"))

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
    latest = DocumentVersion.query.filter_by(document_id=doc_id).order_by(DocumentVersion.id.desc()).first()
    new_version = int(latest.version_number) + 1 if latest else 1
    filepath = os.path.join("uploads", file.filename)
    file.save(filepath)
    db.session.add(DocumentVersion(document_id=doc_id, version_number=new_version, file_path=filepath, uploaded_by=user.username))
    doc = Document.query.get(doc_id)
    doc.current_version = new_version
    db.session.add(DocumentLog(document_id=doc_id, action=f"Uploaded version {new_version}", performed_by=user.username))
    db.session.commit()
    return redirect(url_for("document.view_versions", document_id=doc_id))

@document_bp.route("/download/<int:version_id>")
def download_file(version_id):
    version = DocumentVersion.query.get(version_id)
    return send_file(version.file_path, as_attachment=True)

@document_bp.route("/logs")
@jwt_required()
def logs():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
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
