import { useEffect, useMemo, useRef, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import AppLayout from "@/components/layout/AppLayout";
import { api } from "@/lib/api";
import { Filter } from "lucide-react";
import { useDemo } from "@/context/DemoContext";
import { useLeafletMap } from "@/lib/useLeafletMap";

const severityColor = {
  low: "#e9c46a",
  medium: "#f4a261",
  high: "#e76f51",
  critical: "#9b2226",
};

const severityRadius = {
  low: 6,
  medium: 8,
  high: 10,
  critical: 13,
};

const SEVERITIES = ["low", "medium", "high", "critical"];

function appendLabeledValue(parent, label, value, valueClassName) {
  const cell = document.createElement("div");
  const lab = document.createElement("div");
  lab.className = "text-[#7b827b]";
  lab.textContent = label;
  const val = document.createElement("div");
  val.className = valueClassName;
  val.textContent = value;
  cell.appendChild(lab);
  cell.appendChild(val);
  parent.appendChild(cell);
}

/** Build MapPage alert popups as DOM nodes (no HTML string interpolation). */
function buildAlertPopupContent(alert) {
  const root = document.createElement("div");
  root.className = "font-sans";

  const severity = document.createElement("div");
  severity.className =
    "text-[10px] tracking-[0.2em] uppercase font-bold text-[#7b827b] mb-1";
  severity.textContent = String(alert.severity ?? "");
  root.appendChild(severity);

  const title = document.createElement("div");
  title.className = "font-bold text-[15px] leading-tight mb-1";
  title.textContent = String(alert.title ?? "");
  root.appendChild(title);

  const place = document.createElement("div");
  place.className = "text-xs text-[#4a524a] mb-2";
  place.textContent = `${alert.region ?? ""}, ${alert.country ?? ""}`;
  root.appendChild(place);

  const grid = document.createElement("div");
  grid.className = "grid grid-cols-2 gap-2 text-xs";

  const areaHa =
    typeof alert.area_ha === "number" ? alert.area_ha.toLocaleString() : "—";
  const confidencePct =
    typeof alert.confidence === "number"
      ? `${(alert.confidence * 100).toFixed(0)}%`
      : "—";

  appendLabeledValue(grid, "Area", `${areaHa} ha`, "font-mono font-semibold");
  appendLabeledValue(grid, "Confidence", confidencePct, "font-mono font-semibold");
  appendLabeledValue(grid, "Source", String(alert.source ?? ""), "font-semibold");
  appendLabeledValue(
    grid,
    "Status",
    String(alert.status ?? ""),
    "font-semibold capitalize"
  );

  root.appendChild(grid);
  return root;
}

export default function MapPage() {
  const { isDemo } = useDemo();
  const mapElRef = useRef(null);
  const map = useLeafletMap(mapElRef, {
    center: [-3.5, -60],
    zoom: 3,
    scrollWheelZoom: true,
    zoomControl: false,
    zoomControlPosition: "bottomright",
  });
  const [alerts, setAlerts] = useState([]);
  const [filters, setFilters] = useState(new Set(SEVERITIES));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (isDemo) return;
    let alive = true;
    (async () => {
      try {
        const { data } = await api.get("/alerts?limit=500");
        if (alive) setAlerts(data);
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [isDemo]);

  const visible = useMemo(
    () => alerts.filter((a) => filters.has(a.severity)),
    [alerts, filters]
  );

  useEffect(() => {
    if (!map) return undefined;
    const group = L.layerGroup();
    visible.forEach((a) => {
      const lat = a?.location?.lat;
      const lng = a?.location?.lng;
      if (typeof lat !== "number" || typeof lng !== "number") return;
      const color = severityColor[a.severity];
      const marker = L.circleMarker([lat, lng], {
        radius: severityRadius[a.severity],
        color,
        fillColor: color,
        fillOpacity: 0.55,
        weight: 2,
      });
      marker.bindPopup(buildAlertPopupContent(a));
      group.addLayer(marker);
    });
    group.addTo(map);
    return () => {
      map.removeLayer(group);
    };
  }, [map, visible]);

  if (isDemo) {
    return <Navigate to="/dashboard" replace />;
  }

  const toggle = (sev) => {
    setFilters((prev) => {
      const next = new Set(prev);
      if (next.has(sev)) next.delete(sev);
      else next.add(sev);
      return next;
    });
  };

  const counts = SEVERITIES.reduce(
    (acc, s) => ({ ...acc, [s]: alerts.filter((a) => a.severity === s).length }),
    {}
  );

  return (
    <AppLayout>
      <div className="relative h-screen md:h-screen" data-testid="map-page">
        {/* Map */}
        <div className="absolute inset-0">
          <div
            ref={mapElRef}
            className="w-full h-full"
            data-testid="leaflet-map"
          />
        </div>

        {/* Glass header */}
        <div
          className="absolute top-4 left-4 right-4 md:left-6 md:right-auto md:max-w-md z-[400] rounded-lg px-5 py-4 shadow-sm bg-white border border-[#eaece6]"
          data-testid="map-header"
        >
          <div className="label-eyebrow">Platform detections</div>
          <h2 className="text-xl font-semibold tracking-tight mt-1">
            Unscoped event feed
          </h2>
          <p className="text-xs text-[#4a524a] mt-1" data-testid="map-unscoped-notice">
            These detections are not limited to forests your organization monitors.
            Use Command Center for organization-priority intelligence.
          </p>
          <p className="text-xs text-[#7b827b] mt-2">
            {loading
              ? "Loading…"
              : `${visible.length} of ${alerts.length} events visible`}
          </p>
          <Link
            to="/dashboard"
            className="inline-block mt-3 text-sm font-semibold text-[#2d5a27] hover:underline"
            data-testid="map-to-command-center"
          >
            Open Command Center
          </Link>
        </div>

        {/* Glass filter panel */}
        <div
          className="absolute bottom-6 left-4 md:left-6 z-[400] rounded-lg px-5 py-4 shadow-sm min-w-[240px] bg-white border border-[#eaece6]"
          data-testid="map-filter-panel"
        >
          <div className="flex items-center gap-2 mb-3">
            <Filter className="w-3.5 h-3.5 text-[#4a524a]" strokeWidth={1.6} />
            <div className="label-eyebrow">Severity filter</div>
          </div>
          <div className="space-y-1.5">
            {SEVERITIES.map((s) => (
              <button
                key={s}
                onClick={() => toggle(s)}
                data-testid={`filter-${s}`}
                className={`w-full flex items-center gap-3 px-2.5 py-1.5 rounded-md text-sm transition-colors ${
                  filters.has(s)
                    ? "bg-white/70 text-[#1a1e1a]"
                    : "bg-transparent text-[#7b827b] opacity-60"
                }`}
              >
                <span
                  className="severity-dot"
                  style={{ background: severityColor[s] }}
                />
                <span className="capitalize flex-1 text-left">{s}</span>
                <span className="font-mono text-xs">{counts[s]}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
