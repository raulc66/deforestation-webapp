import { Globe2 } from "lucide-react";

export default function CountriesLeaderboard({ countries, loading }) {
  const top = (countries ?? []).slice(0, 5);
  const maxCount = top[0]?.event_count ?? 1;

  return (
    <div className="card-flat h-full" data-testid="analytics-countries">
      <div className="flex items-center gap-2 mb-5">
        <Globe2 className="w-4 h-4 text-[#7b827b]" strokeWidth={1.5} />
        <div>
          <div className="label-eyebrow">Regional impact</div>
          <h3 className="text-lg font-semibold tracking-tight mt-0.5">Top 5 countries</h3>
        </div>
      </div>

      {loading && (
        <div className="space-y-3 animate-pulse">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-10 bg-[#f4f5f2] rounded" />
          ))}
        </div>
      )}

      {!loading && top.length === 0 && (
        <p className="text-sm text-[#7b827b]">No country data available.</p>
      )}

      {!loading && top.length > 0 && (
        <ol className="space-y-3">
          {top.map((row, idx) => {
            const pct = maxCount ? (row.event_count / maxCount) * 100 : 0;
            return (
              <li key={row.country} data-testid={`country-rank-${idx + 1}`}>
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="font-medium text-[#1a1e1a]">
                    <span className="text-[#7b827b] mr-2 font-mono text-xs">{idx + 1}</span>
                    {row.country}
                  </span>
                  <span className="font-semibold tabular-nums">{row.event_count}</span>
                </div>
                <div className="h-1.5 rounded-full bg-[#eaece6] overflow-hidden">
                  <div
                    className="h-full rounded-full bg-[#2d5a27]"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <div className="text-xs text-[#7b827b] mt-1 tabular-nums">
                  {row.affected_area_ha.toLocaleString()} ha
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
