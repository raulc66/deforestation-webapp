/**
 * Organization-owned monitored forest portfolio.
 */
import SurfaceCard from "@/components/product/SurfaceCard";
import MonitoredAreaAssetCard from "./MonitoredAreaAssetCard";
import StatusBadge from "@/components/product/StatusBadge";
import UpgradePrompt from "@/components/billing/UpgradePrompt";
import { entitlementAreaLabel, monitoringCapacityLabel } from "@/design/semanticStates";

export default function MonitoredAreasCard({ areas, entitlements, loading }) {
  const items = areas?.items ?? [];
  const total = areas?.total ?? items.length;
  const limit = entitlements?.monitored_area_limit;
  const count = entitlements?.monitored_area_count ?? total;
  const limitHint = entitlementAreaLabel(count, limit);

  if (loading) {
    return (
      <SurfaceCard className="p-4 animate-pulse" testId="monitored-areas-loading">
        <div className="h-4 bg-[var(--surface-inset)] rounded w-1/2 mb-3" />
        <div className="h-3 bg-[var(--surface-inset)] rounded w-full" />
      </SurfaceCard>
    );
  }

  return (
    <SurfaceCard className="p-4" testId="monitored-areas-card">
      <div className="flex items-start justify-between gap-2 mb-3">
        <div>
          <div className="fw-kicker mb-1">Monitored forests</div>
          <div className="text-2xl font-bold tabular-nums text-[var(--accent-strong)]" data-testid="monitored-areas-count">
            {total}
          </div>
        </div>
        {limit != null && (
          <StatusBadge
            variant={limitHint === "Limit reached" ? "failed" : limitHint === "Approaching limit" ? "degraded" : "enabled"}
            label={limitHint ?? `${count} / ${limit}`}
            testId="monitored-areas-limit"
          />
        )}
      </div>

      <p className="text-xs text-[var(--text-muted)] mb-3">
        Organization forest assets · operational monitoring coverage
      </p>

      {items.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]" data-testid="monitored-areas-empty">
          No monitored areas configured yet.
        </p>
      ) : (
        <div className="space-y-2" data-testid="monitored-areas-list">
          {items.slice(0, 5).map((area) => (
            <MonitoredAreaAssetCard key={area.id} area={area} />
          ))}
        </div>
      )}

      {limit != null && count >= limit && (
        <UpgradePrompt
          message={`${monitoringCapacityLabel(count, limit)}.`}
          actionLabel="Upgrade to monitor additional forests"
          testId="monitored-areas-upgrade"
          compact
        />
      )}
    </SurfaceCard>
  );
}
