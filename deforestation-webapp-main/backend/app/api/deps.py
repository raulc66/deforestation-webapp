"""Shared FastAPI dependencies."""
from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
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
from app.modules.analytics.intelligence_events_repository import IntelligenceEventsRepository
from app.modules.analytics.intelligence_events_service import IntelligenceEventsService
from app.repositories.ingestion_runs_repository import IngestionRunsRepository
from app.repositories.notification_history_repository import NotificationHistoryRepository
from app.modules.analytics.history_repository import HistoryRepository
from app.modules.analytics.history_service import HistoryService
from app.modules.analytics.risk_repository import RiskRepository
from app.modules.analytics.risk_service import RiskService
from app.modules.analytics.command_center_service import CommandCenterService
from app.modules.analytics.threat_assessment_service import ThreatAssessmentService
from app.repositories.weather_cache_repository import WeatherCacheRepository
from app.services.weather_service import WeatherService
from app.modules.reports.report_repository import ReportRepository
from app.modules.reports.report_service import ReportService
from app.repositories.investigation_repository import InvestigationRepository
from app.repositories.investigation_timeline_repository import InvestigationTimelineRepository
from app.modules.investigations.investigation_service import InvestigationService
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
    events_repo: ForestEventRepository = Depends(forest_event_repo_dep),
) -> CsvImporter:
    return CsvImporter(jobs, sources, events, events_repo)


def analytics_repo_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
) -> AnalyticsRepository:
    return AnalyticsRepository(db)


def analytics_service_dep(
    repo: AnalyticsRepository = Depends(analytics_repo_dep),
) -> AnalyticsService:
    return AnalyticsService(repo)


def intelligence_events_repo_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
) -> IntelligenceEventsRepository:
    return IntelligenceEventsRepository(db)


def intelligence_events_service_dep(
    repo: IntelligenceEventsRepository = Depends(intelligence_events_repo_dep),
) -> IntelligenceEventsService:
    return IntelligenceEventsService(repo)


def threat_assessment_service_dep(
    intel_svc: IntelligenceEventsService = Depends(intelligence_events_service_dep),
) -> ThreatAssessmentService:
    return ThreatAssessmentService(intel_svc)


def ingestion_runs_repo_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
) -> IngestionRunsRepository:
    return IngestionRunsRepository(db)


def notification_history_repo_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
) -> NotificationHistoryRepository:
    return NotificationHistoryRepository(db)


def history_repo_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
) -> HistoryRepository:
    return HistoryRepository(db)


def history_service_dep(
    repo: HistoryRepository = Depends(history_repo_dep),
) -> HistoryService:
    return HistoryService(repo)


def risk_repo_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
) -> RiskRepository:
    return RiskRepository(db)


def weather_cache_repo_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
) -> WeatherCacheRepository:
    return WeatherCacheRepository(db)


def weather_service_dep(
    cache_repo: WeatherCacheRepository = Depends(weather_cache_repo_dep),
) -> WeatherService:
    from app.services.weather_provider import OpenMeteoProvider
    return WeatherService(provider=OpenMeteoProvider(), cache_repo=cache_repo)


def risk_service_dep(
    analytics_svc: AnalyticsService = Depends(analytics_service_dep),
    history_repo: HistoryRepository = Depends(history_repo_dep),
    intel_events_repo: IntelligenceEventsRepository = Depends(intelligence_events_repo_dep),
    risk_repo: RiskRepository = Depends(risk_repo_dep),
    weather_svc: WeatherService = Depends(weather_service_dep),
) -> RiskService:
    return RiskService(analytics_svc, history_repo, intel_events_repo, risk_repo, weather_svc=weather_svc)


def investigation_repo_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
) -> InvestigationRepository:
    return InvestigationRepository(db)


def investigation_timeline_repo_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
) -> InvestigationTimelineRepository:
    return InvestigationTimelineRepository(db)


def investigation_service_dep(
    request: Request,
    repo: InvestigationRepository = Depends(investigation_repo_dep),
    timeline_repo: InvestigationTimelineRepository = Depends(investigation_timeline_repo_dep),
    intel_repo: IntelligenceEventsRepository = Depends(intelligence_events_repo_dep),
) -> InvestigationService:
    notification_svc = getattr(request.app.state, "notification_svc", None)
    return InvestigationService(
        repo, timeline_repo, intel_repo=intel_repo, notification_svc=notification_svc
    )


def command_center_service_dep(
    analytics_svc: AnalyticsService = Depends(analytics_service_dep),
    intel_svc: IntelligenceEventsService = Depends(intelligence_events_service_dep),
    weather_svc: WeatherService = Depends(weather_service_dep),
    threat_svc: ThreatAssessmentService = Depends(threat_assessment_service_dep),
    investigation_svc: InvestigationService = Depends(investigation_service_dep),
) -> CommandCenterService:
    return CommandCenterService(
        analytics_svc, intel_svc, weather_svc=weather_svc, threat_svc=threat_svc,
        investigation_svc=investigation_svc,
    )


def report_repo_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
) -> ReportRepository:
    return ReportRepository(db)


def report_service_dep(
    report_repo: ReportRepository = Depends(report_repo_dep),
    analytics_svc: AnalyticsService = Depends(analytics_service_dep),
    intel_svc: IntelligenceEventsService = Depends(intelligence_events_service_dep),
    risk_svc: RiskService = Depends(risk_service_dep),
    history_svc: HistoryService = Depends(history_service_dep),
    notif_history_repo: NotificationHistoryRepository = Depends(notification_history_repo_dep),
    runs_repo: IngestionRunsRepository = Depends(ingestion_runs_repo_dep),
    weather_svc: WeatherService = Depends(weather_service_dep),
    threat_svc: ThreatAssessmentService = Depends(threat_assessment_service_dep),
    investigation_svc: InvestigationService = Depends(investigation_service_dep),
) -> ReportService:
    from pathlib import Path
    from app.core.config import get_settings
    reports_dir = Path(get_settings().reports_dir)
    return ReportService(
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


# --- Auth dependency ------------------------------------------------------

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    auth_service: AuthService = Depends(auth_service_dep),
) -> UserPublic:
    """Read access token from cookie (browser) or Authorization: Bearer (Swagger/API clients)."""
    token = request.cookies.get("access_token")
    if not token and credentials:
        token = credentials.credentials
    if not token:
        raise AuthError("Not authenticated")
    return await auth_service.get_user_from_token(token)
