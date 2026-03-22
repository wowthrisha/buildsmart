from extensions import db
from datetime import datetime


class MeetingMinutes(db.Model):
    __tablename__ = 'meeting_minutes'

    id            = db.Column(db.Integer, primary_key=True)
    project_id    = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    title         = db.Column(db.String(200), nullable=False)
    meeting_date  = db.Column(db.DateTime, default=datetime.utcnow)
    created_by    = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Compliance snapshot — frozen F4 output at time of meeting
    compliance_score    = db.Column(db.Float, nullable=True)
    compliance_status   = db.Column(db.String(20), nullable=True)
    compliance_snapshot = db.Column(db.Text, nullable=True)  # JSON string

    # Dual signature
    creator_signed    = db.Column(db.Boolean, default=False)
    client_signed     = db.Column(db.Boolean, default=False)
    creator_signed_at = db.Column(db.DateTime, nullable=True)
    client_signed_at  = db.Column(db.DateTime, nullable=True)
    client_email      = db.Column(db.String(200), nullable=True)

    # Lock state
    is_locked    = db.Column(db.Boolean, default=False)
    locked_at    = db.Column(db.DateTime, nullable=True)
    share_token  = db.Column(db.String(64), unique=True, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items   = db.relationship('MomItem', backref='mom', cascade='all,delete-orphan')
    project = db.relationship('Project', backref='minutes')
    creator = db.relationship('User', backref='created_minutes', foreign_keys=[created_by])

    @property
    def sig_count(self):
        return int(self.creator_signed) + int(self.client_signed)

    @property
    def status_label(self):
        if self.is_locked:
            return 'Locked'
        if self.creator_signed and not self.client_signed:
            return 'Awaiting client'
        if not self.creator_signed:
            return 'Draft'
        return 'Draft'


class MomItem(db.Model):
    __tablename__ = 'mom_items'

    id       = db.Column(db.Integer, primary_key=True)
    mom_id   = db.Column(db.Integer, db.ForeignKey('meeting_minutes.id'))
    text     = db.Column(db.String(500), nullable=False)
    state    = db.Column(db.String(20), default='Pending')
    order    = db.Column(db.Integer, default=0)
    added_by = db.Column(db.Integer, db.ForeignKey('users.id'))
