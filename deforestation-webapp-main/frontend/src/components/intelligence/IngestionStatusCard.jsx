import { Clock, CheckCircle2, XCircle, Loader2, Zap } from "lucide-react";

/**
 * Format a UTC datetime string as a relative label ("2 min ago", "3 h ago", etc.)
 * Falls back to the raw string if parsing fails.
 */
function relativeTime(isoStr) {
  if (!isoStr) return "—";
  try {
    const diffMs = Date.now() - new Date(isoStr).getTime();
    const diffMin = Math.floor(diffMs / 60_000);
    if (diffMin < 1) return "just now";
    if (diffMin < 60) return `${diffMin} min ago`;
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24) return `${diffH} h ago`;
    return `${Math.floor(diffH / 24)} d ago`;
  } catch {
    return isoStr;
  }
}

function StatusBadge({ enabled, latestRun }) {
  if (!enabled) {
    return (
      <span
        className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-[#f4f5f2] text-[#7b827b]"
        data-testid="ingestion-status-badge-disabled"
      >
        Disabled
      </span>
    );
  }
  if (!latestRun) {
    return (
      <span
        className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-[#e8f5e9] text-[#2d5a27]"
        data-testid="ingestion-status-badge-active"
      >
        <Loader2 className="w-3 h-3 animate-spin" strokeWidth={2} />
        Waiting for first run
      </span>
    );
  }
  if (latestRun.status === "success") {
    return (
      <span
        className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-[#e8f5e9] text-[#2d5a27]"
        data-testid="ingestion-status-badge-success"
      >
        <CheckCircle2 className="w-3 h-3" strokeWidth={2} />
        Running
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-[#e76f51]/10 text-[#9b2226]"
      data-testid="ingestion-status-badge-failed"
    >
      <XCircle className="w-3 h-3" strokeWidth={2} />
      Last run failed
    </span>
  );
}

export default function IngestionStatusCard({ status, loading }) {
  if (loading) {
    return (
      <div
        className="card-flat animate-pulse h-48 bg-[#f4f5f2]"
        data-testid="ingestion-status-loading"
      />
    );
  }

  if (!status) {
    return (
      <div className="card-flat" data-testid="ingestion-status-empty">
        <div className="flex items-start justify-between">
          <div className="label-eyebrow">Ingestion Scheduler</div>
          <Zap className="w-4 h-4 text-[#7b827b]" strokeWidth={1.5} />
        </div>
        <p className="text-sm text-[#7b827b] mt-4">No status available.</p>
      </div>
    );
  }

  const { scheduler_enabled, poll_interval_minutes, latest_run, successful_runs, failed_runs } = status;

  const rows = [
    {
      label: "Last run",
      value: latest_run ? relativeTime(latest_run.completed_at) : "—",
      testId: "ingestion-last-run",
    },
    {
      label: "Events inserted",
      value: latest_run?.events_inserted ?? "—",
      testId: "ingestion-events-inserted",
    },
    {
      label: "Duplicates skipped",
      value: latest_run?.duplicates_skipped ?? "—",
      testId: "ingestion-duplicates-skipped",
    },
    {
      label: "Duration",
      value: latest_run ? `${latest_run.duration_seconds.toFixed(1)} s` : "—",
      testId: "ingestion-duration",
    },
    {
      label: "Successful / Failed",
      value: `${successful_runs} / ${failed_runs}`,
      testId: "ingestion-run-counts",
    },
  ];

  return (
    <div className="card-flat" data-testid="ingestion-status-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="label-eyebrow">Ingestion Scheduler</div>
          <div className="text-xs text-[#7b827b] mt-0.5">
            Poll interval: {poll_interval_minutes} min
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <Zap className="w-4 h-4 text-[#7b827b]" strokeWidth={1.5} />
          <StatusBadge enabled={scheduler_enabled} latestRun={latest_run} />
        </div>
      </div>

      <dl className="mt-4 space-y-2">
        {rows.map(({ label, value, testId }) => (
          <div key={label} className="flex justify-between items-baseline gap-2">
            <dt className="text-xs text-[#7b827b] shrink-0">{label}</dt>
            <dd
              className="text-sm font-medium text-[#1a1e1a] tabular-nums truncate text-right"
              data-testid={testId}
            >
              {value}
            </dd>
          </div>
        ))}
      </dl>

      {latest_run?.error && (
        <div
          className="mt-3 px-3 py-2 rounded text-xs text-[#9b2226] bg-[#e76f51]/8 border border-[#e76f51]/20 truncate"
          data-testid="ingestion-error-message"
          title={latest_run.error}
        >
          Error: {latest_run.error}
        </div>
      )}
    </div>
  );
}
