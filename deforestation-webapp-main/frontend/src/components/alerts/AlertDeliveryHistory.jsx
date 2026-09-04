import { Layers } from "lucide-react";
import SurfaceCard from "@/components/product/SurfaceCard";
import StatusBadge from "@/components/product/StatusBadge";
import PriorityBadge from "@/components/product/PriorityBadge";
import {
  alertStageLabel,
  deliveryPresentationLabel,
  deliveryStateVariant,
  channelOutcomeSummary,
  formatTimestamp,
  isSimulatedDelivery,
} from "@/design/semanticStates";

const FILTERS = [
  { value: "", label: "All" },
  { value: "pending", label: "Queued" },
  { value: "sent", label: "Delivered" },
  { value: "failed", label: "Failed" },
  { value: "suppressed", label: "Suppressed" },
];

/**
 * Answers "what alerts has my organization actually received, or tried to?"
 * Only states the backend reports are rendered — nothing is inferred.
 */
export default function AlertDeliveryHistory({
  deliveries = [],
  loading = false,
  activeFilter = "",
  onFilterChange,
}) {
  return (
    <SurfaceCard className="p-5" testId="alert-delivery-history">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <h3 className="text-base font-bold text-[var(--text-primary)]">Alert history</h3>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Every alert this organization received or attempted to receive.
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5" data-testid="alert-history-filters">
          {FILTERS.map((filter) => (
            <button
              key={filter.value || "all"}
              type="button"
              aria-pressed={activeFilter === filter.value}
              data-testid={`alert-history-filter-${filter.value || "all"}`}
              onClick={() => onFilterChange?.(filter.value)}
              className={`rounded-md border px-2.5 py-1 text-xs transition-colors ${
                activeFilter === filter.value
                  ? "border-[var(--accent)] bg-[var(--surface-subtle)] font-semibold"
                  : "border-[var(--surface-inset)] text-[var(--text-muted)]"
              }`}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div
          className="h-20 rounded-md bg-[var(--surface-inset)] animate-pulse"
          data-testid="alert-history-loading"
        />
      ) : deliveries.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]" data-testid="alert-history-empty">
          No alerts have been generated for this organization yet.
        </p>
      ) : (
        <ul className="space-y-3">
          {deliveries.map((delivery) => (
            <li
              key={delivery.id}
              className="p-4 border border-[var(--surface-inset)] rounded-md"
              data-testid={`alert-delivery-${delivery.id}`}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="fw-kicker">
                    {delivery.incident_category_label ?? "Forest intelligence"}
                  </div>
                  <h4 className="text-sm font-semibold text-[var(--text-primary)] mt-0.5">
                    {alertStageLabel(delivery.alert_stage)}
                    {delivery.policy_name ? ` · ${delivery.policy_name}` : ""}
                  </h4>
                  {delivery.monitored_area_names?.length > 0 && (
                    <div
                      className="text-xs text-[var(--text-muted)] mt-1 flex items-center gap-1"
                      data-testid={`alert-delivery-${delivery.id}-area`}
                    >
                      <Layers className="w-3 h-3" />
                      {delivery.monitored_area_names.join(", ")}
                    </div>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <PriorityBadge
                    priority={delivery.priority}
                    testId={`alert-delivery-${delivery.id}-priority`}
                  />
                  <StatusBadge
                    variant={
                      isSimulatedDelivery(delivery)
                        ? "unknown"
                        : deliveryStateVariant(delivery.lifecycle)
                    }
                    label={deliveryPresentationLabel(delivery)}
                    testId={`alert-delivery-${delivery.id}-state`}
                  />
                </div>
              </div>

              <dl className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-4">
                <div>
                  <dt className="fw-kicker">Generated</dt>
                  <dd className="text-sm text-[var(--text-primary)] mt-0.5">
                    {formatTimestamp(delivery.created_at)}
                  </dd>
                </div>
                <div>
                  <dt className="fw-kicker">Delivered</dt>
                  <dd
                    className="text-sm text-[var(--text-primary)] mt-0.5"
                    data-testid={`alert-delivery-${delivery.id}-sent-at`}
                  >
                    {delivery.sent_at ? formatTimestamp(delivery.sent_at) : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="fw-kicker">Channels</dt>
                  <dd
                    className="text-sm text-[var(--text-primary)] mt-0.5"
                    data-testid={`alert-delivery-${delivery.id}-channels`}
                  >
                    {delivery.channel_outcomes?.length
                      ? delivery.channel_outcomes.map(channelOutcomeSummary).join(", ")
                      : "—"}
                  </dd>
                </div>
              </dl>

              {isSimulatedDelivery(delivery) && (
                <p
                  className="text-xs text-[var(--text-muted)] mt-3"
                  data-testid={`alert-delivery-${delivery.id}-simulated-note`}
                >
                  No external message was sent.
                </p>
              )}

              {delivery.suppression_reason_label && (
                <p
                  className="text-xs text-[var(--text-muted)] mt-3"
                  data-testid={`alert-delivery-${delivery.id}-suppression`}
                >
                  {delivery.suppression_reason_label}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </SurfaceCard>
  );
}
