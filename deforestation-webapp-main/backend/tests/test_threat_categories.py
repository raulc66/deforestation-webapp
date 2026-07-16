"""Tests for ThreatCategory taxonomy and incident→threat mapping."""
from app.core.ecosystem.incident_categories import IncidentCategory
from app.core.ecosystem.threat_categories import ThreatCategory, threat_origin
from app.core.ecosystem.threat_mapping import (
    map_forest_event_to_threat,
    map_incident_to_threat,
    recommended_actions_for_threat,
)


class TestThreatCategory:
    def test_natural_wildfire_origin(self):
        assert threat_origin(ThreatCategory.WILDFIRE) == "natural"

    def test_human_illegal_logging_origin(self):
        assert threat_origin(ThreatCategory.ILLEGAL_LOGGING) == "human"

    def test_environmental_habitat_origin(self):
        assert threat_origin(ThreatCategory.HABITAT_FRAGMENTATION) == "environmental"


class TestIncidentToThreatMapping:
    def test_wildfire_incident_maps_to_wildfire_threat(self):
        assert map_incident_to_threat(IncidentCategory.WILDFIRE.value) == ThreatCategory.WILDFIRE

    def test_illegal_logging_maps(self):
        assert map_incident_to_threat(IncidentCategory.ILLEGAL_LOGGING.value) == ThreatCategory.ILLEGAL_LOGGING

    def test_habitat_disturbance_maps_to_fragmentation(self):
        assert map_incident_to_threat(IncidentCategory.HABITAT_DISTURBANCE.value) == (
            ThreatCategory.HABITAT_FRAGMENTATION
        )


class TestForestEventToThreatMapping:
    def test_mining_maps(self):
        assert map_forest_event_to_threat("mining") == ThreatCategory.MINING

    def test_agriculture_maps_to_expansion(self):
        assert map_forest_event_to_threat("agriculture") == ThreatCategory.AGRICULTURE_EXPANSION


class TestRecommendedActions:
    def test_wildfire_has_actions(self):
        actions = recommended_actions_for_threat(ThreatCategory.WILDFIRE)
        assert len(actions) >= 1
        assert any("monitor" in a.lower() or "fire" in a.lower() for a in actions)
