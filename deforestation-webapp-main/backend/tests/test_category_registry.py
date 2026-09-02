"""Category registry tests (Package D)."""
from __future__ import annotations

from app.core.ecosystem.category_registry import get_category_registry
from app.core.ecosystem.incident_categories import IncidentCategory


class TestCategoryRegistry:
    def test_singleton(self):
        assert get_category_registry() is get_category_registry()

    def test_lists_all_incident_categories(self):
        registry = get_category_registry()
        assert IncidentCategory.WILDFIRE.value in registry.categories()

    def test_wildfire_definition(self):
        definition = get_category_registry().get("wildfire")
        assert definition is not None
        assert definition.display_name == "Wildfire"
        assert definition.enabled is True
        assert definition.detector_compatible is True
        assert definition.ingestion_compatible is True

    def test_map_event_type_delegates_to_taxonomy(self):
        registry = get_category_registry()
        assert registry.map_event_type("logging") == IncidentCategory.ILLEGAL_LOGGING.value
