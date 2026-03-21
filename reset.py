from app import create_app
from extensions import db
from models.compliance_models import ComplianceRequirement

app = create_app()
with app.app_context():
    ComplianceRequirement.query.filter_by(project_id=1).delete()
    db.session.commit()
    print("Compliance requirements cleared. Refresh the dashboard now.")