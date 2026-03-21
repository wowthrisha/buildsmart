from datetime import datetime
from extensions import db


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    project_id = db.Column(db.Integer)
    created_by = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    current_version = db.Column(db.Integer, default=1)


class DocumentVersion(db.Model):
    __tablename__ = "document_versions"65

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer)
    version_number = db.Column(db.Integer)
    file_path = db.Column(db.String(255))
    uploaded_by = db.Column(db.String(100))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    change_notes = db.Column(db.Text)


class DocumentLog(db.Model):
    __tablename__ = "document_logs"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer)
    action = db.Column(db.String(100))
    performed_by = db.Column(db.String(100))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    details = db.Column(db.Text)