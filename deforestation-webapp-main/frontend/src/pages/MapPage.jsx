import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, ZoomControl } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import AppLayout from "@/components/layout/AppLayout";
import { api } from "@/lib/api";
import { Filter } from "lucide-react";

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

export default function MapPage() {
  const [alerts, setAlerts] = useState([]);
  const [filters, setFilters] = useState(new Set(SEVERITIES));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
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
  }, []);

  const visible = useMemo(
    () => alerts.filter((a) => filters.has(a.severity)),
    [alerts, filters]
  );

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
          <MapContainer
            center={[-3.5, -60]}
            zoom={3}
            scrollWheelZoom
            zoomControl={false}
            className="w-full h-full"
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <ZoomControl position="bottomright" />
            {visible.map((a) => (
              <CircleMarker
                key={a.id}
                center={[a.location.lat, a.location.lng]}
                radius={severityRadius[a.severity]}
                pathOptions={{
                  color: severityColor[a.severity],
                  fillColor: severityColor[a.severity],
                  fillOpacity: 0.55,
                  weight: 2,
                }}
              >
                <Popup>
                  <div className="font-sans">
                    <div className="text-[10px] tracking-[0.2em] uppercase font-bold text-[#7b827b] mb-1">
                      {a.severity}
                    </div>
                    <div className="font-bold text-[15px] leading-tight mb-1">
                      {a.title}
                    </div>
                    <div className="text-xs text-[#4a524a] mb-2">
                      {a.region}, {a.country}
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <div className="text-[#7b827b]">Area</div>
                        <div className="font-mono font-semibold">
                          {a.area_ha.toLocaleString()} ha
                        </div>
                      </div>
                      <div>
                        <div className="text-[#7b827b]">Confidence</div>
                        <div className="font-mono font-semibold">
                          {(a.confidence * 100).toFixed(0)}%
                        </div>
                      </div>
                      <div>
                        <div className="text-[#7b827b]">Source</div>
                        <div className="font-semibold">{a.source}</div>
                      </div>
                      <div>
                        <div className="text-[#7b827b]">Status</div>
                        <div className="font-semibold capitalize">{a.status}</div>
                      </div>
                    </div>
                  </div>
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        </div>

        {/* Glass header */}
        <div
          className="glass absolute top-4 left-4 right-4 md:left-6 md:right-auto md:max-w-md z-[400] rounded-lg px-5 py-4 shadow-sm"
          data-testid="map-header"
        >
          <div className="label-eyebrow">Live Map</div>
          <h2 className="text-xl font-semibold tracking-tight mt-1">
            Global deforestation alerts
          </h2>
          <p className="text-xs text-[#4a524a] mt-1">
            {loading
              ? "Loading…"
              : `${visible.length} of ${alerts.length} alerts visible`}
          </p>
        </div>

        {/* Glass filter panel */}
        <div
          className="glass absolute bottom-6 left-4 md:left-6 z-[400] rounded-lg px-5 py-4 shadow-sm min-w-[240px]"
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
