from datetime import datetime
from extensions import db


class ApprovalRequest(db.Model):
    __tablename__ = 'approval_requests'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    submitted_by = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), default='Pending')
    # States: Pending → Under Review → Approved / Rejected; overdue → Escalated
    rejection_reason = db.Column(db.Text)
    review_notes = db.Column(db.Text)
    reviewed_by = db.Column(db.String(100))
    risk_score = db.Column(db.Float, default=0.0)
    deadline = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship('Project', backref='approval_requests', foreign_keys=[project_id])

    @property
    def is_overdue(self):
        if self.deadline and self.status in ('Pending', 'Under Review'):
            return datetime.utcnow() > self.deadline
        return False

    @property
    def risk_label(self):
        if self.risk_score >= 0.6:
            return 'High'
        elif self.risk_score >= 0.3:
            return 'Medium'
        return 'Low'

    @property
    def status_color(self):
        return {
            'Pending': '#FFD600',
            'Under Review': '#2979FF',
            'Approved': '#39FF82',
            'Rejected': '#ef4444',
            'Escalated': '#FF6B1A',
        }.get(self.status, '#888')


class ApprovalLog(db.Model):
    __tablename__ = 'approval_logs'

    id = db.Column(db.Integer, primary_key=True)
    approval_id = db.Column(db.Integer, db.ForeignKey('approval_requests.id'), nullable=False)
    action = db.Column(db.String(200), nullable=False)
    performed_by = db.Column(db.String(100))
    notes = db.Column(db.Text)
    from_status = db.Column(db.String(50))
    to_status = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    approval = db.relationship('ApprovalRequest', backref='logs')
