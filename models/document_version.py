from app import db

class DocumentVersion(db.Model):
    __tablename__ = "document_versions"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer)
    version_number = db.Column(db.Integer)
    file_path = db.Column(db.String(255))