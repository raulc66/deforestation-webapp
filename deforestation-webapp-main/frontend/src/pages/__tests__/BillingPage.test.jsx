import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import BillingPage from "../BillingPage";

jest.mock("@/lib/api", () => ({
  api: { get: jest.fn(), post: jest.fn() },
  API: "http://localhost:8000/api",
  formatApiErrorDetail: (d) => (d ? String(d) : "Something went wrong."),
}));

jest.mock("@/components/layout/AppLayout", () => ({ children }) => (
  <div data-testid="app-layout">{children}</div>
));

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, disabled, type, ...rest }) => (
    <button onClick={onClick} disabled={disabled} type={type} {...rest}>
      {children}
    </button>
  ),
}));

jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

jest.mock("@/api/billing", () => ({
  fetchBillingStatus: jest.fn(),
  fetchBillingPlans: jest.fn(),
  startCheckout: jest.fn(),
  openBillingPortal: jest.fn(),
}));

const mockOrgState = {
  currentOrganization: { id: "org-a", name: "Org A", role: "owner" },
  selectedOrgId: "org-a",
  organizationVersion: 1,
};

jest.mock("@/context/OrganizationContext", () => ({
  useOrganization: () => mockOrgState,
}));

const billingApi = require("@/api/billing");
const { toast } = require("sonner");

const FOUNDATION_PLAN = {
  key: "foundation",
  display_name: "Foundation",
  description: "Continuous monitoring for a single forest.",
  audience: "Individual forest owners",
  price_label: "EUR 19 / month",
  monitored_area_limit: 1,
  capabilities: ["1 monitored forest", "Forest disturbance intelligence"],
  purchasable: true,
  contact_sales: false,
  current: true,
};

const PROFESSIONAL_PLAN = {
  key: "professional",
  display_name: "Professional",
  description: "Monitor a forest portfolio with cross-source evidence.",
  audience: "Organizations managing multiple forest assets",
  price_label: "EUR 149 / month",
  monitored_area_limit: 5,
  capabilities: ["5 monitored forests", "Alert delivery to email and webhooks"],
  purchasable: true,
  contact_sales: false,
  current: false,
};

const ENTERPRISE_PLAN = {
  key: "enterprise",
  display_name: "Enterprise",
  description: "Institutional forest monitoring capacity.",
  audience: "Forestry institutions",
  price_label: "",
  monitored_area_limit: 50,
  capabilities: ["50 monitored forests"],
  purchasable: false,
  contact_sales: true,
  current: false,
};

function foundationStatus(overrides = {}) {
  return {
    organization: { id: "org-a", name: "Org A", slug: "org-a", role: "owner" },
    plan: { ...FOUNDATION_PLAN, from_subscription: false },
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
      reasons: [
        "1 of 1 monitored forests in use. Upgrade to monitor additional forests.",
        "Alert delivery is not included in your current plan. Upgrade to enable customer alerts.",
      ],
      payment_attention_required: false,
    },
    permissions: { can_manage_billing: true, can_view_billing: true },
    synchronization: {
      billing_configured: false,
      last_event_type: null,
      last_event_at: null,
      last_failure_at: null,
      failed_event_count: 0,
      subscription_synchronized: true,
    },
    ...overrides,
  };
}

function professionalStatus() {
  return {
    ...foundationStatus(),
    plan: { ...PROFESSIONAL_PLAN, current: true, from_subscription: true },
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
    entitlements: {
      monitored_area_limit: 5,
      monitored_area_count: 2,
      monitoring_enabled: true,
      forest_disturbance_enabled: true,
      evidence_correlation_enabled: true,
      live_sources_enabled: true,
      alert_delivery_enabled: true,
    },
    capacity: {
      monitored_area_count: 2,
      monitored_area_limit: 5,
      remaining: 3,
      at_limit: false,
      over_limit: false,
    },
    upgrade: {
      recommended: false,
      recommended_plan_key: null,
      recommended_plan_name: null,
      reasons: [],
      payment_attention_required: false,
    },
  };
}

function mockBilling(status, { canManage = true, plans } = {}) {
  billingApi.fetchBillingStatus.mockResolvedValue(status);
  billingApi.fetchBillingPlans.mockResolvedValue({
    items: plans ?? [FOUNDATION_PLAN, PROFESSIONAL_PLAN, ENTERPRISE_PLAN],
    current_plan_key: status.plan.key,
    can_manage_billing: canManage,
  });
}

beforeEach(() => {
  mockOrgState.currentOrganization = { id: "org-a", name: "Org A", role: "owner" };
  mockOrgState.selectedOrgId = "org-a";
  mockOrgState.organizationVersion = 1;
  delete window.location;
  window.location = { assign: jest.fn(), href: "" };
});

describe("BillingPage plan state", () => {
  it("shows the organization and its current plan", async () => {
    mockBilling(foundationStatus());
    render(<BillingPage />);
    await waitFor(() =>
      expect(screen.getByTestId("current-plan-name")).toHaveTextContent("Foundation")
    );
    expect(screen.getByTestId("billing-page-org-name")).toHaveTextContent("Org A");
    expect(screen.getByTestId("current-plan-price")).toHaveTextContent("EUR 19 / month");
  });

  it("reports monitoring capacity in product language", async () => {
    mockBilling(foundationStatus());
    render(<BillingPage />);
    await waitFor(() => expect(screen.getByTestId("capacity-label")).toBeInTheDocument());
    expect(screen.getByTestId("capacity-label")).toHaveTextContent(
      "1 of 1 monitored forest in use"
    );
    expect(screen.getByTestId("capacity-ratio")).toHaveTextContent("1");
  });

  it("shows the entitlement summary", async () => {
    mockBilling(foundationStatus());
    render(<BillingPage />);
    await waitFor(() => expect(screen.getByTestId("entitlement-list")).toBeInTheDocument());
    expect(screen.getByTestId("entitlement-alerts-status")).toHaveTextContent("Not enabled");
    expect(screen.getByTestId("entitlement-disturbance-status")).toHaveTextContent("Active");
  });

  it("shows no subscription for a baseline organization", async () => {
    mockBilling(foundationStatus());
    render(<BillingPage />);
    await waitFor(() =>
      expect(screen.getByTestId("subscription-state")).toHaveTextContent("No subscription")
    );
    expect(screen.queryByTestId("manage-subscription-btn")).not.toBeInTheDocument();
  });

  it("shows subscription state and renewal for a subscribed organization", async () => {
    mockBilling(professionalStatus());
    render(<BillingPage />);
    await waitFor(() =>
      expect(screen.getByTestId("subscription-state")).toHaveTextContent("Active")
    );
    expect(screen.getByTestId("subscription-renewal")).toHaveTextContent("Renews on");
  });

  it("explains a scheduled cancellation without alarming language", async () => {
    const status = professionalStatus();
    status.subscription.cancel_at_period_end = true;
    mockBilling(status);
    render(<BillingPage />);
    await waitFor(() =>
      expect(screen.getByTestId("subscription-cancellation")).toBeInTheDocument()
    );
    expect(screen.getByTestId("subscription-cancellation")).toHaveTextContent(
      /Monitoring continues until then/
    );
  });

  it("surfaces a payment that needs attention", async () => {
    const status = professionalStatus();
    status.subscription.status = "past_due";
    status.subscription.status_label = "Payment overdue";
    status.subscription.payment_attention_required = true;
    status.upgrade.payment_attention_required = true;
    mockBilling(status);
    render(<BillingPage />);
    await waitFor(() =>
      expect(screen.getByTestId("subscription-payment-attention")).toBeInTheDocument()
    );
    expect(screen.getByTestId("billing-payment-attention")).toBeInTheDocument();
  });

  it("explains an over-capacity organization without threatening data loss", async () => {
    const status = foundationStatus();
    status.capacity = {
      monitored_area_count: 5,
      monitored_area_limit: 1,
      remaining: 0,
      at_limit: true,
      over_limit: true,
    };
    mockBilling(status);
    render(<BillingPage />);
    await waitFor(() =>
      expect(screen.getByTestId("capacity-over-limit")).toBeInTheDocument()
    );
    expect(screen.getByTestId("capacity-over-limit")).toHaveTextContent(
      /stays in place/
    );
  });

  it("states that Stripe handles payment details", async () => {
    mockBilling(foundationStatus());
    render(<BillingPage />);
    await waitFor(() =>
      expect(screen.getByTestId("billing-payment-notice")).toHaveTextContent(/Stripe/)
    );
  });
});

describe("BillingPage plan options", () => {
  it("lists every published plan", async () => {
    mockBilling(foundationStatus());
    render(<BillingPage />);
    await waitFor(() => expect(screen.getByTestId("plan-options")).toBeInTheDocument());
    expect(screen.getByTestId("plan-option-foundation")).toBeInTheDocument();
    expect(screen.getByTestId("plan-option-professional")).toBeInTheDocument();
    expect(screen.getByTestId("plan-option-enterprise")).toBeInTheDocument();
  });

  it("marks the current plan and the recommended plan", async () => {
    mockBilling(foundationStatus());
    render(<BillingPage />);
    await waitFor(() =>
      expect(screen.getByTestId("plan-foundation-current")).toBeInTheDocument()
    );
    expect(screen.getByTestId("plan-professional-recommended")).toBeInTheDocument();
  });

  it("shows plan capabilities as customer language", async () => {
    mockBilling(foundationStatus());
    render(<BillingPage />);
    await waitFor(() =>
      expect(screen.getByTestId("plan-professional-capabilities")).toHaveTextContent(
        "Alert delivery to email and webhooks"
      )
    );
  });

  it("offers contact-sales plans without a purchase button", async () => {
    mockBilling(foundationStatus());
    render(<BillingPage />);
    await waitFor(() =>
      expect(screen.getByTestId("plan-enterprise-contact")).toBeInTheDocument()
    );
    expect(screen.queryByTestId("plan-enterprise-select")).not.toBeInTheDocument();
  });

  it("shows what more capacity would add", async () => {
    mockBilling(foundationStatus());
    render(<BillingPage />);
    await waitFor(() =>
      expect(screen.getByTestId("billing-upgrade-reasons")).toBeInTheDocument()
    );
    expect(screen.getByTestId("billing-recommended-plan")).toHaveTextContent("Professional");
  });

  it("hides upgrade reasoning when nothing is missing", async () => {
    mockBilling(professionalStatus());
    render(<BillingPage />);
    await waitFor(() => expect(screen.getByTestId("plan-options")).toBeInTheDocument());
    expect(screen.queryByTestId("billing-upgrade-reasons")).not.toBeInTheDocument();
  });

  it("never renders entitlement identifiers or Stripe ids", async () => {
    mockBilling(professionalStatus());
    const { container } = render(<BillingPage />);
    await waitFor(() => expect(screen.getByTestId("plan-options")).toBeInTheDocument());
    expect(container.textContent).not.toMatch(/alert_delivery_enabled/);
    expect(container.textContent).not.toMatch(/price_/);
    expect(container.textContent).not.toMatch(/sub_|cus_/);
  });
});

describe("BillingPage checkout and portal", () => {
  it("starts checkout with a plan key and redirects to Stripe", async () => {
    mockBilling(foundationStatus());
    billingApi.startCheckout.mockResolvedValue({
      checkout_url: "https://checkout.stripe.test/c/cs_1",
      plan_key: "professional",
    });
    render(<BillingPage />);
    await waitFor(() =>
      expect(screen.getByTestId("plan-professional-select")).toBeInTheDocument()
    );
    await userEvent.click(screen.getByTestId("plan-professional-select"));
    await waitFor(() => expect(billingApi.startCheckout).toHaveBeenCalledWith("professional"));
    expect(window.location.assign).toHaveBeenCalledWith(
      "https://checkout.stripe.test/c/cs_1"
    );
  });

  it("reports a checkout failure without leaving the page broken", async () => {
    mockBilling(foundationStatus());
    billingApi.startCheckout.mockRejectedValue({
      response: { data: { detail: "Selected plan is not available for purchase" } },
    });
    render(<BillingPage />);
    await waitFor(() =>
      expect(screen.getByTestId("plan-professional-select")).toBeInTheDocument()
    );
    await userEvent.click(screen.getByTestId("plan-professional-select"));
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Selected plan is not available for purchase")
    );
    expect(screen.getByTestId("current-plan-name")).toBeInTheDocument();
  });

  it("opens the Stripe portal to manage the subscription", async () => {
    mockBilling(professionalStatus());
    billingApi.openBillingPortal.mockResolvedValue({
      portal_url: "https://billing.stripe.test/p/bps_1",
    });
    render(<BillingPage />);
    await waitFor(() =>
      expect(screen.getByTestId("manage-subscription-btn")).toBeInTheDocument()
    );
    await userEvent.click(screen.getByTestId("manage-subscription-btn"));
    await waitFor(() =>
      expect(window.location.assign).toHaveBeenCalledWith(
        "https://billing.stripe.test/p/bps_1"
      )
    );
  });

  it("reports a portal failure", async () => {
    mockBilling(professionalStatus());
    billingApi.openBillingPortal.mockRejectedValue({
      response: { data: { detail: "Billing is not available right now" } },
    });
    render(<BillingPage />);
    await waitFor(() =>
      expect(screen.getByTestId("manage-subscription-btn")).toBeInTheDocument()
    );
    await userEvent.click(screen.getByTestId("manage-subscription-btn"));
    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("Billing is not available right now")
    );
  });
});

describe("BillingPage permissions", () => {
  it("hides plan selection from members", async () => {
    const status = foundationStatus();
    status.permissions = { can_manage_billing: false, can_view_billing: true };
    mockBilling(status, { canManage: false });
    render(<BillingPage />);
    await waitFor(() =>
      expect(screen.getByTestId("plan-professional-read-only")).toBeInTheDocument()
    );
    expect(screen.queryByTestId("plan-professional-select")).not.toBeInTheDocument();
  });

  it("hides subscription management from members", async () => {
    const status = professionalStatus();
    status.permissions = { can_manage_billing: false, can_view_billing: true };
    mockBilling(status, { canManage: false });
    render(<BillingPage />);
    await waitFor(() => expect(screen.getByTestId("current-plan-card")).toBeInTheDocument());
    expect(screen.queryByTestId("manage-subscription-btn")).not.toBeInTheDocument();
  });

  it("still shows the plan and capabilities to members", async () => {
    const status = professionalStatus();
    status.permissions = { can_manage_billing: false, can_view_billing: true };
    mockBilling(status, { canManage: false });
    render(<BillingPage />);
    await waitFor(() =>
      expect(screen.getByTestId("current-plan-name")).toHaveTextContent("Professional")
    );
    expect(screen.getByTestId("entitlement-list")).toBeInTheDocument();
  });
});

describe("BillingPage organization coherence", () => {
  it("reloads billing state when the organization changes", async () => {
    mockBilling(professionalStatus());
    const { rerender } = render(<BillingPage />);
    await waitFor(() =>
      expect(screen.getByTestId("current-plan-name")).toHaveTextContent("Professional")
    );

    mockOrgState.currentOrganization = { id: "org-b", name: "Org B", role: "owner" };
    mockOrgState.selectedOrgId = "org-b";
    mockOrgState.organizationVersion = 2;
    mockBilling(foundationStatus());
    rerender(<BillingPage />);

    await waitFor(() =>
      expect(screen.getByTestId("current-plan-name")).toHaveTextContent("Foundation")
    );
    expect(screen.getByTestId("billing-page-org-name")).toHaveTextContent("Org B");
  });

  it("does not leak the previous organization's subscription", async () => {
    mockBilling(professionalStatus());
    const { rerender } = render(<BillingPage />);
    await waitFor(() =>
      expect(screen.getByTestId("subscription-state")).toHaveTextContent("Active")
    );

    mockOrgState.selectedOrgId = "org-b";
    mockOrgState.organizationVersion = 2;
    mockBilling(foundationStatus());
    rerender(<BillingPage />);

    await waitFor(() =>
      expect(screen.getByTestId("subscription-state")).toHaveTextContent("No subscription")
    );
    expect(screen.queryByTestId("subscription-renewal")).not.toBeInTheDocument();
  });

  it("clears billing surfaces when the reload fails", async () => {
    mockBilling(professionalStatus());
    const { rerender } = render(<BillingPage />);
    await waitFor(() => expect(screen.getByTestId("current-plan-card")).toBeInTheDocument());

    mockOrgState.selectedOrgId = "org-b";
    mockOrgState.organizationVersion = 3;
    billingApi.fetchBillingStatus.mockRejectedValue(new Error("network down"));
    billingApi.fetchBillingPlans.mockRejectedValue(new Error("network down"));
    rerender(<BillingPage />);

    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(screen.queryByTestId("current-plan-card")).not.toBeInTheDocument();
    expect(screen.queryByTestId("plan-option-professional")).not.toBeInTheDocument();
  });

  it("waits for an organization before requesting billing state", async () => {
    mockOrgState.selectedOrgId = null;
    mockBilling(foundationStatus());
    render(<BillingPage />);
    await waitFor(() => expect(screen.getByTestId("billing-page")).toBeInTheDocument());
    expect(billingApi.fetchBillingStatus).not.toHaveBeenCalled();
  });
});

describe("BillingPage synchronization state", () => {
  it("warns when a subscription update could not be applied", async () => {
    const status = professionalStatus();
    status.synchronization = {
      ...status.synchronization,
      failed_event_count: 2,
      last_failure_at: "2026-08-13T10:00:00Z",
    };
    mockBilling(status);
    render(<BillingPage />);
    await waitFor(() =>
      expect(screen.getByTestId("billing-sync-warning")).toBeInTheDocument()
    );
    expect(screen.getByTestId("billing-sync-warning")).toHaveTextContent(
      /capabilities remain unchanged/
    );
  });

  it("stays quiet when synchronization is healthy", async () => {
    mockBilling(professionalStatus());
    render(<BillingPage />);
    await waitFor(() => expect(screen.getByTestId("plan-options")).toBeInTheDocument());
    expect(screen.queryByTestId("billing-sync-warning")).not.toBeInTheDocument();
  });
});
