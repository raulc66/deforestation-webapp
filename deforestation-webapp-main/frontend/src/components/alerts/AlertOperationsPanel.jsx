import { Link } from "react-router-dom";
import { BellRing } from "lucide-react";
import SurfaceCard from "@/components/product/SurfaceCard";
import StatusBadge from "@/components/product/StatusBadge";
import {
  alertStageLabel,
  deliveryStateLabel,
  deliveryStateVariant,
  formatTimestamp,
} from "@/design/semanticStates";

const MAX_RECENT = 3;

/**
 * Compact alert operations surface for the Command Center.
 *
 * Alerts are an operational consequence of intelligence, so this stays a
 * summary: counts, channel readiness, and the few most recent deliveries.
 */
export default function AlertOperationsPanel({ overview, loading = false, simulated = false }) {
  if (loading && !overview) {
    return (
      <SurfaceCard
        variant="inset"
        className="p-4 animate-pulse"
        testId="alert-operations-loading"
      >
        <div className="h-4 w-1/3 bg-[var(--surface-inset)] rounded mb-3" />
        <div className="h-12 bg-[var(--surface-inset)] rounded" />
      </SurfaceCard>
    );
  }

  if (!overview) return null;

  const recent = (overview.recent_deliveries ?? []).slice(0, MAX_RECENT);
  const available = overview.alert_delivery_available !== false;
  const attention = overview.attention_count ?? 0;
  const channelsReady =
    (overview.enabled_channel_count ?? 0) > 0 && (overview.active_policy_count ?? 0) > 0;

  return (
    <SurfaceCard variant="inset" className="p-4" testId="alert-operations-panel">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2">
          <BellRing className="w-3.5 h-3.5 text-[var(--text-muted)]" strokeWidth={1.8} />
          <span className="fw-kicker">Alert operations</span>
        </div>
        <StatusBadge
          variant={available ? (channelsReady ? "operational" : "degraded") : "not-enabled"}
          label={
            available
              ? channelsReady
                ? "Delivery ready"
                : "Needs configuration"
              : "Not available"
          }
          testId="alert-operations-state"
        />
      </div>

      <div className="grid grid-cols-3 gap-3 mb-3">
        <div data-testid="alert-operations-attention">
          <div className="fw-kicker">Needs attention</div>
          <div
            className={`fw-metric-value ${attention > 0 ? "text-[var(--signal-strong)]" : ""}`}
          >
            {attention}
          </div>
        </div>
        <div data-testid="alert-operations-delivered">
          <div className="fw-kicker">Delivered</div>
          <div className="fw-metric-value">{overview.sent_count ?? 0}</div>
        </div>
        <div data-testid="alert-operations-policies">
          <div className="fw-kicker">Active policies</div>
          <div className="fw-metric-value">{overview.active_policy_count ?? 0}</div>
        </div>
      </div>

      {recent.length === 0 ? (
        <p className="text-xs text-[var(--text-muted)]" data-testid="alert-operations-empty">
          No alerts delivered yet for this organization.
        </p>
      ) : (
        <ul className="space-y-1.5" data-testid="alert-operations-recent">
          {recent.map((delivery) => (
            <li
              key={delivery.id}
              className="flex items-center justify-between gap-2 text-xs"
              data-testid={`alert-operations-delivery-${delivery.id}`}
            >
              <span className="min-w-0 truncate text-[var(--text-primary)]">
                {alertStageLabel(delivery.alert_stage)}
                {delivery.monitored_area_names?.length
                  ? ` · ${delivery.monitored_area_names[0]}`
                  : ""}
              </span>
              <span className="flex items-center gap-2 shrink-0">
                <span className="text-[var(--text-muted)]">
                  {formatTimestamp(delivery.sent_at ?? delivery.created_at)}
                </span>
                <StatusBadge
                  variant={deliveryStateVariant(delivery.lifecycle)}
                  label={
                    simulated || delivery.simulated || delivery.delivery_results?.some((row) => row.simulated)
                      ? "Simulated"
                      : delivery.delivery_state_label ?? deliveryStateLabel(delivery.lifecycle)
                  }
                />
              </span>
            </li>
          ))}
        </ul>
      )}

      {(overview.channel_states ?? []).some((state) => !state.enabled || !state.configured) && (
        <p className="text-xs text-[var(--text-muted)] mt-3" data-testid="alert-operations-channel-warning">
          One or more notification channels are paused or incomplete.
        </p>
      )}

      <Link
        to="/alerts"
        className="inline-block mt-3 text-xs font-semibold text-[var(--accent)] hover:underline"
        data-testid="alert-operations-manage-link"
      >
        Manage alerts
      </Link>
      {simulated && (
        <p className="text-xs text-[var(--text-muted)] mt-2" data-testid="alert-operations-simulated-note">
          Demonstration deliveries are simulated. No email is sent.
        </p>
      )}
    </SurfaceCard>
  );
}
