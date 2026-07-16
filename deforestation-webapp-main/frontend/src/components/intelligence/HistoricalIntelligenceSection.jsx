/**
 * HistoricalIntelligenceSection — temporal intelligence for analysts.
 *
 * Self-fetching section that renders:
 *   1. HistoricalActivityCard  — top-level summary stats
 *   2. Daily Activity chart    — events + anomalies over a selectable range
 *   3. Monthly summary chart   — stacked bars: forest / urban / other events
 *   4. Regional trend table    — last-30d vs prior-30d per region with trend badge
 *   5. Hotspot ranking table   — all-time hotspots sorted by detection count
 *
 * Charts use recharts (already a project dependency).
 * Daily range changes refetch only the daily endpoint to avoid redundant calls.
 */
import { useCallback, useEffect, useState } from "react";
import { History, TrendingUp, TrendingDown, Minus } from "lucide-react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import {
  fetchHistoricalDaily,
  fetchHistoricalRegions,
  fetchHistoricalHotspots,
  fetchHistoricalMonthly,
} from "@/api/analytics";
import { formatApiErrorDetail } from "@/lib/api";
import HistoricalActivityCard from "./HistoricalActivityCard";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DAILY_RANGE_OPTIONS = [
  { value: 7, label: "7 days" },
  { value: 30, label: "30 days" },
  { value: 90, label: "90 days" },
  { value: 365, label: "1 year" },
];

const SEVERITY_COLORS = {
  critical: "#9b2226",
  high: "#e76f51",
  medium: "#f4a261",
  low: "#e9c46a",
};

const TREND_CONFIG = {
  increasing: { color: "#9b2226", Icon: TrendingUp,   label: "Increasing" },
  decreasing: { color: "#2d5a27", Icon: TrendingDown, label: "Decreasing" },
  stable:     { color: "#7b827b", Icon: Minus,        label: "Stable" },
};

// ---------------------------------------------------------------------------
// Custom tooltip helpers
// ---------------------------------------------------------------------------

function DailyTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-[#eaece6] rounded-md px-3 py-2 text-xs shadow-sm">
      <div className="font-semibold text-[#1a1e1a] mb-1">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.color }}>
          {p.name}: <span className="font-bold">{p.value}</span>
        </div>
      ))}
    </div>
  );
}

function MonthlyTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-[#eaece6] rounded-md px-3 py-2 text-xs shadow-sm">
      <div className="font-semibold text-[#1a1e1a] mb-1">{label}</div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.fill ?? p.color }}>
          {p.name}: <span className="font-bold">{p.value}</span>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function DailyRangeToggle({ value, onChange }) {
  return (
    <div className="flex gap-1" data-testid="daily-range-toggle">
      {DAILY_RANGE_OPTIONS.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
            value === opt.value
              ? "bg-[#2d5a27] text-white"
              : "bg-[#f4f5f2] text-[#4a524a] hover:bg-[#eaece6]"
          }`}
          data-testid={`range-btn-${opt.value}`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

function SkeletonBlock({ className = "" }) {
  return (
    <div className={`animate-pulse bg-[#f4f5f2] rounded ${className}`} />
  );
}

/** Format 'YYYY-MM-DD' to 'Jun 1' */
function fmtDay(s) {
  if (!s) return "";
  const d = new Date(s + "T00:00:00");
  return isNaN(d) ? s : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

/** Format 'YYYY-MM' to 'Jun 2026' */
function fmtMonth(s) {
  if (!s) return "";
  const d = new Date(s + "-01T00:00:00");
  return isNaN(d) ? s : d.toLocaleDateString(undefined, { month: "short", year: "numeric" });
}

function TrendBadge({ trend }) {
  const cfg = TREND_CONFIG[trend] ?? TREND_CONFIG.stable;
  const { Icon, color, label } = cfg;
  return (
    <span
      className="inline-flex items-center gap-1 text-[10px] font-semibold px-1.5 py-0.5 rounded"
      style={{ color, background: `${color}18` }}
      data-testid={`trend-badge-${trend}`}
    >
      <Icon className="w-3 h-3" strokeWidth={2} />
      {label}
    </span>
  );
}

function SeverityDot({ severity }) {
  return (
    <span
      className="inline-block w-2.5 h-2.5 rounded-full shrink-0"
      style={{ background: SEVERITY_COLORS[severity] ?? "#9ca3af" }}
      title={severity}
    />
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function HistoricalIntelligenceSection() {
  const [dailyData, setDailyData] = useState(null);
  const [regionsData, setRegionsData] = useState(null);
  const [hotspotsData, setHotspotsData] = useState(null);
  const [monthlyData, setMonthlyData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [dailyLoading, setDailyLoading] = useState(false);
  const [error, setError] = useState(null);
  const [dailyRange, setDailyRange] = useState(30);

  // Fetch regions / hotspots / monthly once on mount.
  const loadBase = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [regions, hotspots, monthly] = await Promise.all([
        fetchHistoricalRegions(),
        fetchHistoricalHotspots(),
        fetchHistoricalMonthly(),
      ]);
      setRegionsData(regions);
      setHotspotsData(hotspots);
      setMonthlyData(monthly);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(
        formatApiErrorDetail(detail) ||
          err.message ||
          "Failed to load historical intelligence data."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch daily chart whenever range changes.
  const loadDaily = useCallback(async (days) => {
    setDailyLoading(true);
    try {
      const daily = await fetchHistoricalDaily(days);
      setDailyData(daily);
    } catch {
      // Intentional no-op: daily chart shows empty state on failure.
    } finally {
      setDailyLoading(false);
    }
  }, []);

  useEffect(() => { loadBase(); }, [loadBase]);
  useEffect(() => { loadDaily(dailyRange); }, [loadDaily, dailyRange]);

  // Derived chart data.
  const dailyChartData = (dailyData?.days ?? []).map((d) => ({
    ...d,
    label: fmtDay(d.date),
  }));

  const monthlyChartData = (monthlyData?.months ?? []).map((m) => {
    const other = Math.max(0, (m.events ?? 0) - (m.forest_events ?? 0) - (m.urban_events ?? 0));
    return {
      ...m,
      label: fmtMonth(m.month),
      other_events: other,
    };
  });

  return (
    <section className="mb-12" data-testid="historical-intelligence-section">
      {/* Section header */}
      <div className="flex items-end justify-between gap-4 mb-6">
        <div>
          <div className="label-eyebrow flex items-center gap-1.5">
            <History className="w-3 h-3" strokeWidth={2} />
            Historical Intelligence
          </div>
          <h2 className="text-2xl font-semibold tracking-tight mt-1">
            Activity over time
          </h2>
          <p className="text-sm text-[#7b827b] mt-1">
            Trends, hotspots, and regional shifts · all-time data
          </p>
        </div>
        {error && (
          <button
            type="button"
            onClick={loadBase}
            className="text-sm text-[#2d5a27] font-semibold hover:underline shrink-0"
            data-testid="history-retry"
          >
            Retry
          </button>
        )}
      </div>

      {error && (
        <div
          className="mb-6 px-4 py-3 rounded-md border border-[#e76f51]/30 bg-[#e76f51]/5 text-sm text-[#9b2226]"
          data-testid="history-error"
          role="alert"
        >
          {error}
        </div>
      )}

      {/* Summary card */}
      <HistoricalActivityCard
        monthly={monthlyData}
        regions={regionsData}
        hotspots={hotspotsData}
        loading={loading}
      />

      {/* ------------------------------------------------------------------ */}
      {/* Daily activity chart                                                */}
      {/* ------------------------------------------------------------------ */}
      <div className="card-flat mt-6" data-testid="daily-activity-chart">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <div className="label-eyebrow">Daily activity</div>
            <h3 className="text-lg font-semibold tracking-tight mt-0.5">
              Events &amp; anomalies per day
            </h3>
          </div>
          <DailyRangeToggle value={dailyRange} onChange={setDailyRange} />
        </div>

        {(loading || dailyLoading) && <SkeletonBlock className="h-64" />}

        {!loading && !dailyLoading && dailyChartData.length === 0 && (
          <p
            className="text-sm text-[#7b827b] h-64 flex items-center justify-center"
            data-testid="daily-empty"
          >
            No activity data for this period.
          </p>
        )}

        {!loading && !dailyLoading && dailyChartData.length > 0 && (
          <div className="h-64" data-testid="daily-chart-canvas">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={dailyChartData}
                margin={{ top: 8, right: 12, left: -12, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#eaece6" vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 10, fill: "#7b827b" }}
                  interval="preserveStartEnd"
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 11, fill: "#7b827b" }}
                  width={32}
                />
                <Tooltip content={<DailyTooltip />} />
                <Legend
                  wrapperStyle={{ fontSize: "11px", paddingTop: "8px" }}
                />
                <Line
                  type="monotone"
                  dataKey="events"
                  name="Events"
                  stroke="#2d5a27"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="anomalies"
                  name="Anomalies"
                  stroke="#e76f51"
                  strokeWidth={1.5}
                  strokeDasharray="4 3"
                  dot={false}
                  activeDot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Monthly summary chart                                               */}
      {/* ------------------------------------------------------------------ */}
      <div className="card-flat mt-5" data-testid="monthly-summary-chart">
        <div className="mb-4">
          <div className="label-eyebrow">Monthly breakdown</div>
          <h3 className="text-lg font-semibold tracking-tight mt-0.5">
            Events by land cover type
          </h3>
        </div>

        {loading && <SkeletonBlock className="h-64" />}

        {!loading && monthlyChartData.length === 0 && (
          <p
            className="text-sm text-[#7b827b] h-64 flex items-center justify-center"
            data-testid="monthly-empty"
          >
            No monthly data available.
          </p>
        )}

        {!loading && monthlyChartData.length > 0 && (
          <div className="h-64" data-testid="monthly-chart-canvas">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={monthlyChartData}
                margin={{ top: 8, right: 12, left: -12, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#eaece6" vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 10, fill: "#7b827b" }}
                  interval="preserveStartEnd"
                />
                <YAxis
                  allowDecimals={false}
                  tick={{ fontSize: 11, fill: "#7b827b" }}
                  width={32}
                />
                <Tooltip content={<MonthlyTooltip />} />
                <Legend wrapperStyle={{ fontSize: "11px", paddingTop: "8px" }} />
                <Bar dataKey="forest_events" name="Forest/Near-Forest" stackId="a" fill="#2d5a27" />
                <Bar dataKey="urban_events"  name="Urban"              stackId="a" fill="#ef476f" />
                <Bar dataKey="other_events"  name="Other"              stackId="a" fill="#b0b8af" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Regional trend table + Hotspot ranking                             */}
      {/* ------------------------------------------------------------------ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mt-5">

        {/* Regional trends */}
        <div className="card-flat" data-testid="regional-trend-table">
          <div className="mb-4">
            <div className="label-eyebrow">Regional trends</div>
            <h3 className="text-lg font-semibold tracking-tight mt-0.5">
              30-day vs prior 30-day
            </h3>
          </div>

          {loading && (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => (
                <SkeletonBlock key={i} className="h-8" />
              ))}
            </div>
          )}

          {!loading && (!regionsData || regionsData.length === 0) && (
            <p className="text-sm text-[#7b827b]" data-testid="regions-empty">
              No regional data available.
            </p>
          )}

          {!loading && regionsData && regionsData.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs" data-testid="regions-table">
                <thead>
                  <tr className="text-[#7b827b] border-b border-[#eaece6]">
                    <th className="text-left py-2 font-medium">Region</th>
                    <th className="text-right py-2 font-medium">Last 30d</th>
                    <th className="text-right py-2 font-medium">Prev 30d</th>
                    <th className="text-right py-2 font-medium">Change</th>
                    <th className="text-center py-2 font-medium">Trend</th>
                  </tr>
                </thead>
                <tbody>
                  {regionsData.map((row) => (
                    <tr
                      key={row.region}
                      className="border-b border-[#f4f5f2] last:border-0 hover:bg-[#f9faf8]"
                      data-testid={`region-row-${row.region}`}
                    >
                      <td className="py-2 font-medium text-[#1a1e1a] truncate max-w-[110px]">
                        {row.region}
                      </td>
                      <td className="py-2 text-right tabular-nums">{row.events_last_30d}</td>
                      <td className="py-2 text-right tabular-nums text-[#7b827b]">
                        {row.events_previous_30d}
                      </td>
                      <td
                        className="py-2 text-right tabular-nums font-semibold"
                        style={{
                          color:
                            row.change_percent > 10
                              ? "#9b2226"
                              : row.change_percent < -10
                              ? "#2d5a27"
                              : "#7b827b",
                        }}
                      >
                        {row.change_percent > 0 ? "+" : ""}
                        {row.change_percent.toFixed(1)}%
                      </td>
                      <td className="py-2 text-center">
                        <TrendBadge trend={row.trend} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Hotspot ranking */}
        <div className="card-flat" data-testid="hotspot-ranking-table">
          <div className="mb-4">
            <div className="label-eyebrow">All-time hotspots</div>
            <h3 className="text-lg font-semibold tracking-tight mt-0.5">
              Ranked by detection count
            </h3>
          </div>

          {loading && (
            <div className="space-y-2">
              {[...Array(5)].map((_, i) => (
                <SkeletonBlock key={i} className="h-8" />
              ))}
            </div>
          )}

          {!loading && (!hotspotsData || hotspotsData.length === 0) && (
            <p className="text-sm text-[#7b827b]" data-testid="hotspots-empty">
              No hotspot data available.
            </p>
          )}

          {!loading && hotspotsData && hotspotsData.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs" data-testid="hotspots-table">
                <thead>
                  <tr className="text-[#7b827b] border-b border-[#eaece6]">
                    <th className="text-left py-2 font-medium">#</th>
                    <th className="text-left py-2 font-medium">Region</th>
                    <th className="text-right py-2 font-medium">Detections</th>
                    <th className="text-right py-2 font-medium">Avg Priority</th>
                    <th className="text-center py-2 font-medium">Top Severity</th>
                  </tr>
                </thead>
                <tbody>
                  {hotspotsData.map((row, idx) => (
                    <tr
                      key={row.region}
                      className="border-b border-[#f4f5f2] last:border-0 hover:bg-[#f9faf8]"
                      data-testid={`hotspot-row-${row.region}`}
                    >
                      <td className="py-2 text-[#7b827b] font-mono">{idx + 1}</td>
                      <td className="py-2 font-medium text-[#1a1e1a] truncate max-w-[110px]">
                        {row.region}
                      </td>
                      <td className="py-2 text-right tabular-nums font-semibold">
                        {row.detections.toLocaleString()}
                      </td>
                      <td className="py-2 text-right tabular-nums text-[#4a524a]">
                        {row.average_priority.toFixed(3)}
                      </td>
                      <td className="py-2 text-center">
                        <div className="flex items-center justify-center gap-1">
                          <SeverityDot severity={row.highest_severity} />
                          <span className="capitalize">{row.highest_severity}</span>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
