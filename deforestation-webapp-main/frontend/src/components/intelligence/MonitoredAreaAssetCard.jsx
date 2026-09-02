import { MapPin } from "lucide-react";
import SurfaceCard from "@/components/product/SurfaceCard";
import StatusBadge from "@/components/product/StatusBadge";

/**
 * Organization-owned monitored forest asset — bounded fields only.
 */
export default function MonitoredAreaAssetCard({ area }) {
  if (!area) return null;

  const summary = area.intelligence_summary ?? {};
  const intelligenceCount = summary.active_intelligence_count ?? 0;
  const highPriorityCount = summary.high_priority_count ?? 0;
  const areaHa = area.area_hectares;

  return (
    <SurfaceCard variant="inset" className="p-4" testId={`monitored-area-asset-${area.id}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="text-sm font-bold text-[var(--text-primary)] truncate">{area.name}</h4>
          <p className="text-xs text-[var(--text-muted)] mt-0.5 flex items-center gap-1">
            <MapPin className="w-3 h-3 shrink-0" />
            {area.country ?? "—"}
            {area.geometry_type ? ` · ${area.geometry_type}` : ""}
            {areaHa != null ? ` · ${areaHa} ha` : ""}
          </p>
        </div>
        <StatusBadge variant="operational" label="Monitoring" testId={`area-status-${area.id}`} />
      </div>

      <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div>
          <dt className="fw-kicker">Active intelligence</dt>
          <dd className="font-mono font-semibold tabular-nums">{intelligenceCount}</dd>
        </div>
        <div>
          <dt className="fw-kicker">High priority</dt>
          <dd className="font-mono font-semibold tabular-nums text-[var(--signal-strong)]">
            {highPriorityCount}
          </dd>
        </div>
      </dl>
    </SurfaceCard>
  );
}
