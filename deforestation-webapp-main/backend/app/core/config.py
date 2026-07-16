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

    # NASA FIRMS ingestion (optional — mock data used when empty)
    firms_api_key: str = ""

    # Background scheduler
    firms_poll_interval_minutes: int = 60
    enable_background_ingestion: bool = True

    # Outbound notifications
    enable_notifications: bool = True
    discord_webhook_url: str = ""
    generic_webhook_url: str = ""

    # Weather enrichment
    weather_cache_ttl_minutes: int = 30
    weather_provider: str = "open_meteo"

    # Operational Reporting
    reports_dir: str = "reports"
    enable_scheduled_reports: bool = True


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
        firms_api_key=os.environ.get("FIRMS_API_KEY", ""),
        firms_poll_interval_minutes=int(
            os.environ.get("FIRMS_POLL_INTERVAL_MINUTES", "60")
        ),
        enable_background_ingestion=(
            os.environ.get("ENABLE_BACKGROUND_INGESTION", "true").lower() == "true"
        ),
        enable_notifications=(
            os.environ.get("ENABLE_NOTIFICATIONS", "true").lower() == "true"
        ),
        discord_webhook_url=os.environ.get("DISCORD_WEBHOOK_URL", ""),
        generic_webhook_url=os.environ.get("GENERIC_WEBHOOK_URL", ""),
        weather_cache_ttl_minutes=int(
            os.environ.get("WEATHER_CACHE_TTL_MINUTES", "30")
        ),
        weather_provider=os.environ.get("WEATHER_PROVIDER", "open_meteo"),
        reports_dir=os.environ.get("REPORTS_DIR", "reports"),
        enable_scheduled_reports=(
            os.environ.get("ENABLE_SCHEDULED_REPORTS", "true").lower() == "true"
        ),
    )
