import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AlertsPage from "../AlertsPage";

// The page drives several forms through userEvent, which is slower than the
// 5s default when the whole suite runs in parallel.
jest.setTimeout(20000);

jest.mock("@/lib/api", () => ({
  api: { get: jest.fn(), post: jest.fn(), patch: jest.fn(), delete: jest.fn() },
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

jest.mock("sonner", () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

jest.mock("@/api/customerAlerts", () => ({
  fetchAlertOptions: jest.fn(),
  fetchAlertPolicies: jest.fn(),
  fetchNotificationChannels: jest.fn(),
  fetchAlertDeliveries: jest.fn(),
  createAlertPolicy: jest.fn(),
  updateAlertPolicy: jest.fn(),
  setAlertPolicyActive: jest.fn(),
  deleteAlertPolicy: jest.fn(),
  createNotificationChannel: jest.fn(),
  updateNotificationChannel: jest.fn(),
  setNotificationChannelActive: jest.fn(),
  deleteNotificationChannel: jest.fn(),
}));

jest.mock("@/api/monitoringAreas", () => ({
  fetchMonitoringAreas: jest.fn(),
}));

const mockOrgState = {
  currentOrganization: { id: "org-a", name: "Org A", role: "owner" },
  selectedOrgId: "org-a",
  organizationVersion: 1,
};

jest.mock("@/context/OrganizationContext", () => ({
  useOrganization: () => mockOrgState,
}));

const alertsApi = require("@/api/customerAlerts");
const { fetchMonitoringAreas } = require("@/api/monitoringAreas");
const { toast } = require("sonner");

const OPTIONS = {
  incident_categories: [
    { value: "forest_disturbance", label: "Forest Disturbance" },
    { value: "wildfire", label: "Wildfire" },
  ],
  investigation_priorities: ["low", "medium", "high", "critical"],
  severity_levels: ["low", "medium", "high", "critical"],
  evidence_states: ["single_source", "contextual_support", "multi_source"],
  channel_types: ["email", "webhook"],
  max_cooldown_minutes: 10080,
};

const ORG_A_POLICY = {
  id: "policy-a",
  name: "Org A concession watch",
  enabled: true,
  incident_categories: ["forest_disturbance"],
  minimum_investigation_priority: "high",
  minimum_severity: "medium",
  minimum_evidence_state: null,
  monitored_area_ids: ["area-a"],
  notification_channel_ids: ["chan-a"],
  cooldown_minutes: 60,
};

const ORG_A_CHANNEL = {
  id: "chan-a",
  name: "Org A inbox",
  channel_type: "email",
  enabled: true,
  config: { recipients: ["a@example.com"] },
};

const ORG_A_DELIVERY = {
  id: "del-a",
  policy_name: "Org A concession watch",
  incident_category_label: "Forest Disturbance",
  alert_stage: "initial",
  monitored_area_names: ["Org A Forest"],
  priority: "high",
  lifecycle: "sent",
  delivery_state_label: "Delivered",
  created_at: "2026-08-12T10:00:00Z",
  sent_at: "2026-08-12T10:01:00Z",
  channel_outcomes: [],
};

function mockOrgA({ canManage = true, alertDeliveryAvailable = true } = {}) {
  alertsApi.fetchAlertOptions.mockResolvedValue(OPTIONS);
  alertsApi.fetchAlertPolicies.mockResolvedValue({
    items: [ORG_A_POLICY],
    total: 1,
    can_manage: canManage,
    alert_delivery_available: alertDeliveryAvailable,
  });
  alertsApi.fetchNotificationChannels.mockResolvedValue({
    items: [ORG_A_CHANNEL],
    total: 1,
    can_manage: canManage,
  });
  alertsApi.fetchAlertDeliveries.mockResolvedValue({
    items: [ORG_A_DELIVERY],
    total: 1,
  });
  fetchMonitoringAreas.mockResolvedValue({
    items: [{ id: "area-a", name: "Org A Forest", enabled: true }],
  });
}

describe("AlertsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockOrgState.currentOrganization = { id: "org-a", name: "Org A", role: "owner" };
    mockOrgState.selectedOrgId = "org-a";
    mockOrgState.organizationVersion = 1;
    mockOrgA();
  });

  it("loads the active organization's alert configuration", async () => {
    render(<AlertsPage />);
    expect(await screen.findByText("Org A concession watch")).toBeInTheDocument();
    expect(screen.getByTestId("alerts-page-org-name")).toHaveTextContent("Org A");
    expect(alertsApi.fetchAlertPolicies).toHaveBeenCalledTimes(1);
  });

  it("reports that alert delivery is available", async () => {
    render(<AlertsPage />);
    expect(await screen.findByTestId("alerts-page-availability")).toHaveTextContent(
      "Alert delivery available"
    );
  });

  it("reports when alert delivery is not part of the plan", async () => {
    mockOrgA({ alertDeliveryAvailable: false });
    render(<AlertsPage />);
    expect(await screen.findByTestId("alerts-page-availability")).toHaveTextContent(
      "Alert delivery not available"
    );
    expect(screen.getByTestId("alert-delivery-unavailable")).toBeInTheDocument();
    expect(screen.queryByTestId("alert-policy-create-btn")).not.toBeInTheDocument();
  });

  it("gives members a read-only experience", async () => {
    mockOrgA({ canManage: false });
    render(<AlertsPage />);
    expect(await screen.findByTestId("alert-policy-read-only")).toBeInTheDocument();
    expect(screen.queryByTestId("alert-policy-policy-a-edit")).not.toBeInTheDocument();
  });

  it("switches to the channel surface", async () => {
    render(<AlertsPage />);
    await screen.findByText("Org A concession watch");
    await userEvent.click(screen.getByTestId("alerts-tab-channels"));
    expect(screen.getByTestId("notification-channel-list")).toBeInTheDocument();
    expect(screen.getByText("Org A inbox")).toBeInTheDocument();
  });

  it("switches to the history surface", async () => {
    render(<AlertsPage />);
    await screen.findByText("Org A concession watch");
    await userEvent.click(screen.getByTestId("alerts-tab-history"));
    expect(screen.getByTestId("alert-delivery-history")).toBeInTheDocument();
    expect(screen.getByTestId("alert-delivery-del-a-state")).toHaveTextContent("Delivered");
  });

  it("creates a policy and reloads the surface", async () => {
    alertsApi.createAlertPolicy.mockResolvedValue({ id: "policy-new" });
    render(<AlertsPage />);
    await screen.findByText("Org A concession watch");
    await userEvent.click(screen.getByTestId("alert-policy-create-btn"));
    await userEvent.type(screen.getByTestId("policy-name-input"), "Second watch");
    await userEvent.click(screen.getByTestId("policy-submit-btn"));

    await waitFor(() => expect(alertsApi.createAlertPolicy).toHaveBeenCalled());
    expect(alertsApi.createAlertPolicy).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Second watch" })
    );
    await waitFor(() => expect(alertsApi.fetchAlertPolicies).toHaveBeenCalledTimes(2));
  });

  it("edits an existing policy through the update route", async () => {
    alertsApi.updateAlertPolicy.mockResolvedValue({ ...ORG_A_POLICY, cooldown_minutes: 30 });
    render(<AlertsPage />);
    await screen.findByText("Org A concession watch");
    await userEvent.click(screen.getByTestId("alert-policy-policy-a-edit"));
    expect(screen.getByTestId("policy-name-input")).toHaveValue("Org A concession watch");
    await userEvent.clear(screen.getByTestId("policy-cooldown-input"));
    await userEvent.type(screen.getByTestId("policy-cooldown-input"), "30");
    await userEvent.click(screen.getByTestId("policy-submit-btn"));

    await waitFor(() =>
      expect(alertsApi.updateAlertPolicy).toHaveBeenCalledWith(
        "policy-a",
        expect.objectContaining({ cooldown_minutes: 30 })
      )
    );
  });

  it("shows a validation message from the backend instead of a success toast", async () => {
    alertsApi.createAlertPolicy.mockRejectedValue({
      response: { data: { detail: "Cooldown must be between 0 and 10080 minutes" } },
    });
    render(<AlertsPage />);
    await screen.findByText("Org A concession watch");
    await userEvent.click(screen.getByTestId("alert-policy-create-btn"));
    await userEvent.type(screen.getByTestId("policy-name-input"), "Bad policy");
    await userEvent.click(screen.getByTestId("policy-submit-btn"));

    expect(await screen.findByTestId("alert-policy-form-error")).toHaveTextContent(
      "Cooldown must be between 0 and 10080 minutes"
    );
    expect(toast.success).not.toHaveBeenCalled();
  });

  it("pauses a policy through the activation route", async () => {
    alertsApi.setAlertPolicyActive.mockResolvedValue({ ...ORG_A_POLICY, enabled: false });
    render(<AlertsPage />);
    await screen.findByText("Org A concession watch");
    await userEvent.click(screen.getByTestId("alert-policy-policy-a-toggle"));
    await waitFor(() =>
      expect(alertsApi.setAlertPolicyActive).toHaveBeenCalledWith("policy-a", false)
    );
  });

  it("deletes a policy", async () => {
    alertsApi.deleteAlertPolicy.mockResolvedValue({});
    render(<AlertsPage />);
    await screen.findByText("Org A concession watch");
    await userEvent.click(screen.getByTestId("alert-policy-policy-a-delete"));
    await waitFor(() => expect(alertsApi.deleteAlertPolicy).toHaveBeenCalledWith("policy-a"));
  });

  it("creates a webhook channel without ever reading back the secret", async () => {
    alertsApi.createNotificationChannel.mockResolvedValue({ id: "chan-new" });
    render(<AlertsPage />);
    await screen.findByText("Org A concession watch");
    await userEvent.click(screen.getByTestId("alerts-tab-channels"));
    await userEvent.click(screen.getByTestId("channel-create-btn"));
    await userEvent.click(screen.getByTestId("channel-type-webhook"));
    await userEvent.type(screen.getByTestId("channel-name-input"), "Dispatch");
    await userEvent.type(screen.getByTestId("channel-url-input"), "https://x.io/h");
    await userEvent.type(screen.getByTestId("channel-secret-input"), "s3cret");
    await userEvent.click(screen.getByTestId("channel-submit-btn"));

    await waitFor(() =>
      expect(alertsApi.createNotificationChannel).toHaveBeenCalledWith({
        channel_type: "webhook",
        name: "Dispatch",
        enabled: true,
        config: { url: "https://x.io/h", secret_token: "s3cret" },
      })
    );
    await waitFor(() => expect(alertsApi.fetchNotificationChannels).toHaveBeenCalledTimes(2));
  });

  it("filters alert history through the backend", async () => {
    render(<AlertsPage />);
    await screen.findByText("Org A concession watch");
    await userEvent.click(screen.getByTestId("alerts-tab-history"));
    alertsApi.fetchAlertDeliveries.mockResolvedValue({ items: [], total: 0 });
    await userEvent.click(screen.getByTestId("alert-history-filter-failed"));
    await waitFor(() =>
      expect(alertsApi.fetchAlertDeliveries).toHaveBeenLastCalledWith({ lifecycle: "failed" })
    );
    expect(await screen.findByTestId("alert-history-empty")).toBeInTheDocument();
  });

  it("clears org A data and loads org B after switching", async () => {
    const { rerender } = render(<AlertsPage />);
    await screen.findByText("Org A concession watch");

    alertsApi.fetchAlertPolicies.mockResolvedValue({
      items: [
        {
          ...ORG_A_POLICY,
          id: "policy-b",
          name: "Org B plantation watch",
          monitored_area_ids: ["area-b"],
          notification_channel_ids: ["chan-b"],
        },
      ],
      total: 1,
      can_manage: true,
      alert_delivery_available: true,
    });
    alertsApi.fetchNotificationChannels.mockResolvedValue({
      items: [{ ...ORG_A_CHANNEL, id: "chan-b", name: "Org B inbox" }],
      total: 1,
      can_manage: true,
    });
    alertsApi.fetchAlertDeliveries.mockResolvedValue({ items: [], total: 0 });
    fetchMonitoringAreas.mockResolvedValue({
      items: [{ id: "area-b", name: "Org B Forest", enabled: true }],
    });
    mockOrgState.currentOrganization = { id: "org-b", name: "Org B", role: "owner" };
    mockOrgState.selectedOrgId = "org-b";
    mockOrgState.organizationVersion = 2;
    rerender(<AlertsPage />);

    expect(await screen.findByText("Org B plantation watch")).toBeInTheDocument();
    expect(screen.queryByText("Org A concession watch")).not.toBeInTheDocument();
    expect(screen.getByTestId("alerts-page-org-name")).toHaveTextContent("Org B");
  });

  it("does not leave org A channels visible after switching", async () => {
    const { rerender } = render(<AlertsPage />);
    await screen.findByText("Org A concession watch");
    await userEvent.click(screen.getByTestId("alerts-tab-channels"));
    expect(screen.getByText("Org A inbox")).toBeInTheDocument();

    alertsApi.fetchNotificationChannels.mockResolvedValue({
      items: [{ ...ORG_A_CHANNEL, id: "chan-b", name: "Org B inbox" }],
      total: 1,
      can_manage: true,
    });
    mockOrgState.selectedOrgId = "org-b";
    mockOrgState.organizationVersion = 2;
    rerender(<AlertsPage />);

    expect(await screen.findByText("Org B inbox")).toBeInTheDocument();
    expect(screen.queryByText("Org A inbox")).not.toBeInTheDocument();
  });

  it("resets the history filter when the organization changes", async () => {
    const { rerender } = render(<AlertsPage />);
    await screen.findByText("Org A concession watch");
    await userEvent.click(screen.getByTestId("alerts-tab-history"));
    await userEvent.click(screen.getByTestId("alert-history-filter-failed"));
    await waitFor(() =>
      expect(alertsApi.fetchAlertDeliveries).toHaveBeenLastCalledWith({ lifecycle: "failed" })
    );

    mockOrgState.selectedOrgId = "org-b";
    mockOrgState.organizationVersion = 2;
    rerender(<AlertsPage />);

    await waitFor(() =>
      expect(alertsApi.fetchAlertDeliveries).toHaveBeenLastCalledWith({})
    );
    expect(screen.getByTestId("alert-history-filter-all")).toHaveAttribute(
      "aria-pressed",
      "true"
    );
  });

  it("clears every surface when the organization load fails", async () => {
    alertsApi.fetchAlertPolicies.mockRejectedValue(new Error("Forbidden"));
    render(<AlertsPage />);
    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(screen.getByTestId("alert-policy-empty")).toBeInTheDocument();
    expect(screen.queryByText("Org A concession watch")).not.toBeInTheDocument();
  });

  it("never renders internal entitlement or tenant terminology", async () => {
    const { container } = render(<AlertsPage />);
    await screen.findByText("Org A concession watch");
    expect(container.textContent).not.toMatch(/alert_delivery_enabled/);
    expect(container.textContent).not.toMatch(/tenant/i);
    expect(container.textContent).not.toMatch(/dedupe_key/);
  });
});
