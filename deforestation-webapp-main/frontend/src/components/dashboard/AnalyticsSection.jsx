import { useCallback, useEffect, useState } from "react";
import { fetchDashboardAnalytics } from "@/api/analytics";
import { formatApiErrorDetail } from "@/lib/api";
import AnalyticsOverviewCards from "@/components/dashboard/AnalyticsOverviewCards";
import CountriesLeaderboard from "@/components/dashboard/CountriesLeaderboard";
import EventTypeChart from "@/components/dashboard/EventTypeChart";
import SeverityChart from "@/components/dashboard/SeverityChart";
import TrendsChart from "@/components/dashboard/TrendsChart";

export default function AnalyticsSection({ onOverviewLoaded }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchDashboardAnalytics();
      setData(result);
      onOverviewLoaded?.(result.overview);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(formatApiErrorDetail(detail) || err.message || "Failed to load analytics.");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [onOverviewLoaded]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <section className="mb-12" data-testid="analytics-section">
      <div className="flex items-end justify-between gap-4 mb-6">
        <div>
          <div className="label-eyebrow">Analytics · Live</div>
          <h2 className="text-2xl font-semibold tracking-tight mt-1">Platform insights</h2>
        </div>
        {error && (
          <button
            type="button"
            onClick={load}
            className="text-sm text-[#2d5a27] font-semibold hover:underline shrink-0"
            data-testid="analytics-retry"
          >
            Retry
          </button>
        )}
      </div>

      {error && (
        <div
          className="mb-6 px-4 py-3 rounded-md border border-[#e76f51]/30 bg-[#e76f51]/5 text-sm text-[#9b2226]"
          data-testid="analytics-error"
          role="alert"
        >
          {error}
        </div>
      )}

      <AnalyticsOverviewCards overview={data?.overview} loading={loading && !data} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mt-6">
        <CountriesLeaderboard countries={data?.countries} loading={loading && !data} />
        <EventTypeChart eventTypes={data?.eventTypes} loading={loading && !data} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5 mt-5">
        <SeverityChart severity={data?.severity} loading={loading && !data} />
        <TrendsChart trends={data?.trends} loading={loading && !data} />
      </div>
    </section>
  );
}
