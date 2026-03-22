from extensions import db
from datetime import datetime

DESIGN_TAGS = [
    'exterior', 'interior', 'kitchen', 'bathroom',
    'lighting', 'materials', 'flooring', 'facade',
    'landscape', 'staircase', 'ceiling', 'door-window'
]


class ReferencePin(db.Model):
    __tablename__ = 'reference_pins'

    id          = db.Column(db.Integer, primary_key=True)
    project_id  = db.Column(db.Integer, db.ForeignKey('projects.id'))
    added_by    = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Source
    source_url  = db.Column(db.String(500), nullable=True)
    image_url   = db.Column(db.String(500), nullable=True)
    site_name   = db.Column(db.String(100), nullable=True)
    title       = db.Column(db.String(300), nullable=True)

    # Uploaded image (alternative to URL)
    local_image = db.Column(db.String(300), nullable=True)

    # Architect tags + note
    design_tags = db.Column(db.String(300), nullable=True)  # comma-separated
    arch_note   = db.Column(db.Text, nullable=True)

    # Link to MoM decision
    mom_item_id = db.Column(db.Integer, db.ForeignKey('mom_items.id'), nullable=True)

    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    project      = db.relationship('Project', backref='reference_pins')
    added_by_user = db.relationship('User', backref='pins', foreign_keys=[added_by])
