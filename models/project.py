from datetime import datetime

from extensions import db


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    timeline_events = db.relationship(
        "TimelineEvent",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="TimelineEvent.created_at.desc()",
    )


class TimelineEvent(db.Model):
    __tablename__ = "timeline_events"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    event_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    project = db.relationship("Project", back_populates="timeline_events")
