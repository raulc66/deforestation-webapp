import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  fetchIntelligenceEvents,
  fetchIntelligenceSummary,
  fetchIngestionStatus,
  fetchNotificationsStatus,
  fetchLandCoverDistribution,
  fetchRegionalRisk,
  fetchCommandCenter,
  fetchOperationalStatus,
} from "@/api/analytics";
import { fetchMonitoringAreas, fetchMonitoringStatus } from "@/api/monitoringAreas";
import { fetchAlertOverview } from "@/api/customerAlerts";
import { fetchBillingStatus } from "@/api/billing";
import { useOrganization } from "@/context/OrganizationContext";
import { useDemo } from "@/context/DemoContext";
import { useTrial } from "@/context/TrialContext";
import { isDemoOrganization } from "@/lib/demo";
import TrialConversionCta from "@/components/trial/TrialConversionCta";
import MonitoredAreasCard from "./MonitoredAreasCard";
import CustomerMonitoringStatusCard from "./CustomerMonitoringStatusCard";
import InvestigationsCommandCenterCard from "@/components/investigations/InvestigationsCommandCenterCard";
import { formatApiErrorDetail } from "@/lib/api";
import IntelligenceSummaryCards from "./IntelligenceSummaryCards";
import ActiveIntelligenceEvents from "./ActiveIntelligenceEvents";
import IngestionStatusCard from "./IngestionStatusCard";
import NotificationsStatusCard from "./NotificationsStatusCard";
import LandCoverDistributionCard from "./LandCoverDistributionCard";
import IntelligenceMap from "./IntelligenceMap";
import HistoricalIntelligenceSection from "./HistoricalIntelligenceSection";
import RegionalRiskSection from "./RegionalRiskSection";
import RegionalWeatherSection from "./RegionalWeatherSection";
import OperationalStatusCard from "./OperationalStatusCard";
import IntelligenceCommandCenter from "./IntelligenceCommandCenter";

export default function IntelligenceSection() {
  const navigate = useNavigate();
  const {
    selectedOrgId,
    organizationVersion,
    currentOrganization,
    loading: orgLoading,
  } = useOrganization();
  const demo = useDemo();
  const trial = useTrial();
  const sessionIsDemo = demo.isDemo;
  const isDemo = sessionIsDemo || isDemoOrganization(currentOrganization);
  const orgReady =
    Boolean(selectedOrgId) &&
    !orgLoading &&
    (!isDemoOrganization(currentOrganization) || sessionIsDemo);
  const [summary, setSummary] = useState(null);
  const [events, setEvents] = useState(null);
  const [ingestionStatus, setIngestionStatus] = useState(null);
  const [notificationsStatus, setNotificationsStatus] = useState(null);
  const [landCoverData, setLandCoverData] = useState(null);
  const [riskData, setRiskData] = useState(null);
  const [commandCenter, setCommandCenter] = useState(null);
  const [operationalStatus, setOperationalStatus] = useState(null);
  const [monitoringAreas, setMonitoringAreas] = useState(null);
  const [monitoringStatus, setMonitoringStatus] = useState(null);
  const [alertOverview, setAlertOverview] = useState(null);
  const [billingStatus, setBillingStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        summaryData,
        eventsData,
        ingestionData,
        notifData,
        lcData,
        riskResult,
        ccData,
        opStatus,
        areasData,
        monStatus,
        alertData,
        billingData,
      ] = await Promise.all([
        fetchIntelligenceSummary(),
        fetchIntelligenceEvents(),
        isDemo ? Promise.resolve(null) : fetchIngestionStatus(),
        isDemo ? Promise.resolve(null) : fetchNotificationsStatus(),
        isDemo ? Promise.resolve(null) : fetchLandCoverDistribution(),
        isDemo ? Promise.resolve(null) : fetchRegionalRisk(),
        fetchCommandCenter(),
        fetchOperationalStatus(),
        fetchMonitoringAreas().catch(() => ({ items: [], total: 0 })),
        fetchMonitoringStatus().catch(() => null),
        fetchAlertOverview().catch(() => null),
        isDemo ? Promise.resolve(null) : fetchBillingStatus().catch(() => null),
      ]);
      setSummary(summaryData);
      setEvents(eventsData);
      setIngestionStatus(ingestionData);
      setNotificationsStatus(notifData);
      setLandCoverData(lcData);
      setRiskData(riskResult);
      setCommandCenter(ccData);
      setOperationalStatus(opStatus);
      setMonitoringAreas(areasData);
      setMonitoringStatus(monStatus);
      setAlertOverview(alertData);
      setBillingStatus(billingData);
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
      setCommandCenter(null);
      setOperationalStatus(null);
      setMonitoringAreas(null);
      setMonitoringStatus(null);
      setAlertOverview(null);
      setBillingStatus(null);
    } finally {
      setLoading(false);
    }
  }, [isDemo]);

  useEffect(() => {
    if (!orgReady) {
      setLoading(false);
      setError(null);
      return;
    }
    load();
  }, [load, orgReady, organizationVersion, demo.status?.reset_count, demo.lastSimulation?.id]);

  const handleCreateInvestigation = useCallback(
    async (evt) => {
      if (isDemo) {
        const eventId = evt?.id ?? evt?.event_id;
        const result = await demo.investigate(eventId);
        if (result?.ok) {
          demo.setGuideStep("evidence");
        }
        return;
      }
      const params = new URLSearchParams({
        intel_event_id: evt.id ?? "",
        region: evt.region ?? "",
        event_type: evt.event_type ?? "anomaly",
        severity: evt.severity ?? "medium",
        priority_score: String(evt.priority_score ?? 0),
      });
      navigate(`/investigations?${params.toString()}`);
    },
    [navigate, isDemo, demo]
  );

  const evidenceByEventId = Object.fromEntries(
    (commandCenter?.intelligence_evidence?.items ?? []).map((item) => [item.event_id, item])
  );

  return (
    <>
      <section className="mb-12" data-testid="intelligence-section">
        <div className="flex items-end justify-between gap-4 mb-6">
          <div>
            <div className="fw-kicker">Environmental intelligence</div>
            <h2 className="text-2xl font-semibold tracking-tight mt-1 text-[var(--text-primary)]">
              Operational command
            </h2>
            <p className="text-sm text-[var(--text-muted)] mt-1">
              Monitor · detect · evaluate evidence · prioritize investigation
            </p>
          </div>
          {error && (
            <button
              type="button"
              onClick={load}
              className="text-sm text-[var(--accent-strong)] font-semibold hover:underline shrink-0"
              data-testid="intelligence-retry"
            >
              Retry
            </button>
          )}
        </div>

        {error && (
          <div
            className="mb-6 px-4 py-3 rounded-md border border-[var(--signal)]/30 bg-[var(--signal)]/5 text-sm text-[var(--signal-strong)]"
            data-testid="intelligence-error"
            role="alert"
          >
            {error}
          </div>
        )}

        <div className="mb-6">
          <IntelligenceCommandCenter
            monitoringStatus={monitoringStatus}
            commandCenter={commandCenter}
            events={events}
            operationalStatus={operationalStatus}
            alertOverview={alertOverview}
            billingStatus={isDemo ? null : billingStatus}
            loading={loading}
            onInvestigate={handleCreateInvestigation}
            isDemo={isDemo}
            focusedScenario={demo.status?.focused_scenario}
            scenarios={demo.status?.scenarios}
            openedInvestigationEventId={demo.openedInvestigationEventId}
          />
        </div>

        <IntelligenceSummaryCards summary={summary} loading={loading && !summary} />

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-5 mt-6">
          <div className="lg:col-span-1 flex flex-col gap-5">
            <OperationalStatusCard status={operationalStatus} loading={loading && !operationalStatus} />
            <CustomerMonitoringStatusCard status={monitoringStatus} loading={loading && !monitoringStatus} />
            <MonitoredAreasCard
              areas={monitoringAreas}
              entitlements={monitoringStatus?.entitlements}
              loading={loading && !monitoringAreas}
            />
            {trial.isTrial && trial.status?.upgrade_cta?.moment === "area_limit" && (
              <TrialConversionCta moment="area_limit" />
            )}
            {trial.isExpired && <TrialConversionCta moment="expired" />}
            {!isDemo && (
              <IngestionStatusCard status={ingestionStatus} loading={loading && !ingestionStatus} />
            )}
            {!isDemo && <InvestigationsCommandCenterCard loading={loading} />}
            {!isDemo && (
              <details className="fw-surface p-4 text-sm">
                <summary className="fw-kicker cursor-pointer select-none">Additional context</summary>
                <div className="mt-4 space-y-4">
                  <NotificationsStatusCard status={notificationsStatus} loading={loading && !notificationsStatus} />
                  <LandCoverDistributionCard data={landCoverData} loading={loading && !landCoverData} />
                </div>
              </details>
            )}
          </div>
          <div className="lg:col-span-3">
            <ActiveIntelligenceEvents
              events={events?.active}
              loading={loading && !events}
              onCreateInvestigation={handleCreateInvestigation}
              evidenceByEventId={evidenceByEventId}
            />
          </div>
        </div>

        {orgReady && (
          <IntelligenceMap
            evidenceByEventId={evidenceByEventId}
            organizationName={monitoringStatus?.organization?.name}
            demoMode={isDemo}
            catalogEpoch={demo.status?.reset_count ?? 0}
          />
        )}
      </section>
      {!isDemo && orgReady && <RegionalRiskSection />}
      {!isDemo && orgReady && <RegionalWeatherSection />}
      {!isDemo && orgReady && <HistoricalIntelligenceSection />}
    </>
  );
}
