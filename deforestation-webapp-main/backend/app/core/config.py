"""Centralized configuration management."""
import os
from functools import lru_cache
from pydantic import BaseModel

from app.core.commercial.stripe_api import STRIPE_API_VERSION

# Development remains the default so local demo, tests, and Docker Compose are
# unchanged. Production-safety checks run only when FORESTWATCH_ENV=production.
_PRODUCTION_ENV_VALUES = frozenset({"production", "prod"})
_MIN_PRODUCTION_JWT_SECRET_LEN = 32
_KNOWN_DEVELOPMENT_JWT_SECRETS = frozenset(
    {
        "change-me-to-a-long-random-secret",
        "dev-only-jwt-secret-do-not-use-in-production-32",
        "determinism-harness",
        "offline-regression-secret",
        "secret",
    }
)
_KNOWN_DEVELOPMENT_ADMIN_PASSWORDS = frozenset(
    {
        "admin123",
        "ForestAdmin2026!",
        "dev-admin-change-me",
    }
)


def is_production_env(value: str | None) -> bool:
    return (value or "").strip().lower() in _PRODUCTION_ENV_VALUES


def enforce_production_safety(
    *,
    forestwatch_env: str,
    jwt_secret: str,
    admin_password: str,
    cors_origins: str,
) -> None:
    """Refuse known-insecure development defaults when running as production.

    Development, tests, and the interactive demo are unaffected unless
    ``FORESTWATCH_ENV`` is explicitly ``production`` (or ``prod``).
    """
    if not is_production_env(forestwatch_env):
        return
    errors: list[str] = []
    secret = jwt_secret or ""
    if (
        len(secret) < _MIN_PRODUCTION_JWT_SECRET_LEN
        or secret in _KNOWN_DEVELOPMENT_JWT_SECRETS
    ):
        errors.append(
            "JWT_SECRET must be a unique value of at least "
            f"{_MIN_PRODUCTION_JWT_SECRET_LEN} characters, not a documented example"
        )
    if not admin_password or admin_password in _KNOWN_DEVELOPMENT_ADMIN_PASSWORDS:
        errors.append(
            "ADMIN_PASSWORD must be a unique value, not a documented development default"
        )
    origins = (cors_origins or "").strip()
    if not origins or origins == "*":
        errors.append(
            "CORS_ORIGINS must be an explicit origin list, not * or empty"
        )
    if errors:
        raise RuntimeError(
            "ForestWatch refused to start with FORESTWATCH_ENV=production: "
            + "; ".join(errors)
        )


class Settings(BaseModel):
    # Database
    mongo_url: str
    db_name: str

    # Deployment mode: development (default) | production
    forestwatch_env: str = "development"

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
    reconciliation_lock_lease_seconds: int = 300

    # Outbound notifications
    enable_notifications: bool = True
    discord_webhook_url: str = ""
    generic_webhook_url: str = ""

    # Weather enrichment
    weather_cache_ttl_minutes: int = 30
    weather_provider: str = "open_meteo"

    # CLMS contextual dataset refresh (static/reference data)
    clms_refresh_interval_days: int = 30
    clms_dataset_path: str = ""

    # EEA Air Quality ingestion (opt-in; fixture when no token)
    enable_eea_air_quality: bool = False
    eea_aq_api_token: str = ""
    eea_aq_poll_interval_minutes: int = 60
    eea_aq_query_window_hours: int = 24
    eea_aq_countries: str = ""

    # Copernicus EMS Rapid Mapping (public API, opt-in)
    enable_cems_rapid_mapping: bool = False

    # EFFIS burned-area contextual wildfire enrichment (public WFS, opt-in)
    enable_effis_wildfire_context: bool = False
    enable_effis_live: bool = False
    effis_context_window_days: int = 365

    # GFW integrated forest disturbance alerts (API key required for live)
    enable_forest_disturbance: bool = False
    gfw_api_key: str = ""
    gfw_alert_lookback_days: int = 30
    forest_disturbance_window_days: int = 60

    # Intelligence geographic scope: romania | europe | all
    geographic_scope: str = "romania"

    # Intelligence provenance & cross-source correlation (opt-in; off for Phase 0)
    enable_intelligence_provenance: bool = False
    enable_cross_source_correlation: bool = False
    correlation_spatial_distance_km: float = 50.0
    correlation_temporal_hours: int = 72

    # Operational Reporting
    reports_dir: str = "reports"
    enable_scheduled_reports: bool = True

    # Commercial billing (Stripe). Off by default: development and tests use the
    # deterministic fake gateway and never touch a real Stripe account.
    enable_billing: bool = False
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_webhook_tolerance_seconds: int = 300
    # Outbound Stripe API version. Default is the ForestWatch pin; override only
    # to match an existing Dashboard webhook endpoint. Empty is not a contract.
    stripe_api_version: str = STRIPE_API_VERSION
    billing_success_url: str = ""
    billing_cancel_url: str = ""
    billing_portal_return_url: str = ""

    # Plan catalog — prices and allowances are configuration, never source code.
    stripe_price_foundation: str = ""
    stripe_price_professional: str = ""
    stripe_price_enterprise: str = ""
    plan_foundation_price_label: str = ""
    plan_professional_price_label: str = ""
    plan_enterprise_price_label: str = ""
    plan_foundation_area_limit: int = 1
    plan_professional_area_limit: int = 10
    plan_enterprise_area_limit: int = 100
    plan_foundation_purchasable: bool = True
    plan_professional_purchasable: bool = True
    plan_enterprise_purchasable: bool = False
    # Commercial trial (authenticated organization, not Stripe)
    trial_duration_days: int = 14


@lru_cache()
def get_settings() -> Settings:
    forestwatch_env = os.environ.get("FORESTWATCH_ENV", "development").strip() or "development"
    jwt_secret = os.environ["JWT_SECRET"]
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    cors_origins = os.environ.get("CORS_ORIGINS", "*")
    enforce_production_safety(
        forestwatch_env=forestwatch_env,
        jwt_secret=jwt_secret,
        admin_password=admin_password,
        cors_origins=cors_origins,
    )
    return Settings(
        mongo_url=os.environ["MONGO_URL"],
        db_name=os.environ["DB_NAME"],
        forestwatch_env=forestwatch_env,
        jwt_secret=jwt_secret,
        admin_email=os.environ.get("ADMIN_EMAIL", "admin@example.com"),
        admin_password=admin_password,
        frontend_url=os.environ.get("FRONTEND_URL", "http://localhost:3000"),
        cors_origins=cors_origins,
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        firms_api_key=os.environ.get("FIRMS_API_KEY", ""),
        firms_poll_interval_minutes=int(
            os.environ.get("FIRMS_POLL_INTERVAL_MINUTES", "60")
        ),
        enable_background_ingestion=(
            os.environ.get("ENABLE_BACKGROUND_INGESTION", "true").lower() == "true"
        ),
        reconciliation_lock_lease_seconds=int(
            os.environ.get("RECONCILIATION_LOCK_LEASE_SECONDS", "300")
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
        clms_refresh_interval_days=int(
            os.environ.get("CLMS_REFRESH_INTERVAL_DAYS", "30")
        ),
        clms_dataset_path=os.environ.get("CLMS_DATASET_PATH", ""),
        enable_eea_air_quality=(
            os.environ.get("ENABLE_EEA_AIR_QUALITY", "false").lower() == "true"
        ),
        eea_aq_api_token=os.environ.get("EEA_AQ_API_TOKEN", ""),
        eea_aq_poll_interval_minutes=int(
            os.environ.get("EEA_AQ_POLL_INTERVAL_MINUTES", "60")
        ),
        eea_aq_query_window_hours=int(
            os.environ.get("EEA_AQ_QUERY_WINDOW_HOURS", "24")
        ),
        eea_aq_countries=os.environ.get("EEA_AQ_COUNTRIES", "").strip(),
        enable_cems_rapid_mapping=(
            os.environ.get("ENABLE_CEMS_RAPID_MAPPING", "false").lower() == "true"
        ),
        enable_effis_wildfire_context=(
            os.environ.get("ENABLE_EFFIS_WILDFIRE_CONTEXT", "false").lower() == "true"
        ),
        enable_effis_live=(
            os.environ.get("ENABLE_EFFIS_LIVE", "false").lower() == "true"
        ),
        effis_context_window_days=int(
            os.environ.get("EFFIS_CONTEXT_WINDOW_DAYS", "365")
        ),
        enable_forest_disturbance=(
            os.environ.get("ENABLE_FOREST_DISTURBANCE", "false").lower() == "true"
        ),
        gfw_api_key=os.environ.get("GFW_API_KEY", ""),
        gfw_alert_lookback_days=int(
            os.environ.get("GFW_ALERT_LOOKBACK_DAYS", "30")
        ),
        forest_disturbance_window_days=int(
            os.environ.get("FOREST_DISTURBANCE_WINDOW_DAYS", "60")
        ),
        geographic_scope=os.environ.get("GEOGRAPHIC_SCOPE", "romania").strip().lower(),
        enable_intelligence_provenance=(
            os.environ.get("ENABLE_INTELLIGENCE_PROVENANCE", "false").lower() == "true"
        ),
        enable_cross_source_correlation=(
            os.environ.get("ENABLE_CROSS_SOURCE_CORRELATION", "false").lower() == "true"
        ),
        correlation_spatial_distance_km=float(
            os.environ.get("CORRELATION_SPATIAL_DISTANCE_KM", "50")
        ),
        correlation_temporal_hours=int(
            os.environ.get("CORRELATION_TEMPORAL_HOURS", "72")
        ),
        reports_dir=os.environ.get("REPORTS_DIR", "reports"),
        enable_scheduled_reports=(
            os.environ.get("ENABLE_SCHEDULED_REPORTS", "true").lower() == "true"
        ),
        enable_billing=(
            os.environ.get("ENABLE_BILLING", "false").lower() == "true"
        ),
        stripe_secret_key=os.environ.get("STRIPE_SECRET_KEY", ""),
        stripe_webhook_secret=os.environ.get("STRIPE_WEBHOOK_SECRET", ""),
        stripe_api_version=os.environ.get("STRIPE_API_VERSION", STRIPE_API_VERSION),
        stripe_webhook_tolerance_seconds=int(
            os.environ.get("STRIPE_WEBHOOK_TOLERANCE_SECONDS", "300")
        ),
        billing_success_url=os.environ.get("BILLING_SUCCESS_URL", ""),
        billing_cancel_url=os.environ.get("BILLING_CANCEL_URL", ""),
        billing_portal_return_url=os.environ.get("BILLING_PORTAL_RETURN_URL", ""),
        stripe_price_foundation=os.environ.get("STRIPE_PRICE_FOUNDATION", ""),
        stripe_price_professional=os.environ.get("STRIPE_PRICE_PROFESSIONAL", ""),
        stripe_price_enterprise=os.environ.get("STRIPE_PRICE_ENTERPRISE", ""),
        plan_foundation_price_label=os.environ.get("PLAN_FOUNDATION_PRICE_LABEL", ""),
        plan_professional_price_label=os.environ.get(
            "PLAN_PROFESSIONAL_PRICE_LABEL", ""
        ),
        plan_enterprise_price_label=os.environ.get("PLAN_ENTERPRISE_PRICE_LABEL", ""),
        plan_foundation_area_limit=int(
            os.environ.get("PLAN_FOUNDATION_AREA_LIMIT", "1")
        ),
        plan_professional_area_limit=int(
            os.environ.get("PLAN_PROFESSIONAL_AREA_LIMIT", "10")
        ),
        plan_enterprise_area_limit=int(
            os.environ.get("PLAN_ENTERPRISE_AREA_LIMIT", "100")
        ),
        plan_foundation_purchasable=(
            os.environ.get("PLAN_FOUNDATION_PURCHASABLE", "true").lower() == "true"
        ),
        plan_professional_purchasable=(
            os.environ.get("PLAN_PROFESSIONAL_PURCHASABLE", "true").lower() == "true"
        ),
        plan_enterprise_purchasable=(
            os.environ.get("PLAN_ENTERPRISE_PURCHASABLE", "false").lower() == "true"
        ),
        trial_duration_days=int(os.environ.get("TRIAL_DURATION_DAYS", "14")),
    )
