from flask import Blueprint, request, redirect, render_template, url_for, send_file
from extensions import db
from models.document import Document, DocumentVersion, DocumentLog
import os

document_bp = Blueprint("document", __name__)

@document_bp.route("/")
def home():
    return render_template("home.html")

@document_bp.route("/upload", methods=["POST"])
def upload_document():
    title = request.form["title"]
    description = request.form["description"]
    file = request.files["file"]
    if file:
        filepath = os.path.join("uploads", file.filename)
        file.save(filepath)
        doc = Document(title=title, description=description, current_version="1")
        db.session.add(doc)
        db.session.commit()
        db.session.add(DocumentVersion(document_id=doc.id, version_number="1", file_path=filepath))
        db.session.add(DocumentLog(document_id=doc.id, action="UPLOAD", performed_by="Engineer"))
        db.session.commit()
    return redirect(url_for("document.repository"))

@document_bp.route("/repository")
def repository():
    return render_template("repository.html", documents=Document.query.all())

@document_bp.route("/versions/<int:document_id>")
def view_versions(document_id):
    versions = DocumentVersion.query.filter_by(document_id=document_id).all()
    return render_template("versions.html", versions=versions, document_id=document_id)

@document_bp.route("/upload-version/<int:doc_id>", methods=["POST"])
def upload_new_version(doc_id):
    file = request.files["file"]
    latest = DocumentVersion.query.filter_by(document_id=doc_id).order_by(DocumentVersion.id.desc()).first()
    new_version = str(int(latest.version_number) + 1) if latest else "1"
    filepath = os.path.join("uploads", file.filename)
    file.save(filepath)
    db.session.add(DocumentVersion(document_id=doc_id, version_number=new_version, file_path=filepath))
    doc = Document.query.get(doc_id)
    doc.current_version = new_version
    db.session.add(DocumentLog(document_id=doc_id, action="NEW_VERSION", performed_by="Engineer"))
    db.session.commit()
    return redirect(url_for("document.view_versions", document_id=doc_id))

@document_bp.route("/download/<int:version_id>")
def download_file(version_id):
    version = DocumentVersion.query.get(version_id)
    return send_file(version.file_path, as_attachment=True)

@document_bp.route("/logs")
def logs():
    logs = DocumentLog.query.order_by(DocumentLog.timestamp.desc()).all()
    return render_template("logs.html", logs=logs)
