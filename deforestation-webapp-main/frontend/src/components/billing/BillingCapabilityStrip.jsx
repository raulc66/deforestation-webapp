import { Link } from "react-router-dom";
import StatusBadge from "@/components/product/StatusBadge";
import {
  featureAvailabilityLabel,
  monitoringCapacityLabel,
} from "@/design/semanticStates";

/**
 * Compact commercial indication inside the Command Center.
 *
 * Deliberately a single subordinate row: the intelligence hierarchy stays
 * primary and billing never becomes a dashboard of its own.
 */
export default function BillingCapabilityStrip({ status }) {
  if (!status) return null;

  const plan = status.plan ?? {};
  const capacity = status.capacity ?? {};
  const entitlements = status.entitlements ?? {};
  const upgrade = status.upgrade ?? {};
  const alertsEnabled = entitlements.alert_delivery_enabled === true;

  return (
    <div
      className="flex flex-wrap items-center gap-x-5 gap-y-2 px-6 py-3 border-t border-[var(--surface-inset)] bg-[var(--surface-subtle)]"
      data-testid="billing-capability-strip"
    >
      <div>
        <div className="fw-kicker">Plan</div>
        <div className="text-sm font-semibold text-[var(--text-primary)]" data-testid="strip-plan-name">
          {plan.display_name ?? "Foundation"}
        </div>
      </div>
      <div>
        <div className="fw-kicker">Monitoring capacity</div>
        <div className="text-sm text-[var(--text-primary)]" data-testid="strip-capacity">
          {monitoringCapacityLabel(
            capacity.monitored_area_count,
            capacity.monitored_area_limit
          )}
        </div>
      </div>
      <div>
        <div className="fw-kicker">Alerts</div>
        <StatusBadge
          variant={alertsEnabled ? "enabled" : "not-enabled"}
          label={featureAvailabilityLabel(alertsEnabled, {
            includedLabel: "Enabled",
            excludedLabel: "Not in plan",
          })}
          testId="strip-alert-capability"
        />
      </div>
      {(upgrade.recommended || upgrade.payment_attention_required) && (
        <Link
          to="/billing"
          className="ml-auto text-sm font-semibold text-[var(--accent-strong)] hover:underline"
          data-testid="strip-billing-link"
        >
          {upgrade.payment_attention_required
            ? "Payment needs attention"
            : "Increase monitoring capability"}
        </Link>
      )}
    </div>
  );
}
