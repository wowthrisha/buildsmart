import os

class Config:
    SECRET_KEY = "buildsmart-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///buildsmart.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = "uploads"