import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import UpgradePrompt from "../UpgradePrompt";
import BillingCapabilityStrip from "../BillingCapabilityStrip";
import PlanOptionList from "../PlanOptionList";
import CurrentPlanCard from "../CurrentPlanCard";
import MonitoredAreasCard from "@/components/intelligence/MonitoredAreasCard";
import CustomerMonitoringStatusCard from "@/components/intelligence/CustomerMonitoringStatusCard";
import AlertPolicyList from "@/components/alerts/AlertPolicyList";

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, disabled, ...rest }) => (
    <button onClick={onClick} disabled={disabled} {...rest}>
      {children}
    </button>
  ),
}));

const PLANS = [
  {
    key: "foundation",
    display_name: "Foundation",
    description: "One monitored forest.",
    audience: "Individual owners",
    price_label: "EUR 19 / month",
    monitored_area_limit: 1,
    capabilities: ["1 monitored forest"],
    purchasable: true,
    contact_sales: false,
    current: true,
  },
  {
    key: "professional",
    display_name: "Professional",
    description: "A forest portfolio.",
    audience: "Multi-asset organizations",
    price_label: "EUR 149 / month",
    monitored_area_limit: 5,
    capabilities: ["5 monitored forests", "Alert delivery to email and webhooks"],
    purchasable: true,
    contact_sales: false,
    current: false,
  },
  {
    key: "enterprise",
    display_name: "Enterprise",
    description: "Institutional capacity.",
    audience: "Institutions",
    price_label: "",
    monitored_area_limit: 50,
    capabilities: ["50 monitored forests"],
    purchasable: false,
    contact_sales: true,
    current: false,
  },
];

const BASELINE_STATUS = {
  plan: PLANS[0],
  subscription: null,
  entitlements: {
    monitored_area_limit: 1,
    monitored_area_count: 1,
    monitoring_enabled: true,
    forest_disturbance_enabled: true,
    evidence_correlation_enabled: false,
    live_sources_enabled: false,
    alert_delivery_enabled: false,
  },
  capacity: {
    monitored_area_count: 1,
    monitored_area_limit: 1,
    remaining: 0,
    at_limit: true,
    over_limit: false,
  },
  upgrade: {
    recommended: true,
    recommended_plan_key: "professional",
    recommended_plan_name: "Professional",
    reasons: ["Alert delivery is not included in your current plan."],
    payment_attention_required: false,
  },
  permissions: { can_manage_billing: true, can_view_billing: true },
};

describe("UpgradePrompt", () => {
  it("links a limitation to the billing surface", () => {
    render(<UpgradePrompt message="Alert delivery is not included." actionLabel="Upgrade" />);
    expect(screen.getByTestId("upgrade-prompt")).toHaveTextContent(
      "Alert delivery is not included."
    );
    expect(screen.getByTestId("upgrade-prompt-link")).toHaveAttribute("href", "/billing");
  });

  it("renders nothing without a message", () => {
    const { container } = render(<UpgradePrompt />);
    expect(container).toBeEmptyDOMElement();
  });

  it("supports a compact inline form", () => {
    render(<UpgradePrompt message="Limit reached." compact testId="inline-prompt" />);
    expect(screen.getByTestId("inline-prompt")).toBeInTheDocument();
    expect(screen.getByTestId("inline-prompt-link")).toBeInTheDocument();
  });
});

describe("BillingCapabilityStrip", () => {
  it("shows plan, capacity, and alert capability", () => {
    render(<BillingCapabilityStrip status={BASELINE_STATUS} />);
    expect(screen.getByTestId("strip-plan-name")).toHaveTextContent("Foundation");
    expect(screen.getByTestId("strip-capacity")).toHaveTextContent(
      "1 of 1 monitored forest in use"
    );
    expect(screen.getByTestId("strip-alert-capability")).toHaveTextContent("Not in plan");
  });

  it("links to billing when an upgrade is relevant", () => {
    render(<BillingCapabilityStrip status={BASELINE_STATUS} />);
    expect(screen.getByTestId("strip-billing-link")).toHaveTextContent(
      "Increase monitoring capability"
    );
  });

  it("prioritizes a payment problem over an upgrade nudge", () => {
    const status = {
      ...BASELINE_STATUS,
      upgrade: { ...BASELINE_STATUS.upgrade, payment_attention_required: true },
    };
    render(<BillingCapabilityStrip status={status} />);
    expect(screen.getByTestId("strip-billing-link")).toHaveTextContent(
      "Payment needs attention"
    );
  });

  it("stays quiet when nothing needs the customer's attention", () => {
    const status = {
      ...BASELINE_STATUS,
      entitlements: { ...BASELINE_STATUS.entitlements, alert_delivery_enabled: true },
      upgrade: { recommended: false, reasons: [], payment_attention_required: false },
    };
    render(<BillingCapabilityStrip status={status} />);
    expect(screen.queryByTestId("strip-billing-link")).not.toBeInTheDocument();
    expect(screen.getByTestId("strip-alert-capability")).toHaveTextContent("Enabled");
  });

  it("renders nothing when billing state is unavailable", () => {
    const { container } = render(<BillingCapabilityStrip status={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("PlanOptionList", () => {
  it("offers a purchase action only for other purchasable plans", async () => {
    const onSelectPlan = jest.fn();
    render(<PlanOptionList plans={PLANS} canManage onSelectPlan={onSelectPlan} />);
    await userEvent.click(screen.getByTestId("plan-professional-select"));
    expect(onSelectPlan).toHaveBeenCalledWith("professional");
    expect(screen.queryByTestId("plan-foundation-select")).not.toBeInTheDocument();
  });

  it("shows a pending state while checkout opens", () => {
    render(<PlanOptionList plans={PLANS} canManage pendingPlanKey="professional" />);
    expect(screen.getByTestId("plan-professional-select")).toBeDisabled();
    expect(screen.getByTestId("plan-professional-select")).toHaveTextContent(
      /Opening secure checkout/
    );
  });

  it("explains the active plan instead of selling it again", () => {
    render(<PlanOptionList plans={PLANS} canManage />);
    expect(screen.getByTestId("plan-foundation-active-note")).toHaveTextContent(
      /active for your organization/
    );
  });

  it("falls back to pricing on request when no price is configured", () => {
    render(<PlanOptionList plans={PLANS} canManage />);
    expect(screen.getByTestId("plan-enterprise-price")).toHaveTextContent(
      "Pricing on request"
    );
  });

  it("shows a loading placeholder before plans arrive", () => {
    render(<PlanOptionList plans={[]} loading />);
    expect(screen.getByTestId("plan-options-loading")).toBeInTheDocument();
  });
});

describe("CurrentPlanCard", () => {
  it("renders a loading placeholder without status", () => {
    render(<CurrentPlanCard status={null} loading />);
    expect(screen.getByTestId("current-plan-loading")).toBeInTheDocument();
  });

  it("renders nothing when there is no status and no load in flight", () => {
    const { container } = render(<CurrentPlanCard status={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("invokes subscription management", async () => {
    const onManageSubscription = jest.fn();
    render(
      <CurrentPlanCard
        status={{
          ...BASELINE_STATUS,
          subscription: {
            plan_key: "professional",
            plan_name: "Professional",
            status: "active",
            status_label: "Active",
            capability_active: true,
            payment_attention_required: false,
            cancel_at_period_end: false,
            current_period_end: "2026-09-13T12:00:00Z",
            trial_end: null,
          },
        }}
        onManageSubscription={onManageSubscription}
      />
    );
    await userEvent.click(screen.getByTestId("manage-subscription-btn"));
    expect(onManageSubscription).toHaveBeenCalled();
  });
});

describe("Upgrade prompts inside intelligence surfaces", () => {
  it("offers more capacity when the monitored-forest limit is reached", () => {
    render(
      <MonitoredAreasCard
        areas={{ items: [{ id: "a1", name: "Stand" }], total: 1 }}
        entitlements={{ monitored_area_limit: 1, monitored_area_count: 1 }}
      />
    );
    expect(screen.getByTestId("monitored-areas-upgrade")).toHaveTextContent(
      "1 of 1 monitored forest in use"
    );
    expect(screen.getByTestId("monitored-areas-upgrade-link")).toHaveTextContent(
      "Upgrade to monitor additional forests"
    );
  });

  it("stays quiet while capacity remains", () => {
    render(
      <MonitoredAreasCard
        areas={{ items: [{ id: "a1", name: "Stand" }], total: 1 }}
        entitlements={{ monitored_area_limit: 5, monitored_area_count: 1 }}
      />
    );
    expect(screen.queryByTestId("monitored-areas-upgrade")).not.toBeInTheDocument();
  });

  it("offers live environmental sources when they are not included", () => {
    render(
      <CustomerMonitoringStatusCard
        status={{
          entitlements: {
            monitoring_enabled: true,
            monitored_area_limit: 1,
            monitored_area_count: 1,
            live_sources_enabled: false,
          },
          monitored_areas: { enabled_count: 1 },
          disturbance_summary: {},
        }}
      />
    );
    expect(screen.getByTestId("live-sources-upgrade-link")).toHaveTextContent(
      "Upgrade for live environmental intelligence"
    );
  });

  it("stays quiet when live sources are included", () => {
    render(
      <CustomerMonitoringStatusCard
        status={{
          entitlements: {
            monitoring_enabled: true,
            monitored_area_limit: 5,
            monitored_area_count: 1,
            live_sources_enabled: true,
          },
          monitored_areas: { enabled_count: 1 },
          disturbance_summary: {},
        }}
      />
    );
    expect(screen.queryByTestId("live-sources-upgrade")).not.toBeInTheDocument();
  });

  it("offers alert delivery when the plan does not include it", () => {
    render(<AlertPolicyList policies={[]} options={{}} canManage alertDeliveryAvailable={false} />);
    expect(screen.getByTestId("alert-delivery-upgrade-link")).toHaveTextContent(
      "Upgrade to enable customer alerts"
    );
  });

  it("does not mention plans when alert delivery is available", () => {
    render(<AlertPolicyList policies={[]} options={{}} canManage />);
    expect(screen.queryByTestId("alert-delivery-upgrade")).not.toBeInTheDocument();
  });

  it("never exposes entitlement identifiers in upgrade copy", () => {
    const { container } = render(
      <AlertPolicyList policies={[]} options={{}} canManage alertDeliveryAvailable={false} />
    );
    expect(container.textContent).not.toMatch(/alert_delivery_enabled/);
    expect(container.textContent).not.toMatch(/entitlement/i);
  });
});
