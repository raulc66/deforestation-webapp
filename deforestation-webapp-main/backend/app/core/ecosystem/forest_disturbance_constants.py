"""Forest disturbance intelligence vocabulary — drivers, assessment, product language."""
from __future__ import annotations

from enum import StrEnum


class DisturbanceDriver(StrEnum):
    SELECTIVE_LOGGING = "selective_logging"
    CLEARCUTTING = "clearcutting"
    ROAD_DEVELOPMENT = "road_development"
    AGRICULTURAL_CONVERSION = "agricultural_conversion"
    MINING = "mining"
    NATURAL_DISTURBANCE = "natural_disturbance"
    WILDFIRE = "wildfire"
    UNKNOWN = "unknown"


DISTURBANCE_DRIVERS: tuple[str, ...] = tuple(d.value for d in DisturbanceDriver)

# Probable-driver suffix used in metadata when certainty is inferred, not observed.
DRIVER_CANDIDATE_SUFFIX = "_candidate"


class AuthorizationStatus(StrEnum):
    AUTHORIZED = "authorized"
    POTENTIALLY_UNAUTHORIZED = "potentially_unauthorized"
    UNKNOWN = "unknown"
    REQUIRES_VERIFICATION = "requires_verification"


class InvestigationPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Mandatory product language — never assert illegality from satellite evidence alone.
PRODUCT_ASSESSMENT_LABEL = "Potential Unauthorized Forest Activity"
PRODUCT_VERIFICATION_LABEL = "Forest Disturbance Requiring Verification"

# Phrases that must never appear as automated conclusions without legal evidence.
FORBIDDEN_ASSERTION_PHRASES: frozenset[str] = frozenset(
    {
        "illegal logging detected",
        "illegal logging",
        "unauthorized logging confirmed",
        "confirmed illegal activity",
    }
)


def probable_driver_label(driver: str) -> str:
    """Human-readable probable driver — never implies legal certainty."""
    normalized = str(driver or DisturbanceDriver.UNKNOWN.value).strip().lower()
    if normalized.endswith(DRIVER_CANDIDATE_SUFFIX):
        normalized = normalized[: -len(DRIVER_CANDIDATE_SUFFIX)]
    mapping = {
        DisturbanceDriver.SELECTIVE_LOGGING.value: "Selective Logging",
        DisturbanceDriver.CLEARCUTTING.value: "Clear-cutting",
        DisturbanceDriver.ROAD_DEVELOPMENT.value: "Road / Skid-trail Development",
        DisturbanceDriver.AGRICULTURAL_CONVERSION.value: "Agricultural Conversion",
        DisturbanceDriver.MINING.value: "Mining-related Disturbance",
        DisturbanceDriver.NATURAL_DISTURBANCE.value: "Natural Disturbance",
        DisturbanceDriver.WILDFIRE.value: "Wildfire",
        DisturbanceDriver.UNKNOWN.value: "Unknown",
    }
    return mapping.get(normalized, normalized.replace("_", " ").title())


def assert_safe_assessment_language(text: str) -> None:
    lowered = str(text or "").strip().lower()
    for phrase in FORBIDDEN_ASSERTION_PHRASES:
        if phrase in lowered:
            raise ValueError(f"Unsafe assessment language: {phrase!r}")
