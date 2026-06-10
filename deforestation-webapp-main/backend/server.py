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
from app.api.module_routes import router as module_router
from app.modules.analytics.analytics_routes import router as analytics_router
from app.repositories.user_repository import UserRepository
from app.repositories.forest_event_repository import ForestEventRepository
from app.repositories.data_source_repository import DataSourceRepository
from app.services.auth_service import AuthService
from app.services.forest_event_service import ForestEventService
from app.services.data_source_service import DataSourceService


logger = setup_logging()
settings = get_settings()

app = FastAPI(title="ForestWatch API", version="0.3.0")

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
api_router.include_router(module_router)
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
    # 2dsphere index powers $nearSphere and $geoWithin queries
    await db.forest_events.create_index([("location", "2dsphere")])
    await db.notifications.create_index("recipient_user_id")
    await db.notifications.create_index("forest_event_id")
    await db.notifications.create_index("created_at")
    await db.import_jobs.create_index("created_at")
    await db.import_jobs.create_index("status")

    # Migrate legacy string-typed datetime fields to BSON datetime so that
    # sorting and range queries work correctly.
    migrated = await migrate_datetime_strings(db)
    if migrated:
        logger.info("Datetime migration: converted %d field(s)", migrated)

    # Backfill GeoJSON `location` on events that predate the geo refactor.
    backfilled = await backfill_geojson_location(db)
    if backfilled:
        logger.info("Geo migration: backfilled %d event(s)", backfilled)

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
    event_svc = ForestEventService(events_repo, sources_repo)
    n = await event_svc.seed_demo_data(list(valid_source_ids))
    logger.info("Startup complete - seeded %d ForestEvent records", n)


@app.on_event("shutdown")
async def shutdown():
    await close_db()
