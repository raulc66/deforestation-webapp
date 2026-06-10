"""Centralized configuration management."""
import os
from functools import lru_cache
from pydantic import BaseModel


class Settings(BaseModel):
    # Database
    mongo_url: str
    db_name: str

    # Security
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60 * 24  # 1 day for dev simplicity
    refresh_token_days: int = 7

    # Admin seed
    admin_email: str
    admin_password: str

    # CORS / frontend
    frontend_url: str
    cors_origins: str = "*"

    # Logging
    log_level: str = "INFO"


@lru_cache()
def get_settings() -> Settings:
    return Settings(
        mongo_url=os.environ["MONGO_URL"],
        db_name=os.environ["DB_NAME"],
        jwt_secret=os.environ["JWT_SECRET"],
        admin_email=os.environ.get("ADMIN_EMAIL", "admin@example.com"),
        admin_password=os.environ.get("ADMIN_PASSWORD", "admin123"),
        frontend_url=os.environ.get("FRONTEND_URL", "http://localhost:3000"),
        cors_origins=os.environ.get("CORS_ORIGINS", "*"),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
    )
