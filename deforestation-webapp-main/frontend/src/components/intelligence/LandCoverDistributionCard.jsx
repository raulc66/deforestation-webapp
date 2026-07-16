import { Layers } from "lucide-react";

/**
 * Display label and color for each land-cover type.
 * Order matches the classification priority used by the backend.
 */
const LAND_COVER_META = [
  { key: "forest",      label: "Forest",      color: "#1b4332" },
  { key: "near_forest", label: "Near Forest",  color: "#52b788" },
  { key: "agriculture", label: "Agriculture",  color: "#ffd166" },
  { key: "urban",       label: "Urban",        color: "#ef476f" },
  { key: "water",       label: "Water",        color: "#118ab2" },
  { key: "unknown",     label: "Unknown",      color: "#9ca3af" },
];

/**
 * A small horizontal bar indicating relative share.
 */
function DistributionBar({ value, max, color }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div
      className="h-1.5 rounded-full bg-[#eaece6] overflow-hidden mt-1"
      aria-hidden="true"
    >
      <div
        className="h-full rounded-full transition-all duration-500"
        style={{ width: `${pct}%`, background: color }}
      />
    </div>
  );
}

export default function LandCoverDistributionCard({ data, loading }) {
  if (loading) {
    return (
      <div
        className="card-flat animate-pulse h-56 bg-[#f4f5f2]"
        data-testid="land-cover-loading"
      />
    );
  }

  if (!data || !data.distribution) {
    return (
      <div className="card-flat" data-testid="land-cover-empty">
        <div className="flex items-start justify-between">
          <div className="label-eyebrow">Land Cover</div>
          <Layers className="w-4 h-4 text-[#7b827b]" strokeWidth={1.5} />
        </div>
        <p className="text-sm text-[#7b827b] mt-4">No classification data yet.</p>
      </div>
    );
  }

  /** Build a lookup from the distribution array. */
  const counts = Object.fromEntries(
    (data.distribution ?? []).map((d) => [d.land_cover, d.events])
  );
  const total = Object.values(counts).reduce((s, n) => s + n, 0);
  const maxCount = Math.max(...Object.values(counts), 1);

  const dataset = data.dataset ?? null;

  return (
    <div className="card-flat" data-testid="land-cover-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="label-eyebrow">Land Cover</div>
          <div className="text-xs text-[#7b827b] mt-0.5">
            {total.toLocaleString()} events classified
          </div>
        </div>
        <Layers className="w-4 h-4 text-[#7b827b] shrink-0" strokeWidth={1.5} />
      </div>

      {dataset && (
        <div
          className="mt-3 rounded-lg bg-[#f4f5f2] px-3 py-2 text-[11px] text-[#7b827b] space-y-0.5"
          data-testid="land-cover-dataset-info"
        >
          <div className="flex justify-between gap-2">
            <span className="font-medium text-[#3d4a3d]">Dataset source</span>
            <span className="truncate text-right" data-testid="dataset-source">
              {dataset.source}
            </span>
          </div>
          {dataset.version && dataset.version !== "unknown" && (
            <div className="flex justify-between gap-2">
              <span className="font-medium text-[#3d4a3d]">Version</span>
              <span data-testid="dataset-version">{dataset.version}</span>
            </div>
          )}
          {dataset.last_updated && dataset.last_updated !== "unknown" && (
            <div className="flex justify-between gap-2">
              <span className="font-medium text-[#3d4a3d]">Last updated</span>
              <span data-testid="dataset-last-updated">{dataset.last_updated}</span>
            </div>
          )}
        </div>
      )}

      <ul className="mt-4 space-y-2.5" data-testid="land-cover-list">
        {LAND_COVER_META.map(({ key, label, color }) => {
          const count = counts[key] ?? 0;
          const pct = total > 0 ? ((count / total) * 100).toFixed(1) : "0.0";
          return (
            <li key={key} data-testid={`land-cover-row-${key}`}>
              <div className="flex justify-between items-baseline gap-2">
                <div className="flex items-center gap-1.5 min-w-0">
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ background: color }}
                    aria-hidden="true"
                  />
                  <span className="text-xs text-[#1a1e1a] font-medium truncate">
                    {label}
                  </span>
                </div>
                <div className="flex items-baseline gap-1.5 shrink-0">
                  <span
                    className="text-sm font-semibold tabular-nums text-[#1a1e1a]"
                    data-testid={`land-cover-count-${key}`}
                  >
                    {count.toLocaleString()}
                  </span>
                  <span className="text-[10px] text-[#7b827b] tabular-nums">
                    {pct}%
                  </span>
                </div>
              </div>
              <DistributionBar value={count} max={maxCount} color={color} />
            </li>
          );
        })}
      </ul>
    </div>
  );
}
