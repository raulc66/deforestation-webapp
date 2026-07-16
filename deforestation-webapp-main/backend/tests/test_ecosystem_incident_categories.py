"""Tests for ecosystem incident category taxonomy."""
from app.core.ecosystem.incident_categories import (
    INCIDENT_CATEGORIES,
    IncidentCategory,
    map_forest_event_type_to_incident,
    normalize_incident_category,
    resolve_incident_category,
)


class TestIncidentCategoryEnum:
    def test_all_categories_present(self):
        assert "wildfire" in INCIDENT_CATEGORIES
        assert "illegal_logging" in INCIDENT_CATEGORIES
        assert "unknown" in INCIDENT_CATEGORIES
        assert len(INCIDENT_CATEGORIES) == len(IncidentCategory)


class TestNormalizeIncidentCategory:
    def test_none_defaults_to_wildfire(self):
        assert normalize_incident_category(None) == "wildfire"

    def test_empty_defaults_to_wildfire(self):
        assert normalize_incident_category("") == "wildfire"

    def test_valid_category_passthrough(self):
        assert normalize_incident_category("illegal_logging") == "illegal_logging"

    def test_unknown_value_maps_to_unknown(self):
        assert normalize_incident_category("not_a_category") == "unknown"


class TestMapForestEventType:
    def test_wildfire_maps(self):
        assert map_forest_event_type_to_incident("wildfire") == "wildfire"

    def test_logging_maps_to_illegal_logging(self):
        assert map_forest_event_type_to_incident("logging") == "illegal_logging"

    def test_unmapped_returns_unknown(self):
        assert map_forest_event_type_to_incident("nonexistent") == "unknown"


class TestResolveIncidentCategory:
    def test_anomaly_defaults_to_wildfire(self):
        assert resolve_incident_category({"event_type": "anomaly"}) == "wildfire"

    def test_explicit_category_wins(self):
        assert resolve_incident_category({"incident_category": "tree_theft"}) == "tree_theft"

    def test_forest_event_type_mapping(self):
        assert resolve_incident_category({"forest_event_type": "logging"}) == "illegal_logging"

    def test_none_source_defaults_wildfire(self):
        assert resolve_incident_category(None) == "wildfire"
