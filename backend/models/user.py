from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String
from backend.database import Base

VALID_ROLES = {"Architect", "Engineer", "Contractor", "Authority", "Owner"}


class User(Base):
    # Same table name and schema as the Flask app — shared database compatible
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="Engineer")
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<User {self.username} (Role: {self.role})>"
