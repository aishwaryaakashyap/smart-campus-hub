"""Production WSGI entry point for Smart Campus Hub."""

from app import app
from config import validate_production_config

if app.config.get("APP_ENV") == "production":
    validate_production_config(app.config)

__all__ = ["app"]
