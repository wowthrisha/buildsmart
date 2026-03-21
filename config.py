import os

class Config:
    SECRET_KEY = "buildsmart-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///buildsmart.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = "uploads"
    JWT_SECRET_KEY = "buildsmart-jwt-secret-key"
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_COOKIE_CSRF_PROTECT = False