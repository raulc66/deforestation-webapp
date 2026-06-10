"""Shared FastAPI dependencies."""
from fastapi import Depends, Request
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.database import get_db
from app.core.errors import AuthError
from app.repositories.user_repository import UserRepository
from app.repositories.forest_event_repository import ForestEventRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.data_source_repository import DataSourceRepository
from app.repositories.import_job_repository import ImportJobRepository
from app.services.auth_service import AuthService
from app.services.forest_event_service import ForestEventService
from app.services.notification_service import NotificationService
from app.services.data_source_service import DataSourceService
from app.services.alert_service import AlertService
from app.modules.ingestion.csv_importer import CsvImporter
from app.modules.analytics.analytics_repository import AnalyticsRepository
from app.modules.analytics.analytics_service import AnalyticsService
from app.models.user import UserPublic


def db_dep() -> AsyncIOMotorDatabase:
    return get_db()


# --- Repositories ---------------------------------------------------------

def user_repo_dep(db: AsyncIOMotorDatabase = Depends(db_dep)) -> UserRepository:
    return UserRepository(db)


def forest_event_repo_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
) -> ForestEventRepository:
    return ForestEventRepository(db)


def notification_repo_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
) -> NotificationRepository:
    return NotificationRepository(db)


def data_source_repo_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
) -> DataSourceRepository:
    return DataSourceRepository(db)


def import_job_repo_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
) -> ImportJobRepository:
    return ImportJobRepository(db)


# --- Services -------------------------------------------------------------

def auth_service_dep(users: UserRepository = Depends(user_repo_dep)) -> AuthService:
    return AuthService(users)


def data_source_service_dep(
    repo: DataSourceRepository = Depends(data_source_repo_dep),
) -> DataSourceService:
    return DataSourceService(repo)


def forest_event_service_dep(
    events: ForestEventRepository = Depends(forest_event_repo_dep),
    sources: DataSourceRepository = Depends(data_source_repo_dep),
) -> ForestEventService:
    return ForestEventService(events, sources)


def notification_service_dep(
    repo: NotificationRepository = Depends(notification_repo_dep),
) -> NotificationService:
    return NotificationService(repo)


def alert_service_dep(
    events: ForestEventService = Depends(forest_event_service_dep),
) -> AlertService:
    """Legacy AlertService is now a thin adapter over ForestEventService."""
    return AlertService(events)


def csv_importer_dep(
    jobs: ImportJobRepository = Depends(import_job_repo_dep),
    sources: DataSourceRepository = Depends(data_source_repo_dep),
    events: ForestEventService = Depends(forest_event_service_dep),
) -> CsvImporter:
    return CsvImporter(jobs, sources, events)


def analytics_repo_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
) -> AnalyticsRepository:
    return AnalyticsRepository(db)


def analytics_service_dep(
    repo: AnalyticsRepository = Depends(analytics_repo_dep),
) -> AnalyticsService:
    return AnalyticsService(repo)


# --- Auth dependency ------------------------------------------------------

async def get_current_user(
    request: Request,
    auth_service: AuthService = Depends(auth_service_dep),
) -> UserPublic:
    """Read access token from cookie OR Authorization header."""
    token = request.cookies.get("access_token")
    if not token:
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            token = header[7:]
    if not token:
        raise AuthError("Not authenticated")
    return await auth_service.get_user_from_token(token)
