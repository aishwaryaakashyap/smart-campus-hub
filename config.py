import os
from urllib.parse import urlparse

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

load_dotenv()


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


class Config:
    APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()

    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)
    SESSION_COOKIE_HTTPONLY = True

    WTF_CSRF_ENABLED = True

    RESUME_UPLOAD_FOLDER = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "uploads",
        "resumes"
    )
    RESUME_MAX_BYTES = 5 * 1024 * 1024
    RESUME_MAX_TEXT_CHARS = 250000

    # SMTP email configuration
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "").strip()
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = env_bool("MAIL_USE_TLS", True)
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "").strip()
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get(
        "MAIL_DEFAULT_SENDER",
        os.environ.get("MAIL_USERNAME", "")
    ).strip()

    # Trusted application URL used for password-reset links.
    # Never construct reset links from incoming Host headers.
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "").rstrip("/")

    PASSWORD_RESET_TOKEN_MINUTES = 15

    # Student email OTP settings
    STUDENT_OTP_MINUTES = 10
    STUDENT_OTP_MAX_ATTEMPTS = 5
    STUDENT_OTP_RESEND_SECONDS = 60
    STUDENT_OTP_MAX_RESENDS_PER_HOUR = 5


def validate_production_config(config):
    """Reject unsafe or incomplete settings before production startup."""

    problems = []

    secret_key = config.get("SECRET_KEY")
    if not isinstance(secret_key, str) or len(secret_key) < 32:
        problems.append("SECRET_KEY must contain at least 32 characters")

    database_url = config.get("SQLALCHEMY_DATABASE_URI")

    try:
        database = make_url(database_url) if database_url else None
    except Exception:
        database = None

    if database is None:
        problems.append("DATABASE_URL is missing or invalid")
    else:
        if database.drivername not in (
            "mysql+pymysql",
            "mariadb+pymysql"
        ):
            problems.append("DATABASE_URL must use MySQL/MariaDB with PyMySQL")

        if not database.host or not database.database:
            problems.append("DATABASE_URL must specify a host and database")

        if not database.username or not database.password:
            problems.append("DATABASE_URL must specify database credentials")

    base_url = config.get("APP_BASE_URL", "")

    try:
        parsed_url = urlparse(base_url)
        hostname = parsed_url.hostname
    except ValueError:
        hostname = None
        parsed_url = None

    local_hosts = {
        "localhost",
        "127.0.0.1",
        "::1",
        "0.0.0.0"
    }

    if (
        parsed_url is None
        or parsed_url.scheme != "https"
        or not hostname
        or hostname.lower() in local_hosts
        or hostname.lower().endswith(".localhost")
        or parsed_url.username
        or parsed_url.password
    ):
        problems.append("APP_BASE_URL must be a public HTTPS URL")

    if config.get("SESSION_COOKIE_SECURE") is not True:
        problems.append("SESSION_COOKIE_SECURE must be enabled")

    if config.get("SESSION_COOKIE_HTTPONLY") is not True:
        problems.append("SESSION_COOKIE_HTTPONLY must be enabled")

    same_site = config.get("SESSION_COOKIE_SAMESITE")
    if not isinstance(same_site, str) or same_site.lower() not in (
        "lax",
        "strict"
    ):
        problems.append("SESSION_COOKIE_SAMESITE must be Lax or Strict")

    if config.get("WTF_CSRF_ENABLED") is not True:
        problems.append("WTF_CSRF_ENABLED must be enabled")

    if not config.get("MAIL_SERVER"):
        problems.append("MAIL_SERVER is required")

    if not isinstance(config.get("MAIL_PORT"), int) or not (
        1 <= config["MAIL_PORT"] <= 65535
    ):
        problems.append("MAIL_PORT must be between 1 and 65535")

    if config.get("MAIL_USE_TLS") is not True:
        problems.append("MAIL_USE_TLS must be enabled")

    if not config.get("MAIL_USERNAME"):
        problems.append("MAIL_USERNAME is required")

    if not config.get("MAIL_PASSWORD"):
        problems.append("MAIL_PASSWORD is required")

    if not config.get("MAIL_DEFAULT_SENDER"):
        problems.append("MAIL_DEFAULT_SENDER is required")

    if problems:
        raise RuntimeError(
            "Production configuration invalid: "
            + "; ".join(problems)
        )

    return True
