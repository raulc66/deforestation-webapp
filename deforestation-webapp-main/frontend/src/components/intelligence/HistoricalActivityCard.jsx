import { History, TrendingUp, Flame, AlertTriangle } from "lucide-react";

/**
 * Derives summary stats from the three history data sources.
 * Pure computation — no side effects.
 */
function deriveStats(monthly, regions, hotspots) {
  const months = monthly?.months ?? [];
  const totalEvents = months.reduce((s, m) => s + (m.events ?? 0), 0);
  const totalAnomalies = months.reduce((s, m) => s + (m.anomalies ?? 0), 0);

  const increasing = (regions ?? [])
    .filter((r) => r.trend === "increasing")
    .sort((a, b) => b.change_percent - a.change_percent);
  const fastestGrowing = increasing[0]?.region ?? null;

  const hottestRegion = (hotspots ?? [])[0]?.region ?? null;

  return { totalEvents, totalAnomalies, fastestGrowing, hottestRegion };
}

function StatRow({ icon: Icon, label, value, loading, accent }) {
  return (
    <div className="flex items-center gap-3 py-2 border-b border-[#eaece6] last:border-0">
      <div
        className="w-7 h-7 rounded flex items-center justify-center shrink-0"
        style={{ background: `${accent}18` }}
      >
        <Icon className="w-3.5 h-3.5" style={{ color: accent }} strokeWidth={1.8} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-[10px] text-[#7b827b] uppercase tracking-wider">{label}</div>
        {loading ? (
          <div className="h-3.5 w-20 bg-[#eaece6] rounded animate-pulse mt-0.5" />
        ) : (
          <div className="text-sm font-semibold text-[#1a1e1a] truncate">
            {value ?? "—"}
          </div>
        )}
      </div>
    </div>
  );
}

export default function HistoricalActivityCard({ monthly, regions, hotspots, loading }) {
  const stats = loading
    ? { totalEvents: null, totalAnomalies: null, fastestGrowing: null, hottestRegion: null }
    : deriveStats(monthly, regions, hotspots);

  return (
    <div className="card-flat" data-testid="historical-activity-card">
      <div className="flex items-center gap-2 mb-3">
        <History className="w-4 h-4 text-[#7b827b]" strokeWidth={1.5} />
        <div>
          <div className="label-eyebrow">Historical</div>
          <h3 className="text-base font-semibold tracking-tight mt-0">Activity summary</h3>
        </div>
      </div>

      <div className="flex flex-col">
        <StatRow
          icon={AlertTriangle}
          label="Total events"
          value={loading ? null : stats.totalEvents?.toLocaleString()}
          loading={loading}
          accent="#e76f51"
        />
        <StatRow
          icon={AlertTriangle}
          label="Total anomalies"
          value={loading ? null : stats.totalAnomalies?.toLocaleString()}
          loading={loading}
          accent="#9b2226"
        />
        <StatRow
          icon={TrendingUp}
          label="Fastest-growing region"
          value={stats.fastestGrowing}
          loading={loading}
          accent="#2d5a27"
        />
        <StatRow
          icon={Flame}
          label="Hottest region"
          value={stats.hottestRegion}
          loading={loading}
          accent="#c84b31"
        />
      </div>
    </div>
  );
}
