from app import app, db
from models.document import Document

with app.app_context():
    db.create_all()
    print("Tables created!")

    doc = Document(
        title="Foundation Plan",
        description="Initial structural drawing",
        created_by="Engineer"
    )

    db.session.add(doc)
    db.session.commit()

    print("Test document inserted!")