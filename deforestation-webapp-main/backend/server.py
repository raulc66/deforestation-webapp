"""Application entrypoint - clean composition over the layered architecture.

Layers:
  /app/backend/app/
    core/         -> config, logging, db, security, errors
    models/       -> Pydantic domain models (ForestEvent, DataSource,
                     Notification, User)
    repositories/ -> persistence (one collection per repo)
    services/     -> business logic
    api/          -> FastAPI route modules
    modules/      -> placeholder feature modules (planned)
"""
from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from fastapi import FastAPI, APIRouter
from fastapi.exceptions import RequestValidationError
from starlette.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.core.database import get_db, close_db
from app.core.errors import AppError, app_error_handler, validation_error_handler, unhandled_error_handler
from app.core.migrations import migrate_datetime_strings, backfill_geojson_location
from app.api.auth_routes import router as auth_router
from app.api.alert_routes import router as alert_router
from app.api.event_routes import router as event_router
from app.api.notification_routes import router as notification_router
from app.api.data_source_routes import router as data_source_router
from app.api.import_routes import router as import_router
from app.api.monitoring_area_routes import router as monitoring_area_router
from app.api.organization_routes import router as organization_router
from app.api.customer_alert_routes import router as customer_alert_router
from app.api.billing_routes import router as billing_router
from app.api.demo_routes import router as demo_router
from app.api.trial_routes import router as trial_router
from app.api.module_routes import router as module_router
from app.modules.analytics.analytics_routes import router as analytics_router
from app.repositories.user_repository import UserRepository
from app.repositories.forest_event_repository import ForestEventRepository
from app.repositories.data_source_repository import DataSourceRepository
from app.services.auth_service import AuthService
from app.services.forest_event_service import ForestEventService
from app.services.forest_context_service import ForestContextService
from app.services.data_source_service import DataSourceService
from app.services.romania_seed_service import seed_romania_intelligence
from app.services.scheduler_service import SchedulerService
from app.modules.analytics.analytics_repository import AnalyticsRepository
from app.modules.analytics.analytics_service import AnalyticsService
from app.modules.analytics.intelligence_events_repository import IntelligenceEventsRepository
from app.modules.analytics.intelligence_events_service import IntelligenceEventsService
from app.modules.analytics.history_repository import HistoryRepository
from app.modules.analytics.risk_repository import RiskRepository
from app.modules.analytics.risk_service import RiskService
from app.repositories.intelligence_cycle_repository import IntelligenceCycleRepository
from app.modules.ingestion.provider_registry import build_ingestion_providers
from app.modules.ingestion.providers.firms import FIRMSProvider


def _build_ingestion_providers(settings):
    """Backward-compatible alias."""
    return build_ingestion_providers(settings)


from app.repositories.ingestion_runs_repository import IngestionRunsRepository
from app.repositories.notification_history_repository import NotificationHistoryRepository
from app.services.intelligence_notification_service import (
    IntelligenceNotificationService,
    build_providers,
)
from app.repositories.weather_cache_repository import WeatherCacheRepository
from app.services.weather_provider import OpenMeteoProvider
from app.services.weather_service import WeatherService
from app.modules.reports.report_repository import ReportRepository
from app.modules.reports.report_service import ReportService
from app.modules.reports.report_routes import router as reports_router
from app.modules.investigations.investigation_routes import router as investigations_router


logger = setup_logging()
settings = get_settings()

app = FastAPI(
    title="ForestWatch API",
    version="0.3.0",
    swagger_ui_parameters={"persistAuthorization": True},
)

# CORS: allow frontend origin + credentials
origins = (
    [o.strip() for o in settings.cors_origins.split(",")]
    if settings.cors_origins and settings.cors_origins != "*"
    else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Error handlers
app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)

# Main API router with /api prefix
api_router = APIRouter(prefix="/api")


@api_router.get("/")
async def root():
    return {"service": "ForestWatch API", "version": "0.3.0", "status": "ok"}


@api_router.get("/health")
async def health():
    return {"status": "healthy"}


api_router.include_router(auth_router)
api_router.include_router(data_source_router)      # /api/data-sources
api_router.include_router(event_router)            # /api/events (canonical)
api_router.include_router(alert_router)            # /api/alerts (legacy compat)
api_router.include_router(notification_router)     # /api/notifications
api_router.include_router(import_router)           # /api/import/csv, /import/status
api_router.include_router(analytics_router)        # /api/analytics/*
api_router.include_router(monitoring_area_router)  # /api/monitoring-areas/*
api_router.include_router(organization_router)     # /api/organizations/*
api_router.include_router(customer_alert_router)   # /api/customer-alerts/*
api_router.include_router(billing_router)          # /api/billing/*
api_router.include_router(demo_router)             # /api/demo/*
api_router.include_router(trial_router)            # /api/trial/*
api_router.include_router(module_router)
api_router.include_router(reports_router, prefix="/reports")  # /api/reports/*
api_router.include_router(investigations_router)  # /api/investigations/*
app.include_router(api_router)


@app.on_event("startup")
async def startup():
    db = get_db()

    # Drop legacy `alerts` collection if it still holds the old schema
    try:
        if "alerts" in await db.list_collection_names():
            await db.drop_collection("alerts")
            logger.info("Dropped legacy alerts collection")
    except Exception as e:
        logger.warning("Could not drop legacy alerts collection: %s", e)

    # Indexes
    await db.users.create_index("email", unique=True)
    await db.data_sources.create_index("name", unique=True)
    await db.data_sources.create_index("type")
    await db.forest_events.create_index("severity")
    await db.forest_events.create_index("event_type")
    await db.forest_events.create_index("country")
    await db.forest_events.create_index("source_id")
    await db.forest_events.create_index("detected_at")
    await db.forest_events.create_index("metadata.dedupe_key", sparse=True)
    # 2dsphere index powers $nearSphere and $geoWithin queries
    await db.forest_events.create_index([("location", "2dsphere")])
    await db.notifications.create_index("recipient_user_id")
    await db.notifications.create_index("forest_event_id")
    await db.notifications.create_index("created_at")
    await db.import_jobs.create_index("created_at")
    await db.import_jobs.create_index("status")
    # Intelligence event indexes are ensured by migrate_intelligence_events_canonical
    # (WP8.3). Creating them here under a new name would fail if Mongo already has
    # the same keys as the auto-generated index.
    # Ingestion run history — newest-first for status endpoint
    await db.ingestion_runs.create_index([("started_at", -1)])
    # Notification history — newest-first for status endpoint
    await db.notification_history.create_index([("sent_at", -1)])
    # Risk history — date dedup key + newest-first for trend queries
    await db.risk_history.create_index("date", unique=True)
    await db.risk_history.create_index([("created_at", -1)])
    # Weather cache — unique per region + fast staleness query
    await db.weather_cache.create_index("region", unique=True)
    await db.weather_cache.create_index([("cached_at", -1)])
    # Reports — newest-first retrieval; de-dup scheduled reports by type + period
    await db.reports.create_index([("generated_at", -1)])
    await db.reports.create_index([("type", 1), ("period_start", 1)])
    # Investigations — workflow queries
    await db.investigations.create_index([("status", 1), ("priority", 1)])
    await db.investigations.create_index([("updated_at", -1)])
    await db.investigations.create_index("intelligence_event_id", sparse=True)
    await db.investigations.create_index("region")
    await db.investigation_timeline.create_index(
        [("investigation_id", 1), ("created_at", 1)]
    )
    # Tenant forest monitoring areas — tenant isolation + geospatial queries
    await db.forest_monitoring_areas.create_index("tenant_id")
    await db.forest_monitoring_areas.create_index("organization_id")
    await db.forest_monitoring_areas.create_index([("geometry", "2dsphere")])
    # Organizations and commercial entitlements
    await db.organizations.create_index("slug", unique=True)
    await db.organization_memberships.create_index(
        [("organization_id", 1), ("user_id", 1)],
        unique=True,
        name="org_user_unique",
    )
    await db.organization_memberships.create_index("user_id")
    await db.organization_entitlements.create_index(
        [("organization_id", 1), ("entitlement_type", 1)],
        name="org_entitlement_type",
    )
    await db.alert_policies.create_index("organization_id")
    await db.organization_notification_channels.create_index("organization_id")
    await db.alert_deliveries.create_index("dedupe_key", unique=True)
    await db.alert_deliveries.create_index("organization_id")
    await db.alert_deliveries.create_index("lifecycle")
    # Delivery history reads and the cooldown window query.
    await db.alert_deliveries.create_index(
        [("organization_id", 1), ("created_at", -1)],
        name="org_delivery_history",
    )
    await db.alert_deliveries.create_index(
        [("organization_id", 1), ("policy_id", 1), ("created_at", -1)],
        name="org_policy_cooldown",
    )
    # Billing — one Stripe customer and one subscription of record per
    # organization; the unique event id is what makes webhooks idempotent.
    await db.billing_customers.create_index("organization_id", unique=True)
    await db.billing_customers.create_index("stripe_customer_id", unique=True)
    await db.organization_subscriptions.create_index("organization_id", unique=True)
    await db.organization_subscriptions.create_index(
        "stripe_subscription_id",
        unique=True,
        sparse=True,
    )
    await db.billing_events.create_index("stripe_event_id", unique=True)
    await db.billing_events.create_index([("received_at", -1)])
    await db.billing_events.create_index(
        [("organization_id", 1), ("received_at", -1)],
        name="org_billing_event_history",
    )

    # Migrate legacy tenant AOIs to personal organizations (idempotent)
    try:
        from app.repositories.forest_monitoring_area_repository import (
            ForestMonitoringAreaRepository,
        )
        from app.repositories.organization_entitlement_repository import (
            OrganizationEntitlementRepository,
        )
        from app.repositories.organization_membership_repository import (
            OrganizationMembershipRepository,
        )
        from app.repositories.organization_repository import OrganizationRepository
        from app.repositories.user_repository import UserRepository
        from app.services.entitlement_service import EntitlementService
        from app.services.organization_bootstrap_service import (
            OrganizationBootstrapService,
        )

        bootstrap = OrganizationBootstrapService(
            OrganizationRepository(db),
            OrganizationMembershipRepository(db),
            ForestMonitoringAreaRepository(db),
            UserRepository(db),
            EntitlementService(
                OrganizationEntitlementRepository(db),
                ForestMonitoringAreaRepository(db),
            ),
        )
        migrated_users = await bootstrap.migrate_all_users()
        if migrated_users:
            logger.info(
                "Organization bootstrap: ensured personal orgs for %d user(s)",
                migrated_users,
            )
    except Exception as exc:
        logger.warning("Organization bootstrap migration skipped: %s", exc)

    # Migrate legacy string-typed datetime fields to BSON datetime so that
    # sorting and range queries work correctly.
    migrated = await migrate_datetime_strings(db)
    if migrated:
        logger.info("Datetime migration: converted %d field(s)", migrated)

    # Backfill GeoJSON `location` on events that predate the geo refactor.
    backfilled = await backfill_geojson_location(db)
    if backfilled:
        logger.info("Geo migration: backfilled %d event(s)", backfilled)

    from app.core.intelligence_events_migration import migrate_intelligence_events_canonical

    intel_migration = await migrate_intelligence_events_canonical(db)
    summary = intel_migration.as_dict()
    if (
        summary["category_backfill"]["backfilled"]
        or summary["canonical_rekey"]["rekeyed"]
        or summary["canonical_rekey"]["collisions_resolved"]
    ):
        logger.info("Intelligence events canonical migration: %s", summary)

    # Seed admin
    users = UserRepository(db)
    auth = AuthService(users)
    await auth.seed_admin(settings.admin_email, settings.admin_password)

    # Seed DataSources first (ForestEvents reference them)
    sources_repo = DataSourceRepository(db)
    source_svc = DataSourceService(sources_repo)
    name_to_id = await source_svc.seed_demo()
    logger.info("DataSource catalog: %d entries", len(name_to_id))

    # If existing forest_events still reference legacy string source_ids
    # (e.g. "satellite", "scraper"), drop and re-seed against real DataSource ids.
    valid_source_ids = set(name_to_id.values())
    stale = await db.forest_events.find_one(
        {"source_id": {"$nin": list(valid_source_ids)}}
    )
    if stale:
        await db.forest_events.delete_many({})
        logger.info("Re-seeding ForestEvents: stale source_id references found")

    events_repo = ForestEventRepository(db)
    forest_context_svc = ForestContextService(
        refresh_interval_days=settings.clms_refresh_interval_days,
    )
    app.state.forest_context_svc = forest_context_svc

    event_svc = ForestEventService(events_repo, sources_repo, forest_context_svc)
    n = await event_svc.seed_demo_data(list(valid_source_ids))
    logger.info("Global demo seed: %d ForestEvent records", n)

    # Romania intelligence seed — deterministic dataset that exercises anomaly
    # detection, baselines, temporal trends, and the intelligence event pipeline.
    # No-op when seed events already exist (idempotent).
    ro_n = await seed_romania_intelligence(events_repo, list(valid_source_ids))
    if ro_n:
        logger.info("Romania intelligence seed: %d events inserted", ro_n)

    # Background ingestion scheduler — starts after all seeding is complete.
    firms_source_id = name_to_id.get("NASA FIRMS")
    analytics_repo = AnalyticsRepository(db)
    from app.repositories.correlation_repository import CorrelationRepository

    correlation_repo = CorrelationRepository(db)
    cycle_repo = IntelligenceCycleRepository(db)
    analytics_svc = AnalyticsService(
        analytics_repo,
        correlation_repo=correlation_repo,
        cycle_repo=cycle_repo,
    )
    intel_repo = IntelligenceEventsRepository(db)
    intel_svc = IntelligenceEventsService(
        intel_repo,
        include_provenance=settings.enable_intelligence_provenance,
        geographic_scope=settings.geographic_scope,
    )
    runs_repo = IngestionRunsRepository(db)

    # Outbound notification service — active only when at least one provider is configured.
    notif_providers = build_providers(
        discord_webhook_url=settings.discord_webhook_url if settings.enable_notifications else "",
        generic_webhook_url=settings.generic_webhook_url if settings.enable_notifications else "",
    )
    notif_history_repo = NotificationHistoryRepository(db)
    notification_svc = IntelligenceNotificationService(notif_providers, notif_history_repo)
    app.state.notification_svc = notification_svc

    history_repo = HistoryRepository(db)
    risk_repo = RiskRepository(db)

    # Weather service — provider + MongoDB cache
    weather_cache_repo = WeatherCacheRepository(db)
    weather_svc = WeatherService(
        provider=OpenMeteoProvider(),
        cache_repo=weather_cache_repo,
        cache_ttl_minutes=settings.weather_cache_ttl_minutes,
    )
    app.state.weather_svc = weather_svc

    risk_svc = RiskService(
        analytics_svc=analytics_svc,
        history_repo=history_repo,
        intel_events_repo=intel_repo,
        risk_repo=risk_repo,
        weather_svc=weather_svc,
    )

    # Reporting service — generates PDF/CSV/JSON reports on demand and on schedule
    reports_dir = Path(settings.reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)
    from app.modules.analytics.history_service import HistoryService
    from app.modules.analytics.threat_assessment_service import ThreatAssessmentService
    from app.repositories.investigation_repository import InvestigationRepository
    from app.repositories.investigation_timeline_repository import InvestigationTimelineRepository
    from app.modules.investigations.investigation_service import InvestigationService
    history_svc = HistoryService(history_repo)
    report_repo = ReportRepository(db)
    threat_svc = ThreatAssessmentService(intel_svc)
    inv_repo = InvestigationRepository(db)
    inv_timeline_repo = InvestigationTimelineRepository(db)
    investigation_svc = InvestigationService(
        inv_repo, inv_timeline_repo, intel_repo=intel_repo, notification_svc=notification_svc
    )
    report_svc = ReportService(
        report_repo=report_repo,
        analytics_svc=analytics_svc,
        intel_svc=intel_svc,
        risk_svc=risk_svc,
        history_svc=history_svc,
        notif_history_repo=notif_history_repo,
        runs_repo=runs_repo,
        weather_svc=weather_svc,
        threat_svc=threat_svc,
        investigation_svc=investigation_svc,
        reports_dir=reports_dir,
    )
    app.state.report_svc = report_svc

    from app.repositories.reconciliation_lock_repository import ReconciliationLockRepository
    from app.services.reconciliation_advisory_lock import ReconciliationAdvisoryLock

    reconciliation_lock = ReconciliationAdvisoryLock(
        ReconciliationLockRepository(db),
        lease_seconds=settings.reconciliation_lock_lease_seconds,
    )

    from app.repositories.provider_health_repository import ProviderHealthRepository

    health_repo = ProviderHealthRepository(db)
    app.state.provider_health_repo = health_repo
    ingestion_providers = _build_ingestion_providers(settings)
    app.state.ingestion_providers = ingestion_providers

    from app.repositories.organization_entitlement_repository import (
        OrganizationEntitlementRepository,
    )
    from app.repositories.alert_delivery_repository import AlertDeliveryRepository
    from app.repositories.alert_policy_repository import AlertPolicyRepository
    from app.repositories.forest_monitoring_area_repository import ForestMonitoringAreaRepository
    from app.repositories.organization_notification_channel_repository import (
        OrganizationNotificationChannelRepository,
    )
    from app.repositories.organization_repository import OrganizationRepository
    from app.services.customer_alert_dispatcher import CustomerAlertDispatcher
    from app.services.customer_alert_evaluation_service import CustomerAlertEvaluationService
    from app.services.customer_alert_notification_service import CustomerAlertNotificationService
    from app.services.entitlement_service import EntitlementService
    from app.services.notifications.email_sender import FakeEmailSender, SmtpEmailSender

    org_repo = OrganizationRepository(db)
    policy_repo = AlertPolicyRepository(db)
    delivery_repo = AlertDeliveryRepository(db)
    channel_repo = OrganizationNotificationChannelRepository(db)
    area_repo = ForestMonitoringAreaRepository(db)
    entitlement_repo = OrganizationEntitlementRepository(db)
    entitlement_svc = EntitlementService(entitlement_repo, area_repo)
    email_sender = FakeEmailSender()
    smtp_sender = SmtpEmailSender(
        host=getattr(settings, "smtp_host", "") or "",
        port=int(getattr(settings, "smtp_port", 587) or 587),
        username=getattr(settings, "smtp_username", "") or "",
        password=getattr(settings, "smtp_password", "") or "",
        from_address=getattr(settings, "smtp_from_address", "") or "",
    )
    if smtp_sender.is_configured:
        email_sender = smtp_sender
    customer_alert_svc = CustomerAlertNotificationService(
        CustomerAlertEvaluationService(
            org_repo=org_repo,
            policy_repo=policy_repo,
            delivery_repo=delivery_repo,
            area_repo=area_repo,
            entitlement_svc=entitlement_svc,
        ),
        CustomerAlertDispatcher(
            delivery_repo=delivery_repo,
            policy_repo=policy_repo,
            channel_repo=channel_repo,
            area_repo=area_repo,
            intel_repo=intel_repo,
            email_sender=email_sender,
            app_secret=settings.jwt_secret,
        ),
    )
    app.state.customer_alert_svc = customer_alert_svc

    scheduler = SchedulerService(
        firms_provider=FIRMSProvider(api_key=settings.firms_api_key),
        events_service=event_svc,
        events_repo=events_repo,
        analytics_service=analytics_svc,
        intelligence_service=intel_svc,
        runs_repo=runs_repo,
        poll_interval_minutes=settings.firms_poll_interval_minutes,
        enabled=settings.enable_background_ingestion,
        firms_source_id=firms_source_id,
        notification_svc=notification_svc,
        customer_alert_svc=customer_alert_svc,
        risk_svc=risk_svc,
        weather_svc=weather_svc,
        forest_context_svc=forest_context_svc,
        report_svc=report_svc,
        enable_scheduled_reports=settings.enable_scheduled_reports,
        reconciliation_lock=reconciliation_lock,
        ingestion_providers=ingestion_providers,
        health_repo=health_repo,
    )
    app.state.scheduler = scheduler
    await scheduler.start()

    logger.info("Startup complete")


@app.on_event("shutdown")
async def shutdown():
    scheduler: SchedulerService | None = getattr(app.state, "scheduler", None)
    if scheduler:
        await scheduler.stop()
    await close_db()
