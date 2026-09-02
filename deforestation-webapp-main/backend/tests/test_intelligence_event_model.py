"""WP1.2 / WP1.4 — intelligence event model and legacy defaults."""
from datetime import datetime, timezone

from app.core.ecosystem.intelligence_event_defaults import apply_legacy_intelligence_event_defaults
from app.models.intelligence_event import (
    IntelligenceEvent,
    default_derived_event_type,
    default_signal_type,
    intelligence_event_field_mapping,
)


_NOW = datetime(2026, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


class TestIntelligenceEventModel:
    def test_field_mapping_documents_identity_vs_dynamics(self):
        mapping = intelligence_event_field_mapping()
        assert "identity component" in mapping["incident_category"]
        assert "derived label" in mapping["event_type"]
        assert "mutable dynamics" in mapping["severity"]

    def test_from_persisted_applies_legacy_defaults(self):
        event = IntelligenceEvent.from_persisted(
            {
                "id": "evt-1",
                "region": "Suceava",
                "status": "active",
                "severity": "high",
                "first_detected_at": _NOW,
                "last_detected_at": _NOW,
                "detection_count": 1,
                "current_score": 0.64,
                "metadata": {},
            }
        )
        assert event.incident_category == "wildfire"
        assert event.spatial_key == "Suceava"
        assert event.signal_type == default_signal_type()
        assert event.event_type == default_derived_event_type()

    def test_apply_legacy_defaults_without_incident_category(self):
        out = apply_legacy_intelligence_event_defaults({"region": "Cluj"})
        assert out["incident_category"] == "wildfire"
        assert out["spatial_key"] == "Cluj"
        assert out["signal_type"] == "baseline_deviation"
        assert out["event_type"] == "anomaly"
