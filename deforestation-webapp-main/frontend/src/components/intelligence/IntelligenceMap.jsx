/**
 * IntelligenceMap — Romania-focused geospatial intelligence layer.
 *
 * Three independently-toggleable marker layers:
 *   1. Forest Events    — CircleMarkers colored by severity (from /api/events/map)
 *   2. Anomalies        — CircleMarkers sized by anomaly_score (from /api/analytics/intelligence/anomalies)
 *   3. Intelligence     — CircleMarkers colored by priority_score (from /api/analytics/intelligence/events)
 *
 * All marker layers are rendered imperatively via leaflet.markercluster so
 * clusters form automatically without re-rendering the React tree.  The three
 * sub-components (ForestEventsLayer, AnomaliesLayer, IntelligenceEventsLayer)
 * must live inside <MapContainer> because they call useMap().
 *
 * A floating summary panel is positioned absolute over the map wrapper and
 * shows live counts from /api/analytics/intelligence/events/summary.
 */
import { useState, useEffect, useCallback, useMemo } from "react";
import { MapContainer, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";
import { Map as MapIcon } from "lucide-react";
import {
  fetchMapEvents,
  fetchAnomalies,
  fetchIntelligenceEvents,
  fetchIntelligenceSummary,
  fetchRegionalRisk,
  fetchWeather,
  fetchThreats,
} from "@/api/analytics";
import { formatApiErrorDetail } from "@/lib/api";

// ---------------------------------------------------------------------------
// Map constants
// ---------------------------------------------------------------------------

const ROMANIA_CENTER = [45.9432, 24.9668];
const DEFAULT_ZOOM = 7;

// ---------------------------------------------------------------------------
// Colour maps
// ---------------------------------------------------------------------------

const SEVERITY_COLORS = {
  low: "#e9c46a",
  medium: "#f4a261",
  high: "#e76f51",
  critical: "#9b2226",
};

/** Land-cover type → marker border color. */
const LAND_COVER_BORDER_COLORS = {
  forest:      "#1b4332",  // dark green
  near_forest: "#52b788",  // light green
  agriculture: "#ffd166",  // yellow
  urban:       "#ef476f",  // red
  water:       "#118ab2",  // blue
  unknown:     "#9ca3af",  // gray
};

/** Land-cover type → forest confidence weight (for popup display). */
const LAND_COVER_CONFIDENCE = {
  forest:      1.00,
  near_forest: 0.75,
  agriculture: 0.40,
  urban:       0.20,
  water:       0.10,
  unknown:     0.50,
};

/** Risk level → colored glow color for the risk overlay layer. */
const RISK_LEVEL_GLOW_COLORS = {
  Extreme: "#ef4444",  // red
  High:    "#f97316",  // orange
  Moderate: "#eab308", // yellow
  Low:     "#22c55e",  // green
};

/**
 * Temperature → marker fill color for the weather overlay.
 * Range: cold (blue) → warm (orange) → hot (red).
 */
function weatherTempColor(temp) {
  if (temp < 0)  return "#3b82f6";  // blue
  if (temp < 10) return "#60a5fa";  // light blue
  if (temp < 20) return "#a3e635";  // lime
  if (temp < 30) return "#fb923c";  // orange
  if (temp < 40) return "#ef4444";  // red
  return "#991b1b";                 // dark red
}

/** Degrees → compact compass abbreviation. */
function _windCompass(deg) {
  const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  return dirs[Math.round((deg ?? 0) / 45) % 8] ?? "—";
}

/** Source label shown in land-cover popup rows. Matches the active GIS dataset. */
const LAND_COVER_SOURCE_LABEL = "Copernicus";

/** Priority score → accent colour for intelligence event markers. */
function priorityColor(score) {
  if (score >= 0.7) return "#9b2226";
  if (score >= 0.4) return "#e76f51";
  return "#3b82f6";
}

// ---------------------------------------------------------------------------
// Romania region → [lat, lng] lookup
// Used for anomaly and intelligence-event layers (no coordinates in API response).
// ---------------------------------------------------------------------------

const ROMANIA_REGION_COORDS = {
  Suceava: [47.6353, 26.259],
  Bacău: [46.567, 26.9146],
  Harghita: [46.3548, 25.7979],
  Cluj: [46.7712, 23.6236],
  Brașov: [45.6427, 25.5887],
  Prahova: [45.0527, 25.7982],
  Argeș: [44.8563, 24.8698],
  Mureș: [46.538, 24.5547],
  Alba: [46.0737, 23.58],
  Sibiu: [45.7983, 24.1256],
  Covasna: [45.8523, 26.185],
  Neamț: [46.9756, 26.3819],
  Vrancea: [45.7019, 27.1851],
  Buzău: [45.1492, 26.8255],
  Dâmbovița: [44.934, 25.46],
  Gorj: [44.9, 23.28],
  Vâlcea: [45.0997, 24.3692],
  Hunedoara: [45.7489, 22.9106],
  "Caraș-Severin": [45.2971, 21.8964],
  Maramureș: [47.6594, 23.5696],
  "Bistrița-Năsăud": [47.1342, 24.4961],
  Sălaj: [47.19, 23.05],
  Bihor: [47.0722, 22.4306],
  "Satu Mare": [47.793, 22.8859],
  Arad: [46.1659, 21.3153],
  Timiș: [45.7489, 21.2087],
  Mehedinți: [44.6316, 22.6567],
  Dolj: [44.3179, 23.7956],
  Olt: [44.4286, 24.3716],
  Teleorman: [43.9833, 25.0083],
  Giurgiu: [43.905, 25.9697],
  Ilfov: [44.4833, 26.1333],
  Bucharest: [44.4268, 26.1025],
  Călărași: [44.205, 27.3317],
  Ialomița: [44.5761, 27.3608],
  Iași: [47.1585, 27.6014],
  Vaslui: [46.6407, 27.7296],
  Galați: [45.4353, 28.0476],
  Brăila: [45.2692, 27.9575],
  Constanța: [44.1598, 28.6348],
  Tulcea: [45.1786, 28.8028],
  Botoșani: [47.7458, 26.665],
  "Carpathian Forest": [45.9432, 24.9668],
};

function regionCoords(region) {
  return ROMANIA_REGION_COORDS[region] ?? ROMANIA_CENTER;
}

// ---------------------------------------------------------------------------
// Popup HTML builders (inline style only — Tailwind not available in Leaflet DOM)
// ---------------------------------------------------------------------------

const _popupWrap = (accentColor, badge, regionName, rows) => `
  <div style="font-family:system-ui,sans-serif;min-width:170px;max-width:220px">
    <div style="font-size:10px;text-transform:uppercase;letter-spacing:.15em;color:${accentColor};font-weight:700;margin-bottom:2px">${badge}</div>
    <div style="font-weight:700;font-size:14px;line-height:1.3;margin-bottom:8px;color:#1a1e1a">${regionName}</div>
    <table style="font-size:11px;width:100%;border-collapse:collapse;color:#4a524a">
      ${rows.map(([k, v]) => `<tr><td style="color:#7b827b;padding-right:10px;padding-bottom:2px">${k}</td><td style="font-weight:600;color:#1a1e1a">${v}</td></tr>`).join("")}
    </table>
  </div>`;

function forestEventPopup(evt) {
  const color = SEVERITY_COLORS[evt.severity] ?? "#7b827b";
  const lcType = evt.land_cover_type ?? "unknown";
  const lcConf = LAND_COVER_CONFIDENCE[lcType] ?? 0.50;
  const lcLabel = lcType.replace(/_/g, " ");
  const date = evt.detected_at
    ? new Date(evt.detected_at).toLocaleDateString()
    : "—";
  return _popupWrap(color, evt.severity ?? "—", evt.region ?? "Unknown", [
    ["Source", evt.source ?? "—"],
    ["Land Cover", lcLabel],
    ["Land Cover Source", LAND_COVER_SOURCE_LABEL],
    ["Forest Conf.", lcConf.toFixed(2)],
    ["Detected", date],
  ]);
}

function anomalyPopup(a) {
  const dev =
    typeof a.deviation_percent === "number"
      ? `${a.deviation_percent.toFixed(0)} %`
      : "—";
  const score =
    typeof a.anomaly_score === "number"
      ? a.anomaly_score.toFixed(3)
      : "—";
  const forestConf =
    typeof a.forest_confidence === "number"
      ? a.forest_confidence.toFixed(2)
      : "—";
  return _popupWrap("#e76f51", "Anomaly", a.region ?? "Unknown", [
    ["Current events", a.current_count ?? "—"],
    ["Baseline avg", typeof a.baseline_avg === "number" ? a.baseline_avg.toFixed(1) : "—"],
    ["Deviation", dev],
    ["Severity", a.severity ?? "—"],
    ["Score", score],
    ["Forest Conf.", forestConf],
  ]);
}

function _formatThreatLabel(category) {
  if (!category) return "—";
  return String(category).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function intelligencePopup(evt, threat) {
  const score =
    typeof evt.priority_score === "number"
      ? evt.priority_score.toFixed(4)
      : "—";
  const color = priorityColor(evt.priority_score ?? 0);
  const rows = [
    ["Severity", evt.severity ?? "—"],
    ["Escalation", evt.escalation_level ?? "—"],
    ["Trend", evt.trend ?? "—"],
    ["Priority", score],
    ["Detections", evt.detection_count ?? "—"],
  ];
  if (threat) {
    rows.push(
      ["Threat", _formatThreatLabel(threat.threat_category)],
      ["Threat origin", threat.origin ?? "—"],
      ["Monitoring", threat.monitoring_priority ?? "—"],
      [
        "Intervention",
        threat.recommended_actions?.[0] ?? threat.intervention_priority ?? "—",
      ]
    );
  }
  return _popupWrap(color, "Intelligence", evt.region ?? "Unknown", rows);
}

// ---------------------------------------------------------------------------
// Layer sub-components — must be rendered inside <MapContainer>
// ---------------------------------------------------------------------------

/**
 * ForestEventsLayer
 * Renders forest event CircleMarkers clustered by leaflet.markercluster.
 * Fill color: severity. Border color: land cover type.
 * Filtered client-side by the landCoverFilter prop (no extra API requests).
 */
function ForestEventsLayer({ events, visible, landCoverFilter }) {
  const map = useMap();

  useEffect(() => {
    if (!visible || !events.length) return;

    // Active land-cover types (those checked in the filter panel).
    const activeTypes = Object.keys(landCoverFilter).filter(
      (k) => landCoverFilter[k]
    );
    const filtered =
      activeTypes.length > 0
        ? events.filter((evt) =>
            activeTypes.includes(evt.land_cover_type ?? "unknown")
          )
        : events;

    if (!filtered.length) return;

    const cluster = L.markerClusterGroup({ chunkedLoading: true });
    filtered.forEach((evt) => {
      if (typeof evt.latitude !== "number" || typeof evt.longitude !== "number")
        return;
      const fillColor = SEVERITY_COLORS[evt.severity] ?? "#7b827b";
      const borderColor =
        LAND_COVER_BORDER_COLORS[evt.land_cover_type ?? "unknown"] ?? "#9ca3af";
      const m = L.circleMarker([evt.latitude, evt.longitude], {
        color: borderColor,       // border reflects land cover
        fillColor,                // fill reflects severity
        fillOpacity: 0.65,
        radius: 7,
        weight: 2.5,
      });
      m.bindPopup(forestEventPopup(evt));
      cluster.addLayer(m);
    });
    map.addLayer(cluster);

    return () => {
      map.removeLayer(cluster);
    };
  }, [map, events, visible, landCoverFilter]);

  return null;
}

/**
 * AnomaliesLayer
 * Renders anomaly CircleMarkers whose radius scales with anomaly_score.
 * Coordinates are resolved from the ROMANIA_REGION_COORDS lookup.
 */
function AnomaliesLayer({ anomalies, visible }) {
  const map = useMap();

  useEffect(() => {
    if (!visible || !anomalies.length) return;

    const cluster = L.markerClusterGroup({ chunkedLoading: true });
    anomalies.forEach((a) => {
      const coords = regionCoords(a.region);
      const score = a.anomaly_score ?? 0;
      const radius = 8 + score * 14;
      const color = SEVERITY_COLORS[a.severity] ?? "#f4a261";
      const m = L.circleMarker(coords, {
        color,
        fillColor: color,
        fillOpacity: 0.45,
        radius,
        weight: 2,
        dashArray: "5 3",
      });
      m.bindPopup(anomalyPopup(a));
      cluster.addLayer(m);
    });
    map.addLayer(cluster);

    return () => {
      map.removeLayer(cluster);
    };
  }, [map, anomalies, visible]);

  return null;
}

/**
 * IntelligenceEventsLayer
 * Renders active intelligence event CircleMarkers colored by priority_score.
 * Coordinates are resolved from the ROMANIA_REGION_COORDS lookup.
 */
function IntelligenceEventsLayer({ events, visible, threatByEventId }) {
  const map = useMap();

  useEffect(() => {
    if (!visible || !events.length) return;

    const cluster = L.markerClusterGroup({ chunkedLoading: true });
    events.forEach((evt) => {
      const coords = regionCoords(evt.region);
      const color = priorityColor(evt.priority_score ?? 0);
      const threat = threatByEventId?.[evt.id] ?? threatByEventId?.[evt.region];
      const m = L.circleMarker(coords, {
        color,
        fillColor: color,
        fillOpacity: 0.7,
        radius: 10,
        weight: 2,
      });
      m.bindPopup(intelligencePopup(evt, threat));
      cluster.addLayer(m);
    });
    map.addLayer(cluster);

    return () => {
      map.removeLayer(cluster);
    };
  }, [map, events, visible, threatByEventId]);

  return null;
}

// ---------------------------------------------------------------------------
// Floating summary overlay (rendered outside MapContainer)
// ---------------------------------------------------------------------------

function SummaryOverlay({ summary }) {
  if (!summary) return null;

  return (
    <div
      className="absolute bottom-4 left-4 z-[400] glass rounded-lg px-4 py-3 shadow-sm min-w-[190px]"
      data-testid="map-summary-overlay"
    >
      <div className="label-eyebrow mb-2">Intelligence summary</div>
      <dl className="space-y-1.5">
        <div className="flex justify-between items-baseline gap-4">
          <dt className="text-xs text-[#7b827b]">Active</dt>
          <dd
            className="text-sm font-bold tabular-nums text-[#e76f51]"
            data-testid="summary-active"
          >
            {summary.active ?? 0}
          </dd>
        </div>
        <div className="flex justify-between items-baseline gap-4">
          <dt className="text-xs text-[#7b827b]">Critical</dt>
          <dd
            className="text-sm font-bold tabular-nums text-[#9b2226]"
            data-testid="summary-critical"
          >
            {summary.critical ?? 0}
          </dd>
        </div>
        <div className="flex justify-between items-baseline gap-4">
          <dt className="text-xs text-[#7b827b]">Persistent</dt>
          <dd
            className="text-sm font-bold tabular-nums text-[#c84b31]"
            data-testid="summary-persistent"
          >
            {summary.persistent ?? 0}
          </dd>
        </div>
        {summary.highest_priority_region && (
          <div
            className="mt-2 pt-2 border-t border-[#eaece6]"
            data-testid="summary-top-region"
          >
            <div className="text-[10px] text-[#7b827b] uppercase tracking-wider">
              Top signal
            </div>
            <div className="text-xs font-semibold mt-0.5 truncate text-[#1a1e1a]">
              {summary.highest_priority_region}
            </div>
            <div
              className="text-[10px] font-mono text-[#9b2226]"
              data-testid="summary-top-score"
            >
              {summary.highest_priority_score?.toFixed(4) ?? "—"}
            </div>
          </div>
        )}
      </dl>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Risk Overlay Layer — additive colored glow per region
// ---------------------------------------------------------------------------

/**
 * Renders semi-transparent ring markers for each region whose risk data is
 * available in ROMANIA_REGION_COORDS.  The glow is additive: existing severity
 * and land-cover styling on other layers is unaffected.
 *
 * Colors:
 *   Extreme → red (#ef4444)
 *   High    → orange (#f97316)
 *   Moderate → yellow (#eab308)
 *   Low     → green (#22c55e)
 */
function RiskOverlayLayer({ riskRegions, visible }) {
  const map = useMap();

  useEffect(() => {
    if (!visible || !riskRegions || riskRegions.length === 0) return;

    const markers = [];
    riskRegions.forEach((r) => {
      const coords = regionCoords(r.region);
      if (!coords) return;
      const color = RISK_LEVEL_GLOW_COLORS[r.risk_level] || "#22c55e";
      const radius = 18 + r.risk_score * 22; // 18–40 px, proportional to score
      const marker = L.circleMarker(coords, {
        radius,
        color,
        weight: 3,
        opacity: 0.85,
        fillColor: color,
        fillOpacity: 0.10,
        interactive: true,
        className: "risk-overlay-marker",
      });
      marker.bindPopup(
        `<div style="min-width:160px">
          <strong>${r.region}</strong><br/>
          <span style="color:${color}">●</span>
          Risk: <strong>${r.risk_level}</strong>
          (${(r.risk_score * 100).toFixed(1)}%)
        </div>`
      );
      marker.addTo(map);
      markers.push(marker);
    });

    return () => {
      markers.forEach((m) => map.removeLayer(m));
    };
  }, [map, riskRegions, visible]);

  return null;
}

// ---------------------------------------------------------------------------
// Weather Overlay Layer — temperature-colored circles + wind arrows
// ---------------------------------------------------------------------------

/**
 * Renders two marker types when the weather overlay is active:
 *   1. Filled CircleMarker colored by temperature (cold=blue → hot=red).
 *   2. DivIcon wind-direction arrow (rotated Unicode ↑) offset slightly.
 *
 * Both operate independently from the risk overlay — toggling one has no
 * effect on the other.
 */
function WeatherOverlayLayer({ weatherRegions, visible }) {
  const map = useMap();

  useEffect(() => {
    if (!visible || !weatherRegions || weatherRegions.length === 0) return;

    const markers = [];

    weatherRegions.forEach((r) => {
      const coords = regionCoords(r.region);
      if (!coords) return;

      const color = weatherTempColor(r.temperature ?? 15);

      // Temperature-colored filled circle
      const tempMarker = L.circleMarker(coords, {
        radius: 14,
        color: color,
        weight: 2,
        opacity: 0.9,
        fillColor: color,
        fillOpacity: 0.35,
        interactive: true,
        className: "weather-temp-marker",
      });

      const windDir = r.wind_direction ?? 0;
      const compass = _windCompass(windDir);
      const updatedAt = r.updated_at
        ? new Date(r.updated_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
        : "—";

      tempMarker.bindPopup(
        `<div style="min-width:160px;font-family:system-ui,sans-serif">
          <strong style="font-size:14px">${r.region}</strong><br/>
          <table style="font-size:11px;margin-top:6px;width:100%;border-collapse:collapse;color:#4a524a">
            <tr><td style="color:#7b827b;padding-right:8px">Temp</td>
                <td style="color:${color};font-weight:700">${(r.temperature ?? 0).toFixed(1)} °C</td></tr>
            <tr><td style="color:#7b827b;padding-right:8px">Humidity</td>
                <td style="font-weight:600">${(r.humidity ?? 0).toFixed(0)} %</td></tr>
            <tr><td style="color:#7b827b;padding-right:8px">Wind</td>
                <td style="font-weight:600">${(r.wind_speed ?? 0).toFixed(1)} km/h ${compass}</td></tr>
            <tr><td style="color:#7b827b;padding-right:8px">Precip</td>
                <td style="font-weight:600">${(r.precipitation ?? 0).toFixed(1)} mm</td></tr>
            <tr><td style="color:#7b827b;padding-right:8px">Updated</td>
                <td style="font-weight:600">${updatedAt}</td></tr>
          </table>
        </div>`
      );
      tempMarker.addTo(map);
      markers.push(tempMarker);

      // Wind direction arrow — DivIcon offset by 22px to avoid overlapping the circle
      if (r.wind_speed > 0) {
        const arrowIcon = L.divIcon({
          html: `<div style="
            transform: rotate(${windDir}deg);
            font-size: 16px;
            line-height: 1;
            color: #3b82f6;
            text-shadow: 0 0 3px white;
            display:flex;align-items:center;justify-content:center;
          " title="${(r.wind_speed ?? 0).toFixed(1)} km/h ${compass}">↑</div>`,
          iconSize: [20, 20],
          iconAnchor: [10, 10],
          className: "weather-wind-arrow",
        });

        const arrowMarker = L.marker(
          [coords[0], coords[1] + 0.18],
          { icon: arrowIcon, interactive: false }
        );
        arrowMarker.addTo(map);
        markers.push(arrowMarker);
      }
    });

    return () => {
      markers.forEach((m) => map.removeLayer(m));
    };
  }, [map, weatherRegions, visible]);

  return null;
}

// ---------------------------------------------------------------------------
// Layer toggles
// ---------------------------------------------------------------------------

const LAYER_DEFS = [
  { key: "events",          label: "Forest Events",       color: "#e76f51" },
  { key: "anomalies",       label: "Anomalies",            color: "#f4a261" },
  { key: "intelligence",    label: "Intelligence Events",  color: "#9b2226" },
  { key: "risk_overlay",    label: "Risk Overlay",         color: "#ef4444" },
  { key: "weather_overlay", label: "Weather Overlay",      color: "#3b82f6" },
];

function LayerControls({ layers, onToggle }) {
  return (
    <div className="flex flex-wrap gap-4 mb-2" data-testid="map-layer-controls">
      {LAYER_DEFS.map(({ key, label, color }) => (
        <label
          key={key}
          className="inline-flex items-center gap-2 text-sm cursor-pointer select-none"
          data-testid={`layer-toggle-${key}`}
        >
          <input
            type="checkbox"
            checked={layers[key]}
            onChange={() => onToggle(key)}
            className="accent-[#2d5a27] w-3.5 h-3.5"
            aria-label={`Toggle ${label} layer`}
          />
          <span
            className="w-2.5 h-2.5 rounded-full shrink-0"
            style={{ background: color }}
            aria-hidden="true"
          />
          <span className="text-[#1a1e1a] font-medium">{label}</span>
        </label>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Land cover filter panel
// ---------------------------------------------------------------------------

const LAND_COVER_FILTER_DEFS = [
  { key: "forest",      label: "Forest",      color: "#1b4332" },
  { key: "near_forest", label: "Near Forest",  color: "#52b788" },
  { key: "agriculture", label: "Agriculture",  color: "#ffd166" },
  { key: "urban",       label: "Urban",        color: "#ef476f" },
  { key: "water",       label: "Water",        color: "#118ab2" },
  { key: "unknown",     label: "Unknown",      color: "#9ca3af" },
];

function LandCoverFilter({ filter, onToggle }) {
  return (
    <div
      className="flex flex-wrap items-center gap-3 mb-3 text-xs"
      data-testid="land-cover-filter"
    >
      <span className="font-semibold text-[#7b827b] shrink-0">Land cover:</span>
      {LAND_COVER_FILTER_DEFS.map(({ key, label, color }) => (
        <label
          key={key}
          className="inline-flex items-center gap-1.5 cursor-pointer select-none"
          data-testid={`lc-toggle-${key}`}
        >
          <input
            type="checkbox"
            checked={filter[key]}
            onChange={() => onToggle(key)}
            className="accent-[#2d5a27] w-3 h-3"
            aria-label={`Toggle ${label} land cover`}
          />
          <span
            className="w-2 h-2 rounded-full shrink-0"
            style={{ background: color }}
            aria-hidden="true"
          />
          <span className="text-[#1a1e1a]">{label}</span>
        </label>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Time range filter
// ---------------------------------------------------------------------------

const TIME_RANGE_OPTIONS = [
  { value: 7,    label: "7 days" },
  { value: 30,   label: "30 days" },
  { value: 90,   label: "90 days" },
  { value: null, label: "All" },
];

function TimeRangeFilter({ value, onChange }) {
  return (
    <div
      className="flex flex-wrap items-center gap-2 mb-3 text-xs"
      data-testid="time-range-filter"
    >
      <span className="font-semibold text-[#7b827b] shrink-0">Time range:</span>
      {TIME_RANGE_OPTIONS.map((opt) => (
        <button
          key={String(opt.value)}
          type="button"
          onClick={() => onChange(opt.value)}
          className={`px-2.5 py-1 rounded font-medium transition-colors ${
            value === opt.value
              ? "bg-[#2d5a27] text-white"
              : "bg-[#f4f5f2] text-[#4a524a] hover:bg-[#eaece6]"
          }`}
          data-testid={`time-range-btn-${opt.value ?? "all"}`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

export default function IntelligenceMap() {
  const [mapEvents, setMapEvents] = useState([]);
  const [anomalies, setAnomalies] = useState([]);
  const [intelEvents, setIntelEvents] = useState(null);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [layers, setLayers] = useState({
    events: true,
    anomalies: true,
    intelligence: true,
    risk_overlay: false,
    weather_overlay: false,
  });
  const [riskData, setRiskData] = useState(null);
  const [weatherData, setWeatherData] = useState(null);
  const [threatByEventId, setThreatByEventId] = useState({});
  const [landCoverFilter, setLandCoverFilter] = useState({
    forest: true,
    near_forest: true,
    agriculture: true,
    urban: true,
    water: true,
    unknown: true,
  });
  const [timeRangeDays, setTimeRangeDays] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const [eventsData, anomaliesData, intelData, summaryData, threatsData] =
          await Promise.all([
            fetchMapEvents(),
            fetchAnomalies(),
            fetchIntelligenceEvents(),
            fetchIntelligenceSummary(),
            fetchThreats(),
          ]);
        if (!alive) return;
        setMapEvents(eventsData?.events ?? []);
        setAnomalies(anomaliesData?.anomalies ?? []);
        setIntelEvents(intelData);
        setSummary(summaryData);
        const lookup = {};
        for (const t of threatsData?.threats ?? []) {
          if (t.source_event_id) lookup[t.source_event_id] = t;
          if (t.region) lookup[t.region] = t;
        }
        setThreatByEventId(lookup);
      } catch (err) {
        if (!alive) return;
        const detail = err?.response?.data?.detail;
        setError(
          formatApiErrorDetail(detail) ||
            err.message ||
            "Failed to load map data."
        );
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const toggleLayer = useCallback(
    (key) => {
      setLayers((prev) => {
        const next = { ...prev, [key]: !prev[key] };
        // Lazy-load risk data the first time the risk overlay is enabled.
        if (key === "risk_overlay" && next.risk_overlay && !riskData) {
          fetchRegionalRisk()
            .then((d) => setRiskData(d))
            .catch(() => {/* silent – overlay stays empty */});
        }
        // Lazy-load weather data the first time the weather overlay is enabled.
        if (key === "weather_overlay" && next.weather_overlay && !weatherData) {
          fetchWeather()
            .then((d) => setWeatherData(d))
            .catch(() => {/* silent – overlay stays empty */});
        }
        return next;
      });
    },
    [riskData, weatherData]
  );

  const toggleLandCover = useCallback((key) => {
    setLandCoverFilter((prev) => ({ ...prev, [key]: !prev[key] }));
  }, []);

  // Client-side time-range filter applied to the forest events layer.
  // Anomalies and intelligence events are summary data without individual
  // event timestamps, so they are not filtered by time range.
  const filteredMapEvents = useMemo(() => {
    if (!timeRangeDays) return mapEvents;
    const cutoff = new Date(Date.now() - timeRangeDays * 24 * 60 * 60 * 1000);
    return mapEvents.filter((evt) => {
      if (!evt.detected_at) return true;
      return new Date(evt.detected_at) >= cutoff;
    });
  }, [mapEvents, timeRangeDays]);

  const activeIntelEvents = useMemo(
    () => intelEvents?.active ?? [],
    [intelEvents]
  );

  return (
    <section className="mb-12" data-testid="intelligence-map-section">
      {/* Section header */}
      <div className="flex items-end justify-between gap-4 mb-6">
        <div>
          <div className="label-eyebrow flex items-center gap-1.5">
            <MapIcon className="w-3 h-3" strokeWidth={2} />
            Intelligence Map · Romania
          </div>
          <h2 className="text-2xl font-semibold tracking-tight mt-1">
            Geospatial intelligence
          </h2>
          <p className="text-sm text-[#7b827b] mt-1">
            Forest events, anomalies, and intelligence signals · clustered view
          </p>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div
          className="mb-4 px-4 py-3 rounded-md border border-[#e76f51]/30 bg-[#e76f51]/5 text-sm text-[#9b2226]"
          data-testid="map-error"
          role="alert"
        >
          {error}
        </div>
      )}

      {/* Layer toggle controls */}
      <LayerControls layers={layers} onToggle={toggleLayer} />
      {/* Time range filter — applied client-side to the Forest Events layer */}
      <TimeRangeFilter value={timeRangeDays} onChange={setTimeRangeDays} />
      {/* Land cover filter — applies to the Forest Events layer only */}
      <LandCoverFilter filter={landCoverFilter} onToggle={toggleLandCover} />

      {/* Map + overlays wrapper */}
      <div className="relative rounded-lg overflow-hidden border border-[#eaece6]">
        {/* Loading scrim */}
        {loading && (
          <div
            className="absolute inset-0 z-[1000] bg-[#f4f5f2]/85 flex items-center justify-center pointer-events-none"
            data-testid="map-loading"
          >
            <div className="text-sm text-[#7b827b] animate-pulse">
              Loading map data…
            </div>
          </div>
        )}

        <MapContainer
          center={ROMANIA_CENTER}
          zoom={DEFAULT_ZOOM}
          scrollWheelZoom
          style={{ height: "520px", width: "100%" }}
          data-testid="leaflet-map"
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <ForestEventsLayer
            events={filteredMapEvents}
            visible={layers.events}
            landCoverFilter={landCoverFilter}
          />
          <AnomaliesLayer anomalies={anomalies} visible={layers.anomalies} />
          <IntelligenceEventsLayer
            events={activeIntelEvents}
            visible={layers.intelligence}
            threatByEventId={threatByEventId}
          />
          <RiskOverlayLayer
            riskRegions={riskData?.regions ?? []}
            visible={layers.risk_overlay}
          />
          <WeatherOverlayLayer
            weatherRegions={weatherData?.regions ?? []}
            visible={layers.weather_overlay}
          />
        </MapContainer>

        {/* Floating intelligence summary */}
        <SummaryOverlay summary={summary} />
      </div>

      {/* Colour legend */}
      <div
        className="flex flex-wrap gap-4 mt-3 text-xs text-[#7b827b]"
        data-testid="map-legend"
      >
        <span className="font-semibold text-[#1a1e1a]">Fill (severity):</span>
        {[
          { color: "#e9c46a", label: "Low" },
          { color: "#f4a261", label: "Medium" },
          { color: "#e76f51", label: "High" },
          { color: "#9b2226", label: "Critical" },
        ].map(({ color, label }) => (
          <div key={label} className="flex items-center gap-1.5">
            <span
              className="w-3 h-3 rounded-full shrink-0"
              style={{ background: color }}
              aria-hidden="true"
            />
            {label}
          </div>
        ))}
        {layers.risk_overlay && (
          <>
            <span className="font-semibold text-[#1a1e1a] ml-3">Risk glow:</span>
            {[
              { color: "#22c55e", label: "Low" },
              { color: "#eab308", label: "Moderate" },
              { color: "#f97316", label: "High" },
              { color: "#ef4444", label: "Extreme" },
            ].map(({ color, label }) => (
              <div key={label} className="flex items-center gap-1.5">
                <span
                  className="w-3 h-3 rounded-full shrink-0 border-2"
                  style={{ borderColor: color, background: "transparent" }}
                  aria-hidden="true"
                />
                {label}
              </div>
            ))}
          </>
        )}
        {layers.weather_overlay && (
          <>
            <span className="font-semibold text-[#1a1e1a] ml-3">Temperature:</span>
            {[
              { color: "#3b82f6", label: "< 0°C" },
              { color: "#60a5fa", label: "0–10°C" },
              { color: "#a3e635", label: "10–20°C" },
              { color: "#fb923c", label: "20–30°C" },
              { color: "#ef4444", label: "30–40°C" },
              { color: "#991b1b", label: "> 40°C" },
            ].map(({ color, label }) => (
              <div key={label} className="flex items-center gap-1.5">
                <span
                  className="w-3 h-3 rounded-full shrink-0"
                  style={{ background: color }}
                  aria-hidden="true"
                />
                {label}
              </div>
            ))}
          </>
        )}
        <span className="font-semibold text-[#1a1e1a] ml-3">Border (land cover):</span>
        {[
          { color: "#1b4332", label: "Forest" },
          { color: "#52b788", label: "Near Forest" },
          { color: "#ffd166", label: "Agriculture" },
          { color: "#ef476f", label: "Urban" },
          { color: "#118ab2", label: "Water" },
          { color: "#9ca3af", label: "Unknown" },
        ].map(({ color, label }) => (
          <div key={label} className="flex items-center gap-1.5">
            <span
              className="w-3 h-3 rounded-full shrink-0 border-2"
              style={{ borderColor: color, background: "transparent" }}
              aria-hidden="true"
            />
            {label}
          </div>
        ))}
      </div>
    </section>
  );
}
