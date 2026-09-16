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
    <SurfaceCard variant="inset" className="p-4 min-w-0" testId={`monitored-area-asset-${area.id}`}>
      <div className="space-y-2">
        <h4
          className="text-sm font-bold text-[var(--text-primary)] fw-name"
          data-testid={`monitored-area-name-${area.id}`}
        >
          {area.name}
        </h4>
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <p className="text-xs text-[var(--text-muted)] min-w-0 flex-1 basis-[8rem] fw-name">
            <span className="inline-flex items-start gap-1">
              <MapPin className="w-3 h-3 shrink-0 mt-0.5" />
              <span>
                {area.country ?? "—"}
                {area.geometry_type ? ` · ${area.geometry_type}` : ""}
                {areaHa != null ? ` · ${areaHa} ha` : ""}
              </span>
            </span>
          </p>
          <StatusBadge variant="operational" label="Monitoring" testId={`area-status-${area.id}`} />
        </div>
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
