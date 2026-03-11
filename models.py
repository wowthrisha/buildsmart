from extensions import db
from datetime import datetime


class Document(db.Model):

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    current_version = db.Column(db.Integer, default=1)


class DocumentVersion(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    document_id = db.Column(db.Integer)

    version_number = db.Column(db.Integer)

    file_path = db.Column(db.String(300))

    uploaded_by = db.Column(db.String(100))

    upload_date = db.Column(db.DateTime, default=datetime.utcnow)


class DocumentLog(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    document_id = db.Column(db.Integer)

    action = db.Column(db.String(50))

    user = db.Column(db.String(100))

    timestamp = db.Column(db.DateTime, default=datetime.utcnow)