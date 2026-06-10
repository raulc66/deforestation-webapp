import {
  AlertOctagon,
  TreePine,
  Gauge,
  FolderOpen,
  Search,
  CheckCircle2,
} from "lucide-react";

function Stat({ label, value, accent, icon: Icon, sub, testId }) {
  return (
    <div className="card-flat" data-testid={testId}>
      <div className="flex items-start justify-between">
        <div className="label-eyebrow">{label}</div>
        <Icon className="w-4 h-4 text-[#7b827b]" strokeWidth={1.5} />
      </div>
      <div
        className="font-bold text-3xl lg:text-4xl mt-3 tracking-tight"
        style={{ color: accent || "#1a1e1a" }}
      >
        {value}
      </div>
      {sub && <div className="text-xs text-[#7b827b] mt-1.5">{sub}</div>}
    </div>
  );
}

export default function AnalyticsOverviewCards({ overview, loading }) {
  const total = overview?.total_events ?? 0;
  const area = overview?.total_area_affected ?? 0;
  const confidence = overview?.average_confidence ?? 0;
  const open = overview?.open_events ?? 0;
  const investigating = overview?.investigating_events ?? 0;
  const resolved = overview?.resolved_events ?? 0;

  if (loading) {
    return (
      <div
        className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 lg:gap-5"
        data-testid="analytics-overview-loading"
      >
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="card-flat animate-pulse h-28 bg-[#f4f5f2]" />
        ))}
      </div>
    );
  }

  return (
    <div
      className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4 lg:gap-5"
      data-testid="analytics-overview"
    >
      <Stat
        label="Total events"
        value={total.toLocaleString()}
        icon={AlertOctagon}
        sub="all sources"
        testId="stat-total-events"
      />
      <Stat
        label="Area affected"
        value={`${area.toLocaleString()} ha`}
        icon={TreePine}
        sub="cumulative"
        testId="stat-area-affected"
      />
      <Stat
        label="Avg confidence"
        value={`${(confidence * 100).toFixed(1)}%`}
        icon={Gauge}
        sub="detection score"
        testId="stat-avg-confidence"
      />
      <Stat
        label="Open"
        value={open}
        accent="#e76f51"
        icon={FolderOpen}
        sub="active incidents"
        testId="stat-open-events"
      />
      <Stat
        label="Investigating"
        value={investigating}
        accent="#f4a261"
        icon={Search}
        sub="under review"
        testId="stat-investigating-events"
      />
      <Stat
        label="Resolved"
        value={resolved}
        accent="#2d5a27"
        icon={CheckCircle2}
        sub="closed incidents"
        testId="stat-resolved-events"
      />
    </div>
  );
}
