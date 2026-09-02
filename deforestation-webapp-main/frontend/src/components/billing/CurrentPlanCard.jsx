import { CreditCard, ExternalLink } from "lucide-react";
import SurfaceCard from "@/components/product/SurfaceCard";
import StatusBadge from "@/components/product/StatusBadge";
import EntitlementList from "@/components/product/EntitlementList";
import { Button } from "@/components/ui/button";
import {
  formatTimestamp,
  monitoringCapacityLabel,
  subscriptionStateVariant,
} from "@/design/semanticStates";

/**
 * What this organization has today: plan, monitoring capacity, capabilities, and
 * the subscription state behind them.
 */
export default function CurrentPlanCard({
  status,
  loading = false,
  managing = false,
  onManageSubscription,
}) {
  if (loading && !status) {
    return (
      <SurfaceCard className="p-5 animate-pulse" testId="current-plan-loading">
        <div className="h-5 w-1/3 bg-[var(--surface-inset)] rounded mb-4" />
        <div className="h-24 bg-[var(--surface-inset)] rounded" />
      </SurfaceCard>
    );
  }
  if (!status) return null;

  const plan = status.plan ?? {};
  const subscription = status.subscription ?? null;
  const capacity = status.capacity ?? {};
  const entitlements = status.entitlements ?? {};
  const canManage = Boolean(status.permissions?.can_manage_billing);
  const capacityLabel = monitoringCapacityLabel(
    capacity.monitored_area_count,
    capacity.monitored_area_limit
  );

  return (
    <SurfaceCard variant="emphasis" className="p-5" testId="current-plan-card">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="fw-kicker mb-1">Current plan</div>
          <h2
            className="text-xl font-bold tracking-tight text-[var(--text-primary)]"
            data-testid="current-plan-name"
          >
            {plan.display_name ?? "Foundation"}
          </h2>
          <p className="text-sm text-[var(--text-muted)] mt-1" data-testid="current-plan-description">
            {plan.description}
          </p>
          {plan.price_label && (
            <p className="text-sm font-semibold text-[var(--text-primary)] mt-2" data-testid="current-plan-price">
              {plan.price_label}
            </p>
          )}
        </div>
        <div className="flex flex-col items-end gap-2">
          {subscription ? (
            <StatusBadge
              variant={subscriptionStateVariant(subscription.status)}
              label={subscription.status_label}
              testId="subscription-state"
            />
          ) : (
            <StatusBadge
              variant="unknown"
              label="No subscription"
              testId="subscription-state"
            />
          )}
          {canManage && subscription && (
            <Button
              variant="outline"
              onClick={onManageSubscription}
              disabled={managing}
              data-testid="manage-subscription-btn"
            >
              <CreditCard className="w-4 h-4" />
              Manage subscription
              <ExternalLink className="w-3.5 h-3.5" />
            </Button>
          )}
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-5">
        <div>
          <div className="fw-kicker mb-2">Monitoring capacity</div>
          <div
            className="text-2xl font-bold tabular-nums text-[var(--accent-strong)]"
            data-testid="capacity-ratio"
          >
            {capacity.monitored_area_count ?? 0}
            {capacity.monitored_area_limit != null && (
              <span className="text-[var(--text-muted)] text-lg font-semibold">
                {" "}
                / {capacity.monitored_area_limit}
              </span>
            )}
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-1" data-testid="capacity-label">
            {capacityLabel}
          </p>
          {capacity.over_limit && (
            <p className="text-xs text-[var(--signal-strong)] mt-2" data-testid="capacity-over-limit">
              Everything you already monitor stays in place. New forests need more capacity.
            </p>
          )}
        </div>
        <div>
          <div className="fw-kicker mb-2">Included capabilities</div>
          <EntitlementList entitlements={entitlements} />
        </div>
      </div>

      {subscription && (
        <div className="mt-5 pt-4 border-t border-[var(--surface-inset)] grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs text-[var(--text-muted)]">
          {subscription.cancel_at_period_end ? (
            <div data-testid="subscription-cancellation">
              Cancels on {formatTimestamp(subscription.current_period_end)}. Monitoring
              continues until then.
            </div>
          ) : (
            subscription.current_period_end && (
              <div data-testid="subscription-renewal">
                Renews on {formatTimestamp(subscription.current_period_end)}
              </div>
            )
          )}
          {subscription.trial_end && (
            <div data-testid="subscription-trial">
              Trial ends {formatTimestamp(subscription.trial_end)}
            </div>
          )}
          {subscription.payment_attention_required && (
            <div className="text-[var(--signal-strong)]" data-testid="subscription-payment-attention">
              A payment needs attention. Update your payment details to keep monitoring
              capacity.
            </div>
          )}
        </div>
      )}
    </SurfaceCard>
  );
}
