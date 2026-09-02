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
from app.services.forest_context_service import ForestContextService
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
from app.repositories.provider_health_repository import ProviderHealthRepository
from app.repositories.correlation_repository import CorrelationRepository
from app.repositories.intelligence_cycle_repository import IntelligenceCycleRepository
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


def forest_context_service_dep() -> ForestContextService:
    refresh_days = 30
    try:
        from app.core.config import get_settings

        refresh_days = get_settings().clms_refresh_interval_days
    except Exception:
        pass
    return ForestContextService(refresh_interval_days=refresh_days)


def forest_event_service_dep(
    events: ForestEventRepository = Depends(forest_event_repo_dep),
    sources: DataSourceRepository = Depends(data_source_repo_dep),
    forest_context_svc: ForestContextService = Depends(forest_context_service_dep),
) -> ForestEventService:
    return ForestEventService(events, sources, forest_context_svc)


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


def correlation_repo_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
) -> CorrelationRepository:
    return CorrelationRepository(db)


def intelligence_cycle_repo_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
) -> IntelligenceCycleRepository:
    return IntelligenceCycleRepository(db)


def correlation_service_dep(
    repo: CorrelationRepository = Depends(correlation_repo_dep),
):
    from app.services.correlation_service import CorrelationService

    return CorrelationService(repo)


def analytics_service_dep(
    repo: AnalyticsRepository = Depends(analytics_repo_dep),
    correlation_repo: CorrelationRepository = Depends(correlation_repo_dep),
    cycle_repo: IntelligenceCycleRepository = Depends(intelligence_cycle_repo_dep),
) -> AnalyticsService:
    return AnalyticsService(repo, correlation_repo=correlation_repo, cycle_repo=cycle_repo)


def intelligence_events_repo_dep(
    request: Request,
    db: AsyncIOMotorDatabase = Depends(db_dep),
) -> IntelligenceEventsRepository:
    from app.core.demo.constants import DEMO_INTEL_COLLECTION, DEMO_TOKEN_TYPE
    from app.core.security import decode_token

    token = request.cookies.get("access_token")
    if not token:
        header = request.headers.get("authorization") or ""
        if header.lower().startswith("bearer "):
            token = header.split(" ", 1)[1].strip()
    if token:
        try:
            payload = decode_token(token)
            if payload.get("type") == DEMO_TOKEN_TYPE:
                return IntelligenceEventsRepository(
                    db, collection_name=DEMO_INTEL_COLLECTION
                )
        except Exception:
            pass
    return IntelligenceEventsRepository(db)


def intelligence_events_service_dep(
    repo: IntelligenceEventsRepository = Depends(intelligence_events_repo_dep),
) -> IntelligenceEventsService:
    from app.core.config import get_settings

    settings = get_settings()
    return IntelligenceEventsService(
        repo,
        include_provenance=settings.enable_intelligence_provenance,
        geographic_scope=settings.geographic_scope,
    )


def threat_assessment_service_dep(
    intel_svc: IntelligenceEventsService = Depends(intelligence_events_service_dep),
) -> ThreatAssessmentService:
    return ThreatAssessmentService(intel_svc)


def ingestion_runs_repo_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
) -> IngestionRunsRepository:
    return IngestionRunsRepository(db)


def provider_health_repo_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
) -> ProviderHealthRepository:
    return ProviderHealthRepository(db)


def evidence_aware_command_center_dep(
    intel_repo: IntelligenceEventsRepository = Depends(intelligence_events_repo_dep),
    correlation_repo: CorrelationRepository = Depends(correlation_repo_dep),
    cycle_repo: IntelligenceCycleRepository = Depends(intelligence_cycle_repo_dep),
    health_repo: ProviderHealthRepository = Depends(provider_health_repo_dep),
):
    from app.services.evidence_aware_command_center_service import (
        EvidenceAwareCommandCenterService,
    )

    return EvidenceAwareCommandCenterService(
        intel_repo,
        correlation_repo,
        cycle_repo,
        health_repo,
    )


def source_intelligence_service_dep(
    request: Request,
    health_repo: ProviderHealthRepository = Depends(provider_health_repo_dep),
    forest_context_svc: ForestContextService = Depends(forest_context_service_dep),
):
    from app.core.config import get_settings
    from app.modules.ingestion.provider_registry import build_ingestion_providers
    from app.services.source_intelligence_service import SourceIntelligenceService

    settings = get_settings()
    providers = getattr(request.app.state, "ingestion_providers", None)
    if providers is None:
        providers = build_ingestion_providers(settings)
    return SourceIntelligenceService(
        health_repo,
        settings=settings,
        ingestion_providers=providers,
        contextual_providers=[forest_context_svc.provider],
    )


def operational_status_service_dep(
    request: Request,
    source_intel=Depends(source_intelligence_service_dep),
    intel_repo: IntelligenceEventsRepository = Depends(intelligence_events_repo_dep),
    correlation_repo: CorrelationRepository = Depends(correlation_repo_dep),
    cycle_repo: IntelligenceCycleRepository = Depends(intelligence_cycle_repo_dep),
    health_repo: ProviderHealthRepository = Depends(provider_health_repo_dep),
    runs_repo: IngestionRunsRepository = Depends(ingestion_runs_repo_dep),
):
    from app.core.config import get_settings
    from app.services.operational_status_service import OperationalStatusService

    return OperationalStatusService(
        source_intel,
        intel_repo,
        correlation_repo,
        cycle_repo,
        health_repo,
        runs_repo,
        settings=get_settings(),
    )


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


def forest_monitoring_area_repo_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
):
    from app.repositories.forest_monitoring_area_repository import (
        ForestMonitoringAreaRepository,
    )

    return ForestMonitoringAreaRepository(db)


def organization_repo_dep(db: AsyncIOMotorDatabase = Depends(db_dep)):
    from app.repositories.organization_repository import OrganizationRepository

    return OrganizationRepository(db)


def organization_membership_repo_dep(db: AsyncIOMotorDatabase = Depends(db_dep)):
    from app.repositories.organization_membership_repository import (
        OrganizationMembershipRepository,
    )

    return OrganizationMembershipRepository(db)


def organization_entitlement_repo_dep(db: AsyncIOMotorDatabase = Depends(db_dep)):
    from app.repositories.organization_entitlement_repository import (
        OrganizationEntitlementRepository,
    )

    return OrganizationEntitlementRepository(db)


def entitlement_service_dep(
    entitlement_repo=Depends(organization_entitlement_repo_dep),
    area_repo=Depends(forest_monitoring_area_repo_dep),
):
    from app.services.entitlement_service import EntitlementService

    return EntitlementService(entitlement_repo, area_repo)


def organization_bootstrap_service_dep(
    org_repo=Depends(organization_repo_dep),
    membership_repo=Depends(organization_membership_repo_dep),
    area_repo=Depends(forest_monitoring_area_repo_dep),
    user_repo: UserRepository = Depends(user_repo_dep),
    entitlement_svc=Depends(entitlement_service_dep),
):
    from app.services.organization_bootstrap_service import OrganizationBootstrapService

    return OrganizationBootstrapService(
        org_repo,
        membership_repo,
        area_repo,
        user_repo,
        entitlement_svc,
    )


def organization_context_service_dep(
    org_repo=Depends(organization_repo_dep),
    membership_repo=Depends(organization_membership_repo_dep),
    bootstrap_svc=Depends(organization_bootstrap_service_dep),
):
    from app.services.organization_context_service import OrganizationContextService

    return OrganizationContextService(org_repo, membership_repo, bootstrap_svc)


def organization_service_dep(
    org_repo=Depends(organization_repo_dep),
    membership_repo=Depends(organization_membership_repo_dep),
    user_repo: UserRepository = Depends(user_repo_dep),
    entitlement_svc=Depends(entitlement_service_dep),
):
    from app.services.organization_service import OrganizationService

    return OrganizationService(org_repo, membership_repo, user_repo, entitlement_svc)


def monitoring_area_service_dep(
    repo=Depends(forest_monitoring_area_repo_dep),
    entitlement_svc=Depends(entitlement_service_dep),
):
    from app.services.forest_monitoring_area_service import ForestMonitoringAreaService

    return ForestMonitoringAreaService(repo, entitlement_svc=entitlement_svc)


def monitoring_area_read_model_service_dep(
    area_svc=Depends(monitoring_area_service_dep),
    intel_repo: IntelligenceEventsRepository = Depends(intelligence_events_repo_dep),
):
    from app.services.aoi_intelligence_summary_service import AoiIntelligenceSummaryService
    from app.services.monitoring_area_read_model_service import MonitoringAreaReadModelService

    return MonitoringAreaReadModelService(
        area_svc,
        intel_repo,
        summary_svc=AoiIntelligenceSummaryService(),
    )


def billing_customer_repo_dep(db: AsyncIOMotorDatabase = Depends(db_dep)):
    from app.repositories.billing_customer_repository import BillingCustomerRepository

    return BillingCustomerRepository(db)


def organization_subscription_repo_dep(db: AsyncIOMotorDatabase = Depends(db_dep)):
    from app.repositories.organization_subscription_repository import (
        OrganizationSubscriptionRepository,
    )

    return OrganizationSubscriptionRepository(db)


def billing_event_repo_dep(db: AsyncIOMotorDatabase = Depends(db_dep)):
    from app.repositories.billing_event_repository import BillingEventRepository

    return BillingEventRepository(db)


def plan_catalog_dep():
    from app.core.commercial.plan_catalog import build_plan_catalog
    from app.core.config import get_settings

    return build_plan_catalog(get_settings())


def stripe_gateway_dep():
    from app.core.config import get_settings
    from app.services.billing.stripe_gateway import build_stripe_gateway

    return build_stripe_gateway(get_settings())


def entitlement_sync_service_dep(
    entitlement_repo=Depends(organization_entitlement_repo_dep),
    catalog=Depends(plan_catalog_dep),
):
    from app.services.billing.entitlement_sync_service import EntitlementSyncService

    return EntitlementSyncService(entitlement_repo, catalog)


def billing_service_dep(
    catalog=Depends(plan_catalog_dep),
    gateway=Depends(stripe_gateway_dep),
    customer_repo=Depends(billing_customer_repo_dep),
    subscription_repo=Depends(organization_subscription_repo_dep),
    event_repo=Depends(billing_event_repo_dep),
    entitlement_svc=Depends(entitlement_service_dep),
    org_repo=Depends(organization_repo_dep),
):
    from app.core.config import get_settings
    from app.services.billing.billing_service import BillingService, BillingUrls

    settings = get_settings()
    return BillingService(
        catalog=catalog,
        gateway=gateway,
        customer_repo=customer_repo,
        subscription_repo=subscription_repo,
        event_repo=event_repo,
        entitlement_svc=entitlement_svc,
        urls=BillingUrls.from_settings(settings),
        organization_repo=org_repo,
        billing_live=settings.enable_billing,
    )


def stripe_webhook_service_dep(
    catalog=Depends(plan_catalog_dep),
    customer_repo=Depends(billing_customer_repo_dep),
    subscription_repo=Depends(organization_subscription_repo_dep),
    event_repo=Depends(billing_event_repo_dep),
    entitlement_sync=Depends(entitlement_sync_service_dep),
    org_repo=Depends(organization_repo_dep),
):
    from app.core.config import get_settings
    from app.services.billing.stripe_webhook_service import StripeWebhookService

    settings = get_settings()
    return StripeWebhookService(
        event_repo=event_repo,
        customer_repo=customer_repo,
        subscription_repo=subscription_repo,
        entitlement_sync=entitlement_sync,
        catalog=catalog,
        webhook_secret=settings.stripe_webhook_secret,
        organization_repo=org_repo,
        signature_tolerance_seconds=settings.stripe_webhook_tolerance_seconds,
    )


def alert_policy_repo_dep(db: AsyncIOMotorDatabase = Depends(db_dep)):
    from app.repositories.alert_policy_repository import AlertPolicyRepository

    return AlertPolicyRepository(db)


def alert_delivery_repo_dep(db: AsyncIOMotorDatabase = Depends(db_dep)):
    from app.repositories.alert_delivery_repository import AlertDeliveryRepository

    return AlertDeliveryRepository(db)


def organization_notification_channel_repo_dep(db: AsyncIOMotorDatabase = Depends(db_dep)):
    from app.repositories.organization_notification_channel_repository import (
        OrganizationNotificationChannelRepository,
    )

    return OrganizationNotificationChannelRepository(db)


def alert_policy_service_dep(
    policy_repo=Depends(alert_policy_repo_dep),
    channel_repo=Depends(organization_notification_channel_repo_dep),
    delivery_repo=Depends(alert_delivery_repo_dep),
    entitlement_svc=Depends(entitlement_service_dep),
    area_repo=Depends(forest_monitoring_area_repo_dep),
):
    from app.core.config import get_settings
    from app.services.alert_policy_service import AlertPolicyService

    return AlertPolicyService(
        policy_repo,
        channel_repo,
        delivery_repo,
        entitlement_svc,
        app_secret=get_settings().jwt_secret,
        area_repo=area_repo,
    )


def trial_service_dep(
    org_repo=Depends(organization_repo_dep),
    membership_repo=Depends(organization_membership_repo_dep),
    user_repo: UserRepository = Depends(user_repo_dep),
    bootstrap_svc=Depends(organization_bootstrap_service_dep),
    entitlement_svc=Depends(entitlement_service_dep),
    area_repo=Depends(forest_monitoring_area_repo_dep),
    policy_repo=Depends(alert_policy_repo_dep),
    channel_repo=Depends(organization_notification_channel_repo_dep),
):
    from app.core.config import get_settings
    from app.services.trial_service import TrialService

    settings = get_settings()
    return TrialService(
        org_repo,
        membership_repo,
        user_repo,
        bootstrap_svc,
        entitlement_svc,
        area_repo,
        policy_repo=policy_repo,
        channel_repo=channel_repo,
        duration_days=int(getattr(settings, "trial_duration_days", 14) or 14),
    )


def customer_alert_notification_service_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
    org_repo=Depends(organization_repo_dep),
    policy_repo=Depends(alert_policy_repo_dep),
    delivery_repo=Depends(alert_delivery_repo_dep),
    area_repo=Depends(forest_monitoring_area_repo_dep),
    channel_repo=Depends(organization_notification_channel_repo_dep),
    intel_repo: IntelligenceEventsRepository = Depends(intelligence_events_repo_dep),
    entitlement_svc=Depends(entitlement_service_dep),
):
    from app.core.config import get_settings
    from app.services.customer_alert_dispatcher import CustomerAlertDispatcher
    from app.services.customer_alert_evaluation_service import CustomerAlertEvaluationService
    from app.services.customer_alert_notification_service import CustomerAlertNotificationService
    from app.services.notifications.email_sender import FakeEmailSender, SmtpEmailSender

    settings = get_settings()
    email_sender = FakeEmailSender()
    smtp = SmtpEmailSender(
        host=getattr(settings, "smtp_host", "") or "",
        port=int(getattr(settings, "smtp_port", 587) or 587),
        username=getattr(settings, "smtp_username", "") or "",
        password=getattr(settings, "smtp_password", "") or "",
        from_address=getattr(settings, "smtp_from_address", "") or "",
    )
    if smtp.is_configured:
        email_sender = smtp

    evaluation = CustomerAlertEvaluationService(
        org_repo=org_repo,
        policy_repo=policy_repo,
        delivery_repo=delivery_repo,
        area_repo=area_repo,
        entitlement_svc=entitlement_svc,
    )
    dispatcher = CustomerAlertDispatcher(
        delivery_repo=delivery_repo,
        policy_repo=policy_repo,
        channel_repo=channel_repo,
        area_repo=area_repo,
        intel_repo=intel_repo,
        email_sender=email_sender,
        app_secret=settings.jwt_secret,
    )
    return CustomerAlertNotificationService(evaluation, dispatcher)


def aoi_enrichment_service_dep():
    from app.services.aoi_enrichment_service import AoiEnrichmentService

    return AoiEnrichmentService()


def customer_monitoring_status_service_dep(
    area_svc=Depends(monitoring_area_service_dep),
    intel_repo: IntelligenceEventsRepository = Depends(intelligence_events_repo_dep),
    source_intel=Depends(source_intelligence_service_dep),
    cycle_repo: IntelligenceCycleRepository = Depends(intelligence_cycle_repo_dep),
    correlation_repo: CorrelationRepository = Depends(correlation_repo_dep),
    health_repo: ProviderHealthRepository = Depends(provider_health_repo_dep),
    entitlement_svc=Depends(entitlement_service_dep),
    aoi=Depends(aoi_enrichment_service_dep),
):
    from app.services.customer_monitoring_status_service import (
        CustomerMonitoringStatusService,
    )

    return CustomerMonitoringStatusService(
        area_svc,
        intel_repo,
        source_intel,
        cycle_repo,
        correlation_repo,
        health_repo,
        entitlement_svc,
        aoi_enrichment=aoi,
    )


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


def demo_catalog_service_dep(db: AsyncIOMotorDatabase = Depends(db_dep)):
    from app.core.demo.constants import DEMO_INTEL_COLLECTION
    from app.modules.analytics.intelligence_events_repository import (
        IntelligenceEventsRepository,
    )
    from app.repositories.alert_policy_repository import AlertPolicyRepository
    from app.repositories.forest_monitoring_area_repository import (
        ForestMonitoringAreaRepository,
    )
    from app.repositories.organization_entitlement_repository import (
        OrganizationEntitlementRepository,
    )
    from app.repositories.organization_notification_channel_repository import (
        OrganizationNotificationChannelRepository,
    )
    from app.repositories.organization_repository import OrganizationRepository
    from app.services.demo.demo_catalog_service import DemoCatalogService

    return DemoCatalogService(
        org_repo=OrganizationRepository(db),
        area_repo=ForestMonitoringAreaRepository(db),
        entitlement_repo=OrganizationEntitlementRepository(db),
        intel_repo=IntelligenceEventsRepository(db, collection_name=DEMO_INTEL_COLLECTION),
        policy_repo=AlertPolicyRepository(db),
        channel_repo=OrganizationNotificationChannelRepository(db),
    )


def demo_session_service_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
    catalog=Depends(demo_catalog_service_dep),
):
    from app.repositories.demo_session_repository import DemoSessionRepository
    from app.services.demo.demo_session_service import DemoSessionService

    return DemoSessionService(DemoSessionRepository(db), catalog)


def demo_alert_simulation_service_dep(
    db: AsyncIOMotorDatabase = Depends(db_dep),
    sessions=Depends(demo_session_service_dep),
    catalog=Depends(demo_catalog_service_dep),
    policy_repo=Depends(alert_policy_repo_dep),
    channel_repo=Depends(organization_notification_channel_repo_dep),
    delivery_repo=Depends(alert_delivery_repo_dep),
):
    from app.core.demo.constants import DEMO_INTEL_COLLECTION
    from app.modules.analytics.intelligence_events_repository import (
        IntelligenceEventsRepository,
    )
    from app.services.demo.demo_alert_simulation_service import DemoAlertSimulationService

    return DemoAlertSimulationService(
        sessions=sessions,
        catalog=catalog,
        policy_repo=policy_repo,
        channel_repo=channel_repo,
        delivery_repo=delivery_repo,
        intel_repo=IntelligenceEventsRepository(db, collection_name=DEMO_INTEL_COLLECTION),
    )


async def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    auth_service: AuthService = Depends(auth_service_dep),
    demo_sessions=Depends(demo_session_service_dep),
) -> UserPublic | None:
    from app.core.demo.constants import DEMO_TOKEN_TYPE
    from app.core.security import decode_token

    token = request.cookies.get("access_token")
    if not token and credentials:
        token = credentials.credentials
    if not token:
        return None
    try:
        payload = decode_token(token)
    except Exception:
        return None
    if payload.get("type") == DEMO_TOKEN_TYPE:
        try:
            return await demo_sessions.public_user(str(payload.get("sub") or ""))
        except AuthError:
            return None
    if payload.get("type") != "access":
        return None
    try:
        return await auth_service.get_user_from_token(token)
    except AuthError:
        return None


async def get_current_user(
    user: UserPublic | None = Depends(get_optional_user),
) -> UserPublic:
    """Cookie session, Bearer token, or a signed demonstration session."""
    if user is None:
        raise AuthError("Not authenticated")
    return user


def deny_demo_global_data(
    user: UserPublic = Depends(get_current_user),
) -> UserPublic:
    """Block demonstration sessions from unscoped operational collections."""
    from app.core.demo.identity import deny_demo_user_unscoped

    deny_demo_user_unscoped(user)
    return user


def demo_payload_guard(request: Request) -> None:
    from app.core.demo.constants import DEMO_MAX_BODY_BYTES
    from app.core.errors import AppError

    raw = request.headers.get("content-length")
    if not raw:
        return
    try:
        size = int(raw)
    except ValueError:
        return
    if size > DEMO_MAX_BODY_BYTES:
        raise AppError(
            "Demonstration request is too large",
            status_code=413,
            code="demo_payload_too_large",
        )


def demo_session_id_dep(user: UserPublic = Depends(get_current_user)) -> str:
    from app.core.demo.identity import is_demo_user

    if not is_demo_user(user):
        from app.core.errors import ForbiddenError

        raise ForbiddenError("Demonstration session required")
    return str(user.id).removeprefix("demo:")


async def get_organization_context(
    request: Request,
    user: UserPublic = Depends(get_current_user),
    org_ctx_svc=Depends(organization_context_service_dep),
    trial_svc=Depends(trial_service_dep),
):
    from app.core.organization.organization_context import ORGANIZATION_ID_HEADER

    requested = request.headers.get(ORGANIZATION_ID_HEADER)
    ctx = await org_ctx_svc.resolve(user, requested_organization_id=requested)
    if not ctx.is_demo:
        await trial_svc.ensure_current_by_id(ctx.organization_id)
    return ctx
