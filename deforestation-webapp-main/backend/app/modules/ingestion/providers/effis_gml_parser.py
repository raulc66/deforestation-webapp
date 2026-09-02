"""Parse EFFIS WFS 1.0.0 GML burned-area features (verified schema)."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

_GML_NS = {"gml": "http://www.opengis.net/gml", "ms": "http://mapserver.gis.umn.edu/mapserver"}
_COORD_PAIR_RE = re.compile(
    r"([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)"
)


def _local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _text(parent: ET.Element | None, name: str) -> str | None:
    if parent is None:
        return None
    for child in parent:
        if _local(child.tag) == name:
            text = (child.text or "").strip()
            return text or None
    return None


def _centroid_from_coordinates(text: str | None) -> tuple[float, float] | None:
    if not text:
        return None
    pairs = _COORD_PAIR_RE.findall(text)
    if not pairs:
        return None
    lons = [float(a) for a, _ in pairs]
    lats = [float(b) for _, b in pairs]
    return (sum(lats) / len(lats), sum(lons) / len(lons))


def _feature_centroid(feature: ET.Element) -> tuple[float, float] | None:
    for elem in feature.iter():
        if _local(elem.tag) == "coordinates" and elem.text:
            coords = _centroid_from_coordinates(elem.text)
            if coords is not None:
                return coords
    return None


def parse_effis_gml_features(xml_text: str, *, layer: str) -> list[dict[str, Any]]:
    """Return normalized raw feature dicts from an EFFIS WFS GetFeature response."""
    if not xml_text or "ServiceException" in xml_text[:2000]:
        raise ValueError("EFFIS WFS returned an error or empty payload")

    root = ET.fromstring(xml_text)
    records: list[dict[str, Any]] = []

    for member in root:
        if _local(member.tag) != "featureMember":
            continue
        for feature in member:
            fire_id = _text(feature, "id")
            if not fire_id:
                fid = feature.attrib.get("fid") or feature.attrib.get("{http://www.gml.org/gml}id")
                if fid and "." in fid:
                    fire_id = fid.rsplit(".", 1)[-1]
            coords = _feature_centroid(feature)
            if coords is None:
                continue
            lat, lng = coords
            country = _text(feature, "COUNTRY") or "Unknown"
            records.append(
                {
                    "id": str(fire_id or f"{lat:.4f}:{lng:.4f}"),
                    "fire_id": str(fire_id or f"{lat:.4f}:{lng:.4f}"),
                    "fire_date": _text(feature, "FIREDATE"),
                    "final_date": _text(feature, "FINALDATE"),
                    "last_update": _text(feature, "LASTUPDATE"),
                    "country": country,
                    "province": _text(feature, "PROVINCE"),
                    "commune": _text(feature, "COMMUNE"),
                    "area_ha": _text(feature, "AREA_HA"),
                    "latitude": lat,
                    "longitude": lng,
                    "layer": layer,
                }
            )
    return records
