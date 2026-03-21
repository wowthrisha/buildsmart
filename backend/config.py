import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "fallback-dev-key")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fallback-jwt-key")
DEBUG = os.getenv("DEBUG", "False") == "True"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///backend/db/buildiq.db")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
