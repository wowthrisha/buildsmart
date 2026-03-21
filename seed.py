from app import create_app
from extensions import db
from models.user import User
from models.document import Document
from werkzeug.security import generate_password_hash

app = create_app()
with app.app_context():

    # Create user
    user = User(
        username='admin',
        email='admin@buildsmart.com',
        password_hash=generate_password_hash('admin123'),
        role='Architect'
    )
    db.session.add(user)

    # Add test documents
    docs = [
        Document(title="Structural Drawings v1",      project_id=1, created_by="admin", document_type="Structural Drawings",       is_outdated=False),
        Document(title="Electrical Plan v1",           project_id=1, created_by="admin", document_type="Electrical Plan",           is_outdated=False),
        Document(title="Environmental Clearance v1",   project_id=1, created_by="admin", document_type="Environmental Clearance",   is_outdated=False),
        Document(title="Zoning Permit v1",             project_id=1, created_by="admin", document_type="Zoning Permit",             is_outdated=True),
    ]
    db.session.add_all(docs)
    db.session.commit()
    print("User and documents created successfully")