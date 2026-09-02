"""WP1.1 — canonical identity contract tests."""
import pytest

from app.core.ecosystem.canonical_identity import (
    CanonicalIdentity,
    region_from_spatial_key,
    spatial_key_from_region,
)


class TestCanonicalIdentity:
    def test_from_region_constructs_identity(self):
        ident = CanonicalIdentity.from_region("Suceava")
        assert ident.incident_category == "wildfire"
        assert ident.spatial_key == "Suceava"

    def test_as_key_tuple(self):
        ident = CanonicalIdentity(incident_category="wildfire", spatial_key="Cluj")
        assert ident.as_key_tuple() == ("wildfire", "Cluj")

    def test_rejects_empty_spatial_key(self):
        with pytest.raises(ValueError):
            CanonicalIdentity(incident_category="wildfire", spatial_key="  ")

    def test_normalizes_incident_category(self):
        ident = CanonicalIdentity(incident_category="WILDFIRE", spatial_key="A")
        assert ident.incident_category == "wildfire"

    def test_region_spatial_key_round_trip(self):
        assert region_from_spatial_key(spatial_key_from_region("Bacău")) == "Bacău"
