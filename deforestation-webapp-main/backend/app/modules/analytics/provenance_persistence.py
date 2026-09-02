"""Sanitized provenance persistence for IntelligenceEvent metadata."""
from __future__ import annotations

from datetime import datetime
from typing import Any

_ALLOWED_TOP_LEVEL = frozenset(
    {
        "source_id",
        "provider_id",
        "dataset_id",
        "dataset_version",
        "source_event_id",
        "observed_at",
        "ingested_at",
        "detected_at",
        "geographic_scope",
        "domain_evidence",
    }
)

_FORBIDDEN_DOMAIN_KEYS = frozenset(
    {
        "api_key",
        "token",
        "password",
        "secret",
        "raw_payload",
        "raw_response",
        "credentials",
    }
)

_ALLOWED_DOMAIN_KEYS = frozenset(
    {
        "station_id",
        "pollutant",
        "unit",
        "value",
        "hazard_type",
        "activation_code",
        "country",
        "provider_class",
        "detection_method",
        "contributing_sources",
    }
)


def sanitize_provenance_envelope(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    """Strip credentials and unbounded payloads from a provenance envelope."""
    if not raw:
        return None

    cleaned: dict[str, Any] = {}
    for key in _ALLOWED_TOP_LEVEL:
        if key not in raw or raw[key] is None:
            continue
        if key == "domain_evidence":
            domain = raw.get("domain_evidence") or {}
            if not isinstance(domain, dict):
                continue
            safe_domain: dict[str, Any] = {}
            for dk, dv in domain.items():
                if dk in _FORBIDDEN_DOMAIN_KEYS:
                    continue
                if dk in _ALLOWED_DOMAIN_KEYS:
                    safe_domain[dk] = dv
            if safe_domain:
                cleaned["domain_evidence"] = safe_domain
        else:
            cleaned[key] = raw[key]

    return cleaned or None


def provenance_from_detection_evidence(
    evidence: dict[str, Any],
    *,
    geographic_scope: str | None = None,
    detected_at: datetime | None = None,
) -> dict[str, Any] | None:
    """Build persistable provenance block from Detection evidence."""
    raw = evidence.get("provenance")
    if not isinstance(raw, dict):
        return None

    envelope = dict(raw)
    if geographic_scope:
        envelope["geographic_scope"] = geographic_scope
    if detected_at is not None:
        domain = dict(envelope.get("domain_evidence") or {})
        domain.setdefault("detected_at", detected_at.isoformat())
        envelope["domain_evidence"] = domain
        envelope["detected_at"] = detected_at.isoformat()

    return sanitize_provenance_envelope(envelope)
