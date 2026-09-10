function Stat({ label, value, accent, sub, testId }) {
  return (
    <div className="fw-metric min-w-0" data-testid={testId}>
      <div className="fw-kicker">{label}</div>
      <div
        className="fw-metric-value"
        style={{ color: accent || undefined }}
      >
        {value}
      </div>
      {sub && <div className="text-xs text-[var(--text-muted)] mt-1 leading-snug">{sub}</div>}
    </div>
  );
}

export default function IntelligenceSummaryCards({ summary, loading }) {
  if (loading) {
    return (
      <div
        className="fw-surface p-5 animate-pulse h-24 bg-[var(--surface-subtle)]"
        data-testid="intelligence-summary-loading"
      />
    );
  }

  const active = summary?.active ?? 0;
  const resolved = summary?.resolved ?? 0;
  const persistent = summary?.persistent ?? 0;
  const critical = summary?.critical ?? 0;

  return (
    <div
      className="fw-surface p-5"
      data-testid="intelligence-summary-cards"
    >
      <div className="fw-kicker mb-3">Event counts</div>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 lg:gap-6">
        <Stat
          label="Active events"
          value={active}
          accent="#e76f51"
          sub="currently monitored"
          testId="intel-stat-active"
        />
        <Stat
          label="Resolved"
          value={resolved}
          accent="#2d5a27"
          sub="no longer detected"
          testId="intel-stat-resolved"
        />
        <Stat
          label="Persistent"
          value={persistent}
          accent="#c84b31"
          sub="detection count ≥ 3"
          testId="intel-stat-persistent"
        />
        <Stat
          label="Critical"
          value={critical}
          accent="#9b2226"
          sub="highest escalation"
          testId="intel-stat-critical"
        />
      </div>
    </div>
  );
}
