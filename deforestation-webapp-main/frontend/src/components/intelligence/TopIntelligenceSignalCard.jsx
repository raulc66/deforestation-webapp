import { Crosshair } from "lucide-react";

export default function TopIntelligenceSignalCard({ summary, loading }) {
  const hasSignal =
    summary?.highest_priority_region != null &&
    summary?.highest_priority_score != null;

  return (
    <div className="card-flat" data-testid="top-intelligence-signal-card">
      <div className="flex items-center gap-2 mb-4">
        <Crosshair className="w-4 h-4 text-[#7b827b]" strokeWidth={1.5} />
        <div className="label-eyebrow">Highest priority signal</div>
      </div>

      {loading && (
        <div className="animate-pulse space-y-2" data-testid="top-signal-loading">
          <div className="h-7 bg-[#f4f5f2] rounded w-3/4" />
          <div className="h-4 bg-[#f4f5f2] rounded w-1/3" />
        </div>
      )}

      {!loading && !hasSignal && (
        <p
          className="text-sm text-[#7b827b] py-2"
          data-testid="top-signal-empty"
        >
          No active intelligence signals
        </p>
      )}

      {!loading && hasSignal && (
        <div data-testid="top-signal-content">
          <p
            className="text-2xl font-bold tracking-tight text-[#1a1e1a]"
            data-testid="top-signal-region"
          >
            {summary.highest_priority_region}
          </p>
          <div className="flex items-center gap-3 mt-2">
            <div
              className="h-1.5 rounded-full bg-[#eaece6] overflow-hidden flex-1"
              aria-hidden="true"
            >
              <div
                className="h-full rounded-full bg-[#9b2226]"
                style={{ width: `${(summary.highest_priority_score * 100).toFixed(1)}%` }}
              />
            </div>
            <span
              className="text-sm font-mono font-semibold text-[#9b2226] tabular-nums shrink-0"
              data-testid="top-signal-score"
            >
              {summary.highest_priority_score.toFixed(4)}
            </span>
          </div>
          <p className="text-xs text-[#7b827b] mt-1.5">priority score · 0–1 scale</p>
        </div>
      )}
    </div>
  );
}
