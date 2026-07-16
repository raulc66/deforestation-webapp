import { useCallback, useEffect, useState } from "react";
import {
  ClipboardList,
  AlertTriangle,
  Clock,
  MapPin,
} from "lucide-react";
import { fetchInvestigationStatistics } from "@/api/investigations";

function StatBlock({ label, value, testId, accent }) {
  return (
    <div
      className="bg-white border border-[#eaece6] rounded-lg px-4 py-3"
      data-testid={testId}
    >
      <div className="text-[10px] tracking-[0.18em] uppercase text-[#7b827b] font-semibold">
        {label}
      </div>
      <div className={`text-2xl font-bold mt-1 tabular-nums ${accent || "text-[#1a1e1a]"}`}>
        {value}
      </div>
    </div>
  );
}

export default function InvestigationsCommandCenterCard({ loading: parentLoading }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchInvestigationStatistics();
      setStats(data);
    } catch (err) {
      setError(err.message || "Failed to load investigation stats.");
      setStats(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const isLoading = loading || parentLoading;
  const regions = stats?.investigations_by_region
    ? Object.entries(stats.investigations_by_region)
    : [];

  return (
    <div
      className="bg-white border border-[#eaece6] rounded-lg p-5"
      data-testid="investigations-command-center"
    >
      <div className="flex items-center gap-2 mb-4">
        <ClipboardList className="w-4 h-4 text-[#2d5a27]" strokeWidth={1.8} />
        <h3 className="text-sm font-semibold text-[#1a1e1a]">Investigations</h3>
      </div>

      {error && (
        <p className="text-xs text-[#9b2226] mb-3" data-testid="investigations-cc-error">
          {error}
        </p>
      )}

      {isLoading && (
        <p className="text-sm text-[#7b827b]" data-testid="investigations-cc-loading">
          Loading…
        </p>
      )}

      {!isLoading && stats && (
        <>
          <div className="grid grid-cols-2 gap-3 mb-4">
            <StatBlock
              label="Open"
              value={stats.open_investigations ?? 0}
              testId="investigations-open-count"
            />
            <StatBlock
              label="Critical"
              value={stats.critical_investigations ?? 0}
              testId="investigations-critical-count"
              accent="text-[#9b2226]"
            />
          </div>

          <div
            className="flex items-center gap-2 text-sm text-[#4a524a] mb-4"
            data-testid="investigations-avg-resolution"
          >
            <Clock className="w-3.5 h-3.5 text-[#7b827b]" />
            <span>
              Avg resolution:{" "}
              <strong className="text-[#1a1e1a]">
                {stats.average_resolution_time_hours != null
                  ? `${stats.average_resolution_time_hours}h`
                  : "—"}
              </strong>
            </span>
          </div>

          {regions.length > 0 && (
            <div data-testid="investigations-by-region">
              <div className="text-[10px] tracking-[0.18em] uppercase text-[#7b827b] font-semibold mb-2 flex items-center gap-1">
                <MapPin className="w-3 h-3" />
                By region
              </div>
              <ul className="space-y-1">
                {regions.slice(0, 5).map(([region, count]) => (
                  <li
                    key={region}
                    className="flex justify-between text-xs text-[#4a524a]"
                    data-testid={`investigations-region-${region}`}
                  >
                    <span>{region}</span>
                    <span className="font-mono font-semibold">{count}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {stats.critical_investigations > 0 && (
            <div
              className="mt-3 flex items-center gap-1.5 text-xs text-[#9b2226]"
              data-testid="investigations-critical-alert"
            >
              <AlertTriangle className="w-3.5 h-3.5" />
              {stats.critical_investigations} critical investigation
              {stats.critical_investigations !== 1 ? "s" : ""} require attention
            </div>
          )}
        </>
      )}
    </div>
  );
}
