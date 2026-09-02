"""Registry for scheduled ingestion providers."""
from __future__ import annotations

from app.core.config import Settings
from app.modules.ingestion.providers.firms import FIRMSProvider


def build_ingestion_providers(settings: Settings) -> list:
    """Compose scheduled observation ingestion providers from settings."""
    providers = [FIRMSProvider(api_key=settings.firms_api_key)]
    if settings.enable_eea_air_quality:
        from app.modules.ingestion.providers.eea_air_quality import EEAAirQualityProvider

        providers.append(EEAAirQualityProvider())
    if settings.enable_cems_rapid_mapping:
        from app.modules.ingestion.providers.cems_rapid_mapping import CEMSRapidMappingProvider

        providers.append(CEMSRapidMappingProvider())
    if settings.enable_effis_wildfire_context:
        from app.modules.ingestion.providers.effis import EFFISWildfireContextProvider

        providers.append(EFFISWildfireContextProvider(settings=settings))
    if settings.enable_forest_disturbance:
        from app.modules.ingestion.providers.gfw_integrated_alerts import (
            GFWIntegratedAlertsProvider,
        )

        providers.append(GFWIntegratedAlertsProvider(settings=settings))
    return providers
