/**
 * Organization monitoring posture — disturbance relevance and capabilities.
 */
import SurfaceCard from "@/components/product/SurfaceCard";
import EntitlementList from "@/components/product/EntitlementList";
import StatusBadge from "@/components/product/StatusBadge";
import UpgradePrompt from "@/components/billing/UpgradePrompt";

export default function CustomerMonitoringStatusCard({ status, loading }) {
  if (loading) {
    return (
      <SurfaceCard className="p-4 animate-pulse" testId="customer-monitoring-status-loading">
        <div className="h-4 bg-[var(--surface-inset)] rounded w-2/3 mb-3" />
        <div className="h-3 bg-[var(--surface-inset)] rounded w-full" />
      </SurfaceCard>
    );
  }

  if (!status) return null;

  const entitlements = status.entitlements ?? {};
  const inside = status.disturbance_summary?.inside_monitored_area_count ?? 0;
  const highCritical = status.disturbance_summary?.high_critical_investigation_count ?? 0;
  const authDefault = status.disturbance_summary?.authorization_status_default ?? "unknown";
  const monitoringOn = entitlements.monitoring_enabled !== false;

  return (
    <SurfaceCard className="p-4" testId="customer-monitoring-status-card">
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="fw-kicker">Monitoring posture</div>
        <StatusBadge
          variant={monitoringOn ? "operational" : "disabled"}
          label={monitoringOn ? "Active" : "Disabled"}
          testId="monitoring-enabled-badge"
        />
      </div>

      <dl className="space-y-2 text-sm mb-4">
        <div className="flex justify-between gap-4">
          <dt className="text-[var(--text-muted)]">Enabled AOIs</dt>
          <dd className="font-semibold tabular-nums" data-testid="monitoring-enabled-count">
            {status.monitored_areas?.enabled_count ?? 0}
          </dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-[var(--text-muted)]">Disturbances in AOI</dt>
          <dd className="font-semibold tabular-nums text-[var(--signal)]" data-testid="monitoring-inside-count">
            {inside}
          </dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-[var(--text-muted)]">High / critical</dt>
          <dd className="font-semibold tabular-nums text-[var(--signal-strong)]" data-testid="monitoring-high-count">
            {highCritical}
          </dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-[var(--text-muted)]">Authorization</dt>
          <dd className="font-medium text-xs" data-testid="monitoring-auth-status">
            {authDefault === "unknown"
              ? "Unknown — verification required"
              : String(authDefault).replace(/_/g, " ")}
          </dd>
        </div>
      </dl>

      <EntitlementList entitlements={entitlements} />

      {entitlements.live_sources_enabled === false && (
        <UpgradePrompt
          message="Live environmental sources are not included in your current plan."
          actionLabel="Upgrade for live environmental intelligence"
          testId="live-sources-upgrade"
          compact
        />
      )}

      <p className="text-xs text-[var(--text-muted)] mt-3 leading-relaxed border-t border-[var(--surface-inset)] pt-3">
        Potential Unauthorized Forest Activity requires verification — satellite
        disturbance alone does not establish illegality.
      </p>
    </SurfaceCard>
  );
}
