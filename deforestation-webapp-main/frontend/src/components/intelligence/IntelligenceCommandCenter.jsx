import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, AlertTriangle, Layers, Radio } from "lucide-react";
import SurfaceCard from "@/components/product/SurfaceCard";
import StatusBadge from "@/components/product/StatusBadge";
import EntitlementList from "@/components/product/EntitlementList";
import PriorityBadge from "@/components/product/PriorityBadge";
import DisturbanceInvestigationPanel from "./DisturbanceInvestigationPanel";
import AlertOperationsPanel from "@/components/alerts/AlertOperationsPanel";
import BillingCapabilityStrip from "@/components/billing/BillingCapabilityStrip";
import { sortEvidenceByPriority } from "@/design/semanticStates";

function Metric({ label, value, testId, accent }) {
  return (
    <div className="fw-metric" data-testid={testId}>
      <div className="fw-kicker">{label}</div>
      <div className={`fw-metric-value ${accent ?? ""}`.trim()}>{value}</div>
    </div>
  );
}

function EmptyQueueGuidance({ isDemo, areaCount, testId = "command-center-queue-empty", showAction = true }) {
  if (isDemo) {
    return (
      <div data-testid={testId}>
        <p className="text-sm text-[var(--text-muted)] leading-relaxed">
          No demonstration signals in the current scenario. Open another scenario or reset the demonstration.
        </p>
      </div>
    );
  }

  if (areaCount === 0) {
    return (
      <div data-testid={testId}>
        <p className="text-sm text-[var(--text-primary)] font-medium">
          No forests are being monitored yet.
        </p>
        <p className="text-sm text-[var(--text-muted)] mt-2 leading-relaxed">
          Add a monitored forest so ForestWatch can rank disturbances inside areas this organization cares about.
          An empty queue is expected until a forest is under watch.
        </p>
        {showAction && (
          <Link
            to="/trial/setup"
            className="inline-flex mt-3 fw-button-primary text-xs py-2 px-3"
            data-testid="command-center-add-forest"
          >
            Add a monitored forest
          </Link>
        )}
      </div>
    );
  }

  return (
    <div data-testid={testId}>
      <p className="text-sm text-[var(--text-primary)] font-medium">
        No disturbances currently require attention.
      </p>
      <p className="text-sm text-[var(--text-muted)] mt-2 leading-relaxed">
        ForestWatch is watching the forests you added. New signals appear here when a detection
        intersects a monitored area, with evidence and investigation priority.
        Empty is not a failure — it means nothing in your AOIs currently ranks for investigation.
      </p>
    </div>
  );
}

/**
 * Operational home — organization-aware priority queue for intelligence.
 */
export default function IntelligenceCommandCenter({
  monitoringStatus,
  commandCenter,
  events,
  operationalStatus,
  alertOverview,
  billingStatus,
  loading,
  onInvestigate,
  isDemo = false,
  focusedScenario = null,
  scenarios = [],
}) {
  const [selectedId, setSelectedId] = useState(null);

  const org = monitoringStatus?.organization ?? {};
  const entitlements = monitoringStatus?.entitlements ?? {};
  const disturbance = monitoringStatus?.disturbance_summary ?? {};
  const evidenceItems = commandCenter?.intelligence_evidence?.items ?? [];

  const priorityQueue = useMemo(() => {
    const disturbances = evidenceItems.filter(
      (item) => item.incident_category === "forest_disturbance"
    );
    const sorted = sortEvidenceByPriority(disturbances);
    const others = evidenceItems.filter(
      (item) => item.incident_category !== "forest_disturbance"
    );
    return [...sorted, ...others];
  }, [evidenceItems]);

  const selectedItem =
    priorityQueue.find((item) => item.event_id === selectedId) ??
    priorityQueue[0] ??
    null;

  useEffect(() => {
    if (!focusedScenario || !priorityQueue.length) return;
    const scenario = scenarios.find((item) => item.id === focusedScenario);
    const region = scenario?.region;
    if (!region) return;
    const match = priorityQueue.find((item) => item.region === region);
    if (match) setSelectedId(match.event_id);
  }, [focusedScenario, priorityQueue, scenarios]);

  const activeCount = events?.active?.length ?? 0;
  const highPriority = disturbance.high_critical_investigation_count ?? 0;
  const areaCount =
    entitlements.monitored_area_count ??
    monitoringStatus?.monitored_areas?.enabled_count ??
    0;
  const areaLimit = entitlements.monitored_area_limit;
  const degradedCount = (commandCenter?.degraded_sources ?? []).length;
  const monitoringOperational =
    entitlements.monitoring_enabled !== false && degradedCount === 0;

  if (loading && !monitoringStatus) {
    return (
      <SurfaceCard className="p-6 animate-pulse" testId="command-center-loading">
        <div className="h-6 bg-[var(--surface-inset)] rounded w-1/3 mb-4" />
        <div className="h-24 bg-[var(--surface-inset)] rounded" />
      </SurfaceCard>
    );
  }

  return (
    <SurfaceCard variant="emphasis" className="p-0 overflow-hidden" testId="intelligence-command-center">
      <div className="px-6 py-5 border-b border-[var(--surface-inset)] bg-[var(--surface-subtle)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="fw-kicker mb-1">{isDemo ? "ForestWatch Demo" : "Command Center"}</div>
            <h2 className="text-xl font-bold tracking-tight text-[var(--text-primary)]" data-testid="command-center-org-name">
              {org.name ?? "Organization"}
            </h2>
            {org.role && (
              <p className="text-xs text-[var(--text-muted)] capitalize mt-0.5" data-testid="command-center-org-role">
                {org.role}
              </p>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <StatusBadge
              variant={monitoringOperational ? "operational" : "degraded"}
              label={monitoringOperational ? "Monitoring operational" : "Monitoring degraded"}
              testId="command-center-monitoring-state"
            />
            {degradedCount > 0 && (
              <StatusBadge
                variant="degraded"
                label={`${degradedCount} source${degradedCount === 1 ? "" : "s"} degraded`}
                testId="command-center-degraded-sources"
              />
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-5">
          <Metric
            label={isDemo ? "Monitored forests" : "Monitored areas"}
            value={areaLimit != null && !isDemo ? `${areaCount} / ${areaLimit}` : areaCount}
            testId="command-center-area-metric"
          />
          <Metric
            label={isDemo ? "Active intelligence events" : "Active intelligence"}
            value={activeCount}
            testId="command-center-events-metric"
          />
          <Metric
            label={isDemo ? "High priority" : "High-priority investigations"}
            value={highPriority}
            testId="command-center-high-metric"
            accent={highPriority > 0 ? "text-[var(--signal-strong)]" : ""}
          />
          <Metric
            label={isDemo ? "Requires investigation" : "In monitored AOIs"}
            value={
              isDemo
                ? highPriority
                : disturbance.inside_monitored_area_count ?? 0
            }
            testId="command-center-inside-metric"
            accent={
              (isDemo ? highPriority : disturbance.inside_monitored_area_count ?? 0) > 0
                ? "text-[var(--signal)]"
                : ""
            }
          />
        </div>
      </div>

      {!isDemo && <BillingCapabilityStrip status={billingStatus} />}

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-0 xl:divide-x divide-[var(--surface-inset)]">
        <div className="xl:col-span-2 p-5">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle className="w-4 h-4 text-[var(--signal)]" strokeWidth={1.8} />
            <h3 className="text-sm font-semibold">Requires attention</h3>
          </div>

          {priorityQueue.length === 0 ? (
            <EmptyQueueGuidance isDemo={isDemo} areaCount={areaCount} />
          ) : (
            <ul className="space-y-2 max-h-[420px] overflow-y-auto" data-testid="command-center-priority-queue">
              {priorityQueue.slice(0, 12).map((item) => {
                const isDisturbance = item.incident_category === "forest_disturbance";
                const d = item.disturbance_assessment ?? {};
                const active = selectedItem?.event_id === item.event_id;
                return (
                  <li key={item.event_id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(item.event_id)}
                      className={`w-full text-left p-3 rounded-md border transition-colors ${
                        active
                          ? "border-[var(--accent)] bg-[var(--surface-subtle)]"
                          : "border-[var(--surface-inset)] hover:bg-[var(--surface-subtle)]/60"
                      }`}
                      data-testid={`command-center-queue-${item.event_id}`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <div className="text-xs uppercase tracking-wide text-[var(--text-muted)]">
                            {isDisturbance ? "Forest disturbance" : item.incident_category ?? "Intelligence"}
                          </div>
                          <div className="text-sm font-semibold truncate mt-0.5">
                            {item.region ?? item.event_id}
                          </div>
                          {item.monitored_area?.name && (
                            <div className="text-xs text-[var(--text-muted)] mt-1 flex items-center gap-1">
                              <Layers className="w-3 h-3" />
                              {item.monitored_area.name}
                            </div>
                          )}
                        </div>
                        {isDisturbance && d.investigation_priority && (
                          <PriorityBadge priority={d.investigation_priority} />
                        )}
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}

          {!isDemo && (
          <div className="mt-5 pt-4 border-t border-[var(--surface-inset)]">
            <div className="flex items-center gap-2 mb-2">
              <Radio className="w-3.5 h-3.5 text-[var(--text-muted)]" />
              <span className="fw-kicker">Organization capabilities</span>
            </div>
            <EntitlementList entitlements={entitlements} compact={false} />
          </div>
          )}

          {alertOverview && (
            <div className="mt-5 pt-4 border-t border-[var(--surface-inset)]">
              <AlertOperationsPanel overview={alertOverview} simulated={isDemo} />
            </div>
          )}
        </div>

        <div className="xl:col-span-3 p-5 bg-[var(--surface-subtle)]/40">
          {selectedItem?.incident_category === "forest_disturbance" ? (
            <DisturbanceInvestigationPanel
              item={selectedItem}
              isDemo={isDemo}
              onInvestigate={
                onInvestigate
                  ? () => onInvestigate({ id: selectedItem.event_id, region: selectedItem.region })
                  : undefined
              }
            />
          ) : selectedItem ? (
            <SurfaceCard variant="inset" className="p-5" testId="command-center-generic-detail">
              <div className="fw-kicker mb-2">{selectedItem.incident_category ?? "Intelligence"}</div>
              <h3 className="text-lg font-bold">{selectedItem.region ?? selectedItem.event_id}</h3>
              <p className="text-sm text-[var(--text-muted)] mt-2 flex items-center gap-1.5">
                <Activity className="w-4 h-4" />
                Review on map or in the active events table for full context.
              </p>
            </SurfaceCard>
          ) : (
            <SurfaceCard variant="inset" className="p-5 h-full min-h-[280px]" testId="command-center-detail-empty">
              <div className="fw-kicker mb-2">What to do next</div>
              <EmptyQueueGuidance
                isDemo={isDemo}
                areaCount={areaCount}
                testId="command-center-detail-guidance"
                showAction={false}
              />
            </SurfaceCard>
          )}
        </div>
      </div>
    </SurfaceCard>
  );
}
