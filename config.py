
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_COOKIE_SAMESITE = "Lax"

    # Enable secure session cookies for HTTPS production deployments.
    # Keep disabled by default for local HTTP development.
    SESSION_COOKIE_SECURE = os.environ.get(
        "SESSION_COOKIE_SECURE", "0"
    ).strip().lower() in ("1", "true", "yes", "on")

    # Private student resume storage; never serve as static files.
    RESUME_UPLOAD_FOLDER = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "uploads",
        "resumes"
    )
    RESUME_MAX_BYTES = 5 * 1024 * 1024
    RESUME_MAX_TEXT_CHARS = 250000
