import SurfaceCard from "@/components/product/SurfaceCard";
import StatusBadge from "@/components/product/StatusBadge";
import { SYSTEM_LABELS } from "@/design/semanticStates";

export default function OperationalStatusCard({ status, loading }) {
  if (loading && !status) {
    return (
      <SurfaceCard className="p-4 animate-pulse" testId="operational-status-loading">
        <div className="h-3 bg-[var(--surface-inset)] rounded w-1/2 mb-3" />
        <div className="h-2 bg-[var(--surface-inset)] rounded w-full mb-2" />
        <div className="h-2 bg-[var(--surface-inset)] rounded w-3/4" />
      </SurfaceCard>
    );
  }
  if (!status) return null;

  const providers = status.providers ?? [];
  const cycle = status.intelligence_cycle ?? {};
  const correlation = status.correlation ?? {};
  const degraded = providers.filter((p) =>
    ["degraded", "failed"].includes(String(p.current_status).toLowerCase())
  );
  const systemVariant =
    degraded.length > 0 ? "degraded" : "operational";

  return (
    <SurfaceCard className="p-4" testId="operational-status-card">
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="fw-kicker">System status</div>
        <StatusBadge
          variant={systemVariant}
          label={SYSTEM_LABELS[systemVariant] ?? systemVariant}
          testId="operational-system-badge"
        />
      </div>

      <div className="text-sm space-y-2 text-[var(--text-secondary)]">
        <div>
          <span className="font-semibold text-[var(--text-primary)]">Scope:</span>{" "}
          {status.geographic_scope}
        </div>
        <div>
          <span className="font-semibold text-[var(--text-primary)]">Cycle:</span>{" "}
          {cycle.intelligence_cycle_id ?? "unavailable"}
        </div>
        <div>
          <span className="font-semibold text-[var(--text-primary)]">Correlation:</span>{" "}
          {correlation.state ?? "unavailable"}
        </div>
        <div className="space-y-1 pt-1">
          {providers.slice(0, 5).map((provider) => {
            const st = String(provider.current_status || "").toLowerCase();
            const variant =
              st === "failed" ? "failed" : st === "degraded" ? "degraded" : "operational";
            return (
              <div
                key={provider.provider_id}
                className="flex items-center justify-between gap-2 text-xs"
                data-testid={`provider-${provider.provider_id}`}
              >
                <span>{provider.display_name}</span>
                <StatusBadge variant={variant} label={provider.current_status} />
              </div>
            );
          })}
        </div>
        {(status.regions ?? []).length > 0 && (
          <div className="text-xs" data-testid="operational-regions">
            Regions: {(status.regions ?? []).map((r) => r.country).join(", ")}
          </div>
        )}
      </div>
    </SurfaceCard>
  );
}
