import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import AppLayout from "@/components/layout/AppLayout";
import SurfaceCard from "@/components/product/SurfaceCard";
import CurrentPlanCard from "@/components/billing/CurrentPlanCard";
import PlanOptionList from "@/components/billing/PlanOptionList";
import UpgradePrompt from "@/components/billing/UpgradePrompt";
import { useOrganization } from "@/context/OrganizationContext";
import { useDemo } from "@/context/DemoContext";
import { useTrial } from "@/context/TrialContext";
import DemoConversionCta from "@/components/demo/DemoConversionCta";
import TrialConversionCta from "@/components/trial/TrialConversionCta";
import {
  fetchBillingPlans,
  fetchBillingStatus,
  openBillingPortal,
  startCheckout,
} from "@/api/billing";

function errorMessage(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback;
}

/**
 * Organization-scoped commercial surface: what the organization can monitor
 * today, and how to change it.
 *
 * Billing state is cleared before every reload so a previously selected
 * organization's plan can never remain on screen.
 */
export default function BillingPage() {
  const { currentOrganization, selectedOrgId, organizationVersion } = useOrganization();
  const { isDemo, recordEvent } = useDemo();
  const { isTrial, isExpired, status: trialStatus } = useTrial();

  const [status, setStatus] = useState(null);
  const [plans, setPlans] = useState([]);
  const [canManage, setCanManage] = useState(false);
  const [loading, setLoading] = useState(true);
  const [pendingPlanKey, setPendingPlanKey] = useState(null);
  const [managing, setManaging] = useState(false);

  const reset = useCallback(() => {
    setStatus(null);
    setPlans([]);
    setCanManage(false);
    setPendingPlanKey(null);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [statusData, planData] = await Promise.all([
        fetchBillingStatus(),
        fetchBillingPlans(),
      ]);
      setStatus(statusData);
      setPlans(planData?.items ?? []);
      setCanManage(Boolean(planData?.can_manage_billing));
    } catch (err) {
      reset();
      toast.error(errorMessage(err, "Failed to load plan information"));
    } finally {
      setLoading(false);
    }
  }, [reset]);

  useEffect(() => {
    if (isDemo) return;
    if (!selectedOrgId) return;
    reset();
    load();
  }, [selectedOrgId, organizationVersion, load, reset, isDemo]);

  const choosePlan = useCallback(async (planKey) => {
    setPendingPlanKey(planKey);
    try {
      const session = await startCheckout(planKey);
      if (session?.checkout_url) {
        // Payment details are entered on Stripe's hosted page, never here.
        window.location.assign(session.checkout_url);
        return;
      }
      toast.error("Could not open secure checkout");
    } catch (err) {
      toast.error(errorMessage(err, "Could not open secure checkout"));
    } finally {
      setPendingPlanKey(null);
    }
  }, []);

  const manageSubscription = useCallback(async () => {
    setManaging(true);
    try {
      const session = await openBillingPortal();
      if (session?.portal_url) {
        window.location.assign(session.portal_url);
        return;
      }
      toast.error("Could not open subscription management");
    } catch (err) {
      toast.error(errorMessage(err, "Could not open subscription management"));
    } finally {
      setManaging(false);
    }
  }, []);

  const upgrade = status?.upgrade ?? {};
  const synchronization = status?.synchronization ?? {};

  if (isDemo) {
    return (
      <AppLayout>
        <div className="p-6 md:p-8 max-w-3xl mx-auto" data-testid="billing-page">
          <SurfaceCard className="p-5" testId="demo-billing-blocked">
            <div className="fw-kicker mb-2">Plan</div>
            <h1 className="text-xl font-bold">Create an organization to subscribe</h1>
            <p className="text-sm text-[var(--text-muted)] mt-2">
              Demonstration sessions have no billing account and cannot purchase a plan.
            </p>
            <DemoConversionCta
              moment="exhausted"
              onClick={() => recordEvent("conversion_cta_clicked", { moment: "billing" })}
            />
          </SurfaceCard>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6" data-testid="billing-page">
        <SurfaceCard variant="emphasis" className="p-5" testId="billing-page-header">
          <div className="fw-kicker mb-1">Plan &amp; monitoring capacity</div>
          <h1
            className="text-xl font-bold tracking-tight text-[var(--text-primary)]"
            data-testid="billing-page-org-name"
          >
            {currentOrganization?.name ?? "Organization"}
          </h1>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Continuous intelligence for monitored forests. Your plan sets how many forests
            you can monitor and which intelligence capabilities are active.
          </p>
        </SurfaceCard>

        {isTrial && (
          <p className="text-sm text-[var(--text-secondary)]" data-testid="billing-trial-note">
            Trial · {trialStatus?.days_remaining ?? 0} days remaining. A paid plan replaces
            this entitlement profile without changing your forests, intelligence, or alerts.
          </p>
        )}
        {isExpired && <TrialConversionCta moment="expired" />}

        <CurrentPlanCard
          status={status}
          loading={loading}
          managing={managing}
          onManageSubscription={manageSubscription}
        />

        {upgrade.payment_attention_required && (
          <UpgradePrompt
            message="A recent payment needs attention. Update your payment details to keep your monitoring capacity."
            actionLabel="Manage subscription"
            to="/billing"
            testId="billing-payment-attention"
          />
        )}

        {(upgrade.reasons ?? []).length > 0 && (
          <SurfaceCard className="p-5" testId="billing-upgrade-reasons">
            <div className="fw-kicker mb-2">What more capacity would add</div>
            <ul className="space-y-2">
              {upgrade.reasons.map((reason) => (
                <li key={reason} className="text-sm text-[var(--text-primary)]">
                  {reason}
                </li>
              ))}
            </ul>
            {upgrade.recommended_plan_name && (
              <p className="text-xs text-[var(--text-muted)] mt-3" data-testid="billing-recommended-plan">
                {upgrade.recommended_plan_name} covers these.
              </p>
            )}
          </SurfaceCard>
        )}

        <PlanOptionList
          plans={plans}
          canManage={canManage}
          pendingPlanKey={pendingPlanKey}
          recommendedPlanKey={upgrade.recommended_plan_key}
          loading={loading}
          onSelectPlan={choosePlan}
        />

        {synchronization.failed_event_count > 0 && (
          <SurfaceCard className="p-4" testId="billing-sync-warning">
            <p className="text-sm text-[var(--text-muted)]">
              A recent subscription update could not be applied automatically. Your current
              capabilities remain unchanged while we reconcile it.
            </p>
          </SurfaceCard>
        )}

        <p className="text-xs text-[var(--text-muted)]" data-testid="billing-payment-notice">
          Payments and payment details are handled by Stripe. ForestWatch never stores card
          details.
        </p>
      </div>
    </AppLayout>
  );
}
