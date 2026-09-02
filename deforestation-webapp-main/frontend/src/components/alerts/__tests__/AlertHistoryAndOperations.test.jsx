import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AlertDeliveryHistory from "../AlertDeliveryHistory";
import AlertOperationsPanel from "../AlertOperationsPanel";

const DELIVERED = {
  id: "del-1",
  policy_name: "Harghita concession watch",
  incident_category_label: "Forest Disturbance",
  alert_stage: "initial",
  alert_stage_label: "Initial alert",
  monitored_area_names: ["Harghita Block"],
  priority: "high",
  lifecycle: "sent",
  delivery_state_label: "Delivered",
  created_at: "2026-08-12T10:00:00Z",
  sent_at: "2026-08-12T10:01:00Z",
  channel_outcomes: [
    {
      channel_id: "chan-1",
      channel_type: "email",
      channel_type_label: "Email channel",
      channel_name: "Operations inbox",
      delivered: true,
      failure_reason: null,
    },
  ],
  suppression_reason: null,
  suppression_reason_label: null,
};

const FAILED = {
  ...DELIVERED,
  id: "del-2",
  lifecycle: "failed",
  delivery_state_label: "Delivery failed",
  sent_at: null,
  channel_outcomes: [
    {
      channel_id: "chan-1",
      channel_type: "email",
      channel_type_label: "Email channel",
      channel_name: "Operations inbox",
      delivered: false,
      failure_reason: "smtp_unavailable",
    },
  ],
};

const SUPPRESSED = {
  ...DELIVERED,
  id: "del-3",
  lifecycle: "suppressed",
  delivery_state_label: "Suppressed",
  sent_at: null,
  channel_outcomes: [],
  suppression_reason: "no_channels",
  suppression_reason_label: "No enabled notification channel configured",
};

describe("AlertDeliveryHistory", () => {
  it("shows a delivered alert with its stage, area and priority", () => {
    render(<AlertDeliveryHistory deliveries={[DELIVERED]} />);
    expect(screen.getByText(/Initial alert · Harghita concession watch/)).toBeInTheDocument();
    expect(screen.getByTestId("alert-delivery-del-1-area")).toHaveTextContent("Harghita Block");
    expect(screen.getByTestId("alert-delivery-del-1-priority")).toHaveTextContent(
      "High priority"
    );
  });

  it("distinguishes delivered from failed", () => {
    render(<AlertDeliveryHistory deliveries={[DELIVERED, FAILED]} />);
    expect(screen.getByTestId("alert-delivery-del-1-state")).toHaveTextContent("Delivered");
    expect(screen.getByTestId("alert-delivery-del-2-state")).toHaveTextContent("Delivery failed");
  });

  it("shows no delivery time for a failed alert", () => {
    render(<AlertDeliveryHistory deliveries={[FAILED]} />);
    expect(screen.getByTestId("alert-delivery-del-2-sent-at")).toHaveTextContent("—");
  });

  it("marks a failing channel in the outcome summary", () => {
    render(<AlertDeliveryHistory deliveries={[FAILED]} />);
    expect(screen.getByText("Operations inbox (failed)")).toBeInTheDocument();
  });

  it("explains a suppression in customer language", () => {
    render(<AlertDeliveryHistory deliveries={[SUPPRESSED]} />);
    expect(screen.getByTestId("alert-delivery-del-3-suppression")).toHaveTextContent(
      "No enabled notification channel configured"
    );
    expect(screen.getByTestId("alert-delivery-del-3-state")).toHaveTextContent("Suppressed");
  });

  it("never renders internal lifecycle identifiers", () => {
    const { container } = render(
      <AlertDeliveryHistory deliveries={[DELIVERED, FAILED, SUPPRESSED]} />
    );
    expect(container.textContent).not.toMatch(/lifecycle/i);
    expect(container.textContent).not.toMatch(/dedupe/i);
    expect(container.textContent).not.toMatch(/smtp_unavailable/);
  });

  it("offers only delivery states the backend reports", () => {
    render(<AlertDeliveryHistory deliveries={[]} />);
    const filters = screen.getByTestId("alert-history-filters");
    expect(filters).toHaveTextContent("Queued");
    expect(filters).toHaveTextContent("Delivered");
    expect(filters).toHaveTextContent("Failed");
    expect(filters).toHaveTextContent("Suppressed");
    expect(filters).not.toHaveTextContent("Bounced");
  });

  it("reports the selected filter and notifies on change", async () => {
    const onFilterChange = jest.fn();
    render(
      <AlertDeliveryHistory deliveries={[]} activeFilter="failed" onFilterChange={onFilterChange} />
    );
    expect(screen.getByTestId("alert-history-filter-failed")).toHaveAttribute(
      "aria-pressed",
      "true"
    );
    await userEvent.click(screen.getByTestId("alert-history-filter-sent"));
    expect(onFilterChange).toHaveBeenCalledWith("sent");
  });

  it("shows an empty state", () => {
    render(<AlertDeliveryHistory deliveries={[]} />);
    expect(screen.getByTestId("alert-history-empty")).toBeInTheDocument();
  });

  it("shows a loading placeholder", () => {
    render(<AlertDeliveryHistory deliveries={[]} loading />);
    expect(screen.getByTestId("alert-history-loading")).toBeInTheDocument();
  });
});

describe("AlertOperationsPanel", () => {
  const overview = {
    alert_delivery_available: true,
    can_manage: true,
    policy_count: 2,
    active_policy_count: 2,
    channel_count: 1,
    enabled_channel_count: 1,
    channel_states: [
      { id: "chan-1", name: "Operations inbox", channel_type: "email", enabled: true, configured: true },
    ],
    pending_count: 0,
    sent_count: 4,
    failed_count: 0,
    suppressed_count: 0,
    attention_count: 0,
    recent_deliveries: [DELIVERED],
  };

  const renderPanel = (props) => render(<AlertOperationsPanel {...props} />);

  it("summarizes alert operations without a second dashboard", () => {
    renderPanel({ overview });
    expect(screen.getByTestId("alert-operations-panel")).toBeInTheDocument();
    expect(screen.getByTestId("alert-operations-delivered")).toHaveTextContent("4");
    expect(screen.getByTestId("alert-operations-policies")).toHaveTextContent("2");
    expect(screen.getByTestId("alert-operations-state")).toHaveTextContent("Delivery ready");
  });

  it("flags alerts requiring attention", () => {
    renderPanel({ overview: { ...overview, failed_count: 2, attention_count: 2 } });
    expect(screen.getByTestId("alert-operations-attention")).toHaveTextContent("2");
  });

  it("reports when delivery is not available for the organization", () => {
    renderPanel({ overview: { ...overview, alert_delivery_available: false } });
    expect(screen.getByTestId("alert-operations-state")).toHaveTextContent("Not available");
  });

  it("reports when configuration is incomplete", () => {
    renderPanel({
      overview: { ...overview, active_policy_count: 0, enabled_channel_count: 0 },
    });
    expect(screen.getByTestId("alert-operations-state")).toHaveTextContent(
      "Needs configuration"
    );
  });

  it("warns about paused or incomplete channels", () => {
    renderPanel({
      overview: {
        ...overview,
        channel_states: [
          { id: "chan-1", name: "Paused inbox", channel_type: "email", enabled: false, configured: true },
        ],
      },
    });
    expect(screen.getByTestId("alert-operations-channel-warning")).toBeInTheDocument();
  });

  it("caps the recent delivery list", () => {
    const many = Array.from({ length: 6 }, (_, index) => ({
      ...DELIVERED,
      id: `del-${index}`,
    }));
    renderPanel({ overview: { ...overview, recent_deliveries: many } });
    expect(screen.getByTestId("alert-operations-recent").children).toHaveLength(3);
  });

  it("links to the alert management surface", () => {
    renderPanel({ overview });
    expect(screen.getByTestId("alert-operations-manage-link")).toHaveAttribute("href", "/alerts");
  });

  it("renders nothing without an overview", () => {
    const { container } = renderPanel({ overview: null });
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a loading placeholder before data arrives", () => {
    renderPanel({ overview: null, loading: true });
    expect(screen.getByTestId("alert-operations-loading")).toBeInTheDocument();
  });

  it("shows an empty state when nothing has been delivered", () => {
    renderPanel({ overview: { ...overview, recent_deliveries: [] } });
    expect(screen.getByTestId("alert-operations-empty")).toBeInTheDocument();
  });
});
