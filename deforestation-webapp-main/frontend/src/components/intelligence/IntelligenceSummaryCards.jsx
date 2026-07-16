import { Activity, CheckCircle2, AlertTriangle, ShieldAlert } from "lucide-react";

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

export default function IntelligenceSummaryCards({ summary, loading }) {
  if (loading) {
    return (
      <div
        className="grid grid-cols-2 lg:grid-cols-4 gap-4 lg:gap-5"
        data-testid="intelligence-summary-loading"
      >
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="card-flat animate-pulse h-28 bg-[#f4f5f2]" />
        ))}
      </div>
    );
  }

  const active = summary?.active ?? 0;
  const resolved = summary?.resolved ?? 0;
  const persistent = summary?.persistent ?? 0;
  const critical = summary?.critical ?? 0;

  return (
    <div
      className="grid grid-cols-2 lg:grid-cols-4 gap-4 lg:gap-5"
      data-testid="intelligence-summary-cards"
    >
      <Stat
        label="Active events"
        value={active}
        accent="#e76f51"
        icon={Activity}
        sub="currently monitored"
        testId="intel-stat-active"
      />
      <Stat
        label="Resolved"
        value={resolved}
        accent="#2d5a27"
        icon={CheckCircle2}
        sub="no longer detected"
        testId="intel-stat-resolved"
      />
      <Stat
        label="Persistent"
        value={persistent}
        accent="#c84b31"
        icon={AlertTriangle}
        sub="detection count ≥ 3"
        testId="intel-stat-persistent"
      />
      <Stat
        label="Critical"
        value={critical}
        accent="#9b2226"
        icon={ShieldAlert}
        sub="highest escalation"
        testId="intel-stat-critical"
      />
    </div>
  );
}
