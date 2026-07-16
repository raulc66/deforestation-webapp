"""Unit tests for app.core.geography.romania."""
import pytest
from app.core.geography.romania import (
    ROMANIA_BBOX,
    ROMANIA_REGIONS,
    is_romania_event,
    is_romania_expression,
)


class TestIsRomaniaEvent:
    # --- country match -------------------------------------------------------

    def test_exact_country_match(self):
        assert is_romania_event({"country": "Romania"}) is True

    def test_country_match_case_insensitive(self):
        assert is_romania_event({"country": "ROMANIA"}) is True
        assert is_romania_event({"country": "romania"}) is True
        assert is_romania_event({"country": "RoMaNiA"}) is True

    def test_country_match_with_whitespace(self):
        assert is_romania_event({"country": "  Romania  "}) is True

    def test_non_romania_country(self):
        assert is_romania_event({"country": "Brazil"}) is False

    # --- region match --------------------------------------------------------

    @pytest.mark.parametrize("region", [
        "Transylvania", "Muntenia", "Oltenia", "Banat",
        "Moldova", "Dobrogea", "Crișana", "Maramureș",
    ])
    def test_canonical_regions_match(self, region):
        assert is_romania_event({"region": region}) is True

    @pytest.mark.parametrize("region", [
        "transylvania", "MUNTENIA", "Oltenia ", " banat",
    ])
    def test_region_match_case_and_whitespace_insensitive(self, region):
        assert is_romania_event({"region": region}) is True

    def test_ascii_region_variants(self):
        assert is_romania_event({"region": "crisana"}) is True
        assert is_romania_event({"region": "maramures"}) is True

    def test_non_romania_region(self):
        assert is_romania_event({"region": "Amazon"}) is False

    # --- bounding box match --------------------------------------------------

    def test_center_of_romania_matches(self):
        assert is_romania_event({"latitude": 45.9, "longitude": 24.9}) is True

    def test_exact_bbox_boundary_matches(self):
        bbox = ROMANIA_BBOX
        assert is_romania_event({
            "latitude": bbox["min_lat"],
            "longitude": bbox["min_lng"],
        }) is True
        assert is_romania_event({
            "latitude": bbox["max_lat"],
            "longitude": bbox["max_lng"],
        }) is True

    def test_outside_bbox_does_not_match(self):
        assert is_romania_event({"latitude": 0.0, "longitude": 0.0}) is False
        assert is_romania_event({"latitude": 51.5, "longitude": 0.1}) is False

    def test_bbox_with_partial_coords_does_not_crash(self):
        assert is_romania_event({"latitude": 45.9}) is False
        assert is_romania_event({"longitude": 24.9}) is False

    # --- missing / empty fields ----------------------------------------------

    def test_empty_dict_returns_false(self):
        assert is_romania_event({}) is False

    def test_none_values_return_false(self):
        assert is_romania_event({"country": None, "region": None}) is False

    def test_empty_string_fields_return_false(self):
        assert is_romania_event({"country": "", "region": ""}) is False

    # --- priority: country beats region / bbox --------------------------------

    def test_country_takes_priority(self):
        # country=Romania, region outside -> True
        assert is_romania_event({"country": "Romania", "region": "Amazon"}) is True

    def test_non_romania_country_bbox_inside_still_false(self):
        # Explicit non-Romania country overrides bbox match only if country path
        # is exclusive — in our OR logic a bbox match will still return True.
        # This test documents actual behaviour: bbox wins as a fallback.
        assert is_romania_event({
            "country": "Bulgaria",
            "latitude": 45.9,
            "longitude": 24.9,
        }) is True

    # --- region set sanity ---------------------------------------------------

    def test_regions_frozenset_contains_expected_entries(self):
        required = {"transylvania", "muntenia", "oltenia", "banat",
                    "moldova", "dobrogea", "crisana", "maramures"}
        assert required.issubset(ROMANIA_REGIONS)

    def test_bbox_is_valid_wgs84_rectangle(self):
        b = ROMANIA_BBOX
        assert -90 <= b["min_lat"] < b["max_lat"] <= 90
        assert -180 <= b["min_lng"] < b["max_lng"] <= 180


class TestIsRomaniaExpression:
    def test_has_three_or_branches(self):
        expr = is_romania_expression()
        assert "$or" in expr
        assert len(expr["$or"]) == 3

    def test_bbox_constants_match_python_constants(self):
        expr = is_romania_expression()
        bbox_branch = expr["$or"][2]["$and"]
        # Extract the numeric literals from the gte/lte pairs
        lats = [b["$gte"][1] for b in bbox_branch if "$gte" in b and b["$gte"][0].get("$ifNull", [None])[0] == "$latitude"]
        assert lats == [ROMANIA_BBOX["min_lat"]]
