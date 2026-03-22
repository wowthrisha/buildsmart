import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-in-prod")
    SQLALCHEMY_DATABASE_URI = os.environ.get("FLASK_DATABASE_URL") or \
                              os.environ.get("DATABASE_URL", "sqlite:///buildsmart.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = "uploads"
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-only-change-in-prod")
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_COOKIE_CSRF_PROTECT = False