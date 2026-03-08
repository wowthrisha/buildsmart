from app import db

class DocumentLog(db.Model):
    __tablename__ = "document_logs"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer)
    action = db.Column(db.String(50))