import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Brain } from "lucide-react";
import {
  fetchIntelligenceEvents,
  fetchIntelligenceSummary,
  fetchIngestionStatus,
  fetchNotificationsStatus,
  fetchLandCoverDistribution,
  fetchRegionalRisk,
} from "@/api/analytics";
import { formatApiErrorDetail } from "@/lib/api";
import IntelligenceSummaryCards from "./IntelligenceSummaryCards";
import TopIntelligenceSignalCard from "./TopIntelligenceSignalCard";
import ActiveIntelligenceEvents from "./ActiveIntelligenceEvents";
import IngestionStatusCard from "./IngestionStatusCard";
import NotificationsStatusCard from "./NotificationsStatusCard";
import LandCoverDistributionCard from "./LandCoverDistributionCard";
import HighestRiskRegionCard from "./HighestRiskRegionCard";
import IntelligenceMap from "./IntelligenceMap";
import HistoricalIntelligenceSection from "./HistoricalIntelligenceSection";
import RegionalRiskSection from "./RegionalRiskSection";
import RegionalWeatherSection from "./RegionalWeatherSection";
import InvestigationsCommandCenterCard from "@/components/investigations/InvestigationsCommandCenterCard";

export default function IntelligenceSection() {
  const navigate = useNavigate();
  const [summary, setSummary] = useState(null);
  const [events, setEvents] = useState(null);
  const [ingestionStatus, setIngestionStatus] = useState(null);
  const [notificationsStatus, setNotificationsStatus] = useState(null);
  const [landCoverData, setLandCoverData] = useState(null);
  const [riskData, setRiskData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [summaryData, eventsData, ingestionData, notifData, lcData, riskResult] = await Promise.all([
        fetchIntelligenceSummary(),
        fetchIntelligenceEvents(),
        fetchIngestionStatus(),
        fetchNotificationsStatus(),
        fetchLandCoverDistribution(),
        fetchRegionalRisk(),
      ]);
      setSummary(summaryData);
      setEvents(eventsData);
      setIngestionStatus(ingestionData);
      setNotificationsStatus(notifData);
      setLandCoverData(lcData);
      setRiskData(riskResult);
    } catch (err) {
      const detail = err?.response?.data?.detail;
      setError(
        formatApiErrorDetail(detail) ||
          err.message ||
          "Failed to load intelligence data."
      );
      setSummary(null);
      setEvents(null);
      setIngestionStatus(null);
      setNotificationsStatus(null);
      setLandCoverData(null);
      setRiskData(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleCreateInvestigation = useCallback(
    (evt) => {
      const params = new URLSearchParams({
        intel_event_id: evt.id ?? "",
        region: evt.region ?? "",
        event_type: evt.event_type ?? "anomaly",
        severity: evt.severity ?? "medium",
        priority_score: String(evt.priority_score ?? 0),
      });
      navigate(`/investigations?${params.toString()}`);
    },
    [navigate]
  );

  return (
    <>
    <section className="mb-12" data-testid="intelligence-section">
      <div className="flex items-end justify-between gap-4 mb-6">
        <div>
          <div className="label-eyebrow flex items-center gap-1.5">
            <Brain className="w-3 h-3" strokeWidth={2} />
            Environmental Intelligence · Live
          </div>
          <h2 className="text-2xl font-semibold tracking-tight mt-1">
            Active anomaly intelligence
          </h2>
          <p className="text-sm text-[#7b827b] mt-1">
            Ranked by operational priority · updated each visit
          </p>
        </div>
        {error && (
          <button
            type="button"
            onClick={load}
            className="text-sm text-[#2d5a27] font-semibold hover:underline shrink-0"
            data-testid="intelligence-retry"
          >
            Retry
          </button>
        )}
      </div>

      {error && (
        <div
          className="mb-6 px-4 py-3 rounded-md border border-[#e76f51]/30 bg-[#e76f51]/5 text-sm text-[#9b2226]"
          data-testid="intelligence-error"
          role="alert"
        >
          {error}
        </div>
      )}

      {/* Summary stat cards */}
      <IntelligenceSummaryCards summary={summary} loading={loading && !summary} />

      {/* Highest-priority signal + active events table */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-5 mt-6">
        <div className="lg:col-span-1 flex flex-col gap-5">
          <TopIntelligenceSignalCard
            summary={summary}
            loading={loading && !summary}
          />
          <IngestionStatusCard
            status={ingestionStatus}
            loading={loading && !ingestionStatus}
          />
          <NotificationsStatusCard
            status={notificationsStatus}
            loading={loading && !notificationsStatus}
          />
          <LandCoverDistributionCard
            data={landCoverData}
            loading={loading && !landCoverData}
          />
          <HighestRiskRegionCard
            region={riskData?.regions?.[0] ?? null}
          />
          <InvestigationsCommandCenterCard loading={loading} />
        </div>
        <div className="lg:col-span-3">
          <ActiveIntelligenceEvents
            events={events?.active}
            loading={loading && !events}
            onCreateInvestigation={handleCreateInvestigation}
          />
        </div>
      </div>
    {/* Intelligence map */}
      <IntelligenceMap />
    </section>
    <RegionalRiskSection />
    <RegionalWeatherSection />
    <HistoricalIntelligenceSection />
  </>
  );
}
