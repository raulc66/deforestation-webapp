import { Check, Trees } from "lucide-react";
import SurfaceCard from "@/components/product/SurfaceCard";
import StatusBadge from "@/components/product/StatusBadge";
import { Button } from "@/components/ui/button";

function PlanOption({ plan, canManage, pending, onSelect, recommended }) {
  return (
    <SurfaceCard
      variant={plan.current ? "emphasis" : "default"}
      className="p-4 flex flex-col"
      testId={`plan-option-${plan.key}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <Trees className="w-4 h-4 text-[var(--accent-strong)]" strokeWidth={1.7} />
            <h3 className="text-base font-bold text-[var(--text-primary)]">
              {plan.display_name}
            </h3>
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-1">{plan.audience}</p>
        </div>
        {plan.current ? (
          <StatusBadge variant="enabled" label="Current plan" testId={`plan-${plan.key}-current`} />
        ) : recommended ? (
          <StatusBadge variant="operational" label="Recommended" testId={`plan-${plan.key}-recommended`} />
        ) : null}
      </div>

      <p className="text-sm text-[var(--text-muted)] mt-3">{plan.description}</p>

      <div className="text-sm font-semibold text-[var(--text-primary)] mt-3" data-testid={`plan-${plan.key}-price`}>
        {plan.price_label || "Pricing on request"}
      </div>

      <ul className="mt-3 space-y-1.5 flex-1" data-testid={`plan-${plan.key}-capabilities`}>
        {(plan.capabilities ?? []).map((capability) => (
          <li key={capability} className="flex items-start gap-2 text-sm text-[var(--text-primary)]">
            <Check className="w-3.5 h-3.5 mt-0.5 text-[var(--accent-strong)]" strokeWidth={2} />
            <span>{capability}</span>
          </li>
        ))}
      </ul>

      <div className="mt-4">
        {plan.current ? (
          <p className="text-xs text-[var(--text-muted)]" data-testid={`plan-${plan.key}-active-note`}>
            These capabilities are active for your organization.
          </p>
        ) : plan.purchasable ? (
          canManage ? (
            <Button
              className="w-full"
              onClick={() => onSelect(plan.key)}
              disabled={pending}
              data-testid={`plan-${plan.key}-select`}
            >
              {pending ? "Opening secure checkout…" : `Choose ${plan.display_name}`}
            </Button>
          ) : (
            <p className="text-xs text-[var(--text-muted)]" data-testid={`plan-${plan.key}-read-only`}>
              An organization owner or admin can change the plan.
            </p>
          )
        ) : (
          <p className="text-xs text-[var(--text-muted)]" data-testid={`plan-${plan.key}-contact`}>
            Talk to us about {plan.display_name} monitoring capacity.
          </p>
        )}
      </div>
    </SurfaceCard>
  );
}

/**
 * Plan options for the organization — a monitoring capability comparison, not a
 * generic pricing table.
 */
export default function PlanOptionList({
  plans = [],
  canManage = false,
  pendingPlanKey = null,
  recommendedPlanKey = null,
  loading = false,
  onSelectPlan,
}) {
  if (loading && plans.length === 0) {
    return (
      <SurfaceCard className="p-5 animate-pulse" testId="plan-options-loading">
        <div className="h-4 w-1/4 bg-[var(--surface-inset)] rounded mb-4" />
        <div className="h-32 bg-[var(--surface-inset)] rounded" />
      </SurfaceCard>
    );
  }

  return (
    <section data-testid="plan-options">
      <div className="fw-kicker mb-3">Monitoring plans</div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {plans.map((plan) => (
          <PlanOption
            key={plan.key}
            plan={plan}
            canManage={canManage}
            pending={pendingPlanKey === plan.key}
            recommended={recommendedPlanKey === plan.key && !plan.current}
            onSelect={onSelectPlan}
          />
        ))}
      </div>
    </section>
  );
}
