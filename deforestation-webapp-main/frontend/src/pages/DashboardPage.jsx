import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import AppLayout from "@/components/layout/AppLayout";
import AnalyticsSection from "@/components/dashboard/AnalyticsSection";
import IntelligenceSection from "@/components/intelligence/IntelligenceSection";
import { useAuth } from "@/context/AuthContext";
import {
  ArrowUpRight,
  Cpu,
  Bell,
  BarChart3,
  Database,
  Bug,
  Satellite,
} from "lucide-react";

const placeholderModules = [
  {
    key: "ingestion",
    title: "Data Ingestion",
    Icon: Database,
    blurb: "GLAD, Hansen, MapBiomas — versioned pulls into the lake.",
  },
  {
    key: "scraping",
    title: "Web Scraping",
    Icon: Bug,
    blurb: "NGO reports, gov bulletins, news enrichment.",
  },
  {
    key: "satellite",
    title: "Satellite Processing",
    Icon: Satellite,
    blurb: "Sentinel-2 NDVI deltas with cloud masking.",
  },
  {
    key: "alerting",
    title: "Alerting",
    Icon: Bell,
    blurb: "Multi-channel dispatch with delivery receipts.",
  },
  {
    key: "analytics",
    title: "Analytics",
    Icon: BarChart3,
    blurb: "Time-series rollups & regional benchmarking.",
  },
  {
    key: "ai_predictions",
    title: "AI Predictions",
    Icon: Cpu,
    blurb: "Risk scoring + 30/60/90-day forecasts.",
  },
];

export default function DashboardPage() {
  const { user } = useAuth();
  const [overview, setOverview] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [alertsLoading, setAlertsLoading] = useState(true);
  const [alertsError, setAlertsError] = useState(null);

  const handleOverviewLoaded = useCallback((nextOverview) => {
    setOverview(nextOverview);
  }, []);

  useEffect(() => {
    let alive = true;
    (async () => {
      setAlertsLoading(true);
      setAlertsError(null);
      try {
        const { data } = await api.get("/alerts?limit=8");
        if (alive) setAlerts(data);
      } catch {
        if (alive) {
          setAlertsError("Could not load recent activity.");
          setAlerts([]);
        }
      } finally {
        if (alive) setAlertsLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const totalEvents = overview?.total_events;
  const headerCount =
    totalEvents != null ? totalEvents : alertsLoading ? "…" : alerts.length;

  return (
    <AppLayout>
      <div className="bg-grain min-h-screen">
        <div className="max-w-7xl mx-auto px-6 lg:px-10 py-8 lg:py-12" data-testid="dashboard-page">
          {/* Header */}
          <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6 mb-10">
            <div>
              <div className="label-eyebrow mb-3">Overview · Live</div>
              <h1 className="text-4xl lg:text-5xl font-bold tracking-tight">
                Welcome, {user?.name?.split(" ")[0] || "Watcher"}.
              </h1>
              <p className="text-[#4a524a] mt-3 max-w-xl">
                {overview
                  ? `Monitoring ${overview.total_events} forest events · ${overview.total_area_affected.toLocaleString()} ha tracked.`
                  : `Loading platform overview…`}
              </p>
            </div>
            <Link
              to="/map"
              data-testid="open-map-link"
              className="inline-flex items-center gap-2 px-5 py-2.5 bg-[#2d5a27] text-white rounded-md text-sm font-medium hover:bg-[#21421d] transition-colors self-start"
            >
              Open live map
              <ArrowUpRight className="w-4 h-4" strokeWidth={1.7} />
            </Link>
          </div>

          <AnalyticsSection onOverviewLoaded={handleOverviewLoaded} />

          <IntelligenceSection />

          {/* Recent activity — legacy alerts feed for map-compatible rows */}
          <div className="mb-12">
            <div className="flex items-center justify-between mb-5">
              <div>
                <div className="label-eyebrow">Recent activity</div>
                <h2 className="text-2xl font-semibold tracking-tight mt-1">
                  Newest detections
                </h2>
                <p className="text-sm text-[#7b827b] mt-1">
                  {headerCount} events in the system
                </p>
              </div>
              <Link
                to="/map"
                className="text-sm text-[#2d5a27] font-semibold hover:underline"
                data-testid="view-all-on-map"
              >
                View all on map →
              </Link>
            </div>

            {alertsError && (
              <div
                className="mb-4 px-4 py-3 rounded-md border border-[#e76f51]/30 bg-[#e76f51]/5 text-sm text-[#9b2226]"
                role="alert"
              >
                {alertsError}
              </div>
            )}

            <div className="bg-white border border-[#eaece6] rounded-lg overflow-hidden">
              <table className="w-full text-sm" data-testid="recent-alerts-table">
                <thead className="bg-[#f4f5f2] text-[#7b827b]">
                  <tr>
                    <th className="text-left font-semibold px-5 py-3">Title</th>
                    <th className="text-left font-semibold px-5 py-3 hidden md:table-cell">
                      Region
                    </th>
                    <th className="text-left font-semibold px-5 py-3">Severity</th>
                    <th className="text-right font-semibold px-5 py-3 hidden sm:table-cell">
                      Area (ha)
                    </th>
                    <th className="text-right font-semibold px-5 py-3 hidden md:table-cell">
                      Detected
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {alertsLoading && (
                    <tr>
                      <td colSpan={5} className="px-5 py-6 text-center text-[#7b827b]">
                        Loading alerts…
                      </td>
                    </tr>
                  )}
                  {!alertsLoading &&
                    alerts.map((a) => (
                      <tr
                        key={a.id}
                        className="border-t border-[#eaece6] hover:bg-[#f4f5f2]/60"
                        data-testid={`alert-row-${a.id}`}
                      >
                        <td className="px-5 py-3 font-medium text-[#1a1e1a]">
                          {a.title}
                        </td>
                        <td className="px-5 py-3 text-[#4a524a] hidden md:table-cell">
                          {a.region}, {a.country}
                        </td>
                        <td className="px-5 py-3">
                          <span className="inline-flex items-center gap-2 text-xs uppercase tracking-wider font-semibold">
                            <span
                              className="severity-dot"
                              style={{
                                background:
                                  {
                                    low: "#e9c46a",
                                    medium: "#f4a261",
                                    high: "#e76f51",
                                    critical: "#9b2226",
                                  }[a.severity] || "#7b827b",
                              }}
                            />
                            {a.severity}
                          </span>
                        </td>
                        <td className="px-5 py-3 text-right hidden sm:table-cell font-mono text-xs">
                          {a.area_ha.toLocaleString()}
                        </td>
                        <td className="px-5 py-3 text-right text-[#7b827b] hidden md:table-cell font-mono text-xs">
                          {new Date(a.detected_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))}
                  {!alertsLoading && !alertsError && alerts.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-5 py-6 text-center text-[#7b827b]">
                        No recent detections.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Placeholder modules */}
          <div>
            <div className="label-eyebrow mb-3">Roadmap modules</div>
            <h2 className="text-2xl font-semibold tracking-tight mb-2">
              Coming soon
            </h2>
            <p className="text-[#4a524a] mb-6 max-w-2xl">
              Each module ships behind a stable interface — extend independently
              without touching the rest of the platform.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {placeholderModules.map((m) => (
                <div
                  key={m.key}
                  className="card-flat relative overflow-hidden"
                  data-testid={`module-card-${m.key}`}
                >
                  <div className="absolute top-4 right-4 text-[9px] tracking-[0.22em] uppercase font-bold text-[#c84b31] bg-[#c84b31]/10 px-2 py-1 rounded">
                    Planned
                  </div>
                  <div className="w-10 h-10 rounded-md bg-[#eaece6] flex items-center justify-center mb-4">
                    <m.Icon className="w-5 h-5 text-[#2d5a27]" strokeWidth={1.5} />
                  </div>
                  <h3 className="font-semibold text-lg tracking-tight">
                    {m.title}
                  </h3>
                  <p className="text-sm text-[#4a524a] mt-2 leading-relaxed">
                    {m.blurb}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
