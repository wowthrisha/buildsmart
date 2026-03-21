from extensions import db
from datetime import datetime

# Required document types for compliance
REQUIRED_DOCUMENT_TYPES = [
    "Structural Drawings",
    "Electrical Plan",
    "Environmental Clearance",
    "Zoning Permit",
    "Fire Safety Certificate",
    "Safety Compliance Document",
]

# Readiness thresholds
READINESS_THRESHOLDS = {
    "NOT_READY":          (0,  40),
    "NEEDS_WORK":         (41, 70),
    "READY_FOR_APPROVAL": (71, 100),
}


class ComplianceRequirement(db.Model):
    """
    Tracks which document types are required per project.
    Does NOT duplicate Document — it references document_type
    and links to the uploaded Document record if one exists.
    """
    __tablename__ = "compliance_requirements"

    id         = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)

    # Matches Document.document_type
    document_type = db.Column(db.String(120), nullable=False)

    # FK to the actual Document row once uploaded (nullable until then)
    document_id   = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project  = db.relationship("Project",  backref=db.backref("compliance_requirements", lazy="dynamic"))
    document = db.relationship("Document", backref=db.backref("compliance_requirement",  uselist=False))

    def __repr__(self):
        return f"<ComplianceRequirement project={self.project_id} type='{self.document_type}'>"

    def to_dict(self):
        return {
            "id":            self.id,
            "project_id":    self.project_id,
            "document_type": self.document_type,
            "document_id":   self.document_id,
            "is_fulfilled":  self.document_id is not None,
            "is_outdated":   self.document.is_outdated if self.document else False,
        }