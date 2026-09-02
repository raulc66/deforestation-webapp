import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AlertPolicyList from "../AlertPolicyList";
import AlertPolicyForm from "../AlertPolicyForm";
import NotificationChannelList from "../NotificationChannelList";
import NotificationChannelForm from "../NotificationChannelForm";

const OPTIONS = {
  incident_categories: [
    { value: "forest_disturbance", label: "Forest Disturbance" },
    { value: "wildfire", label: "Wildfire" },
  ],
  investigation_priorities: ["low", "medium", "high", "critical"],
  severity_levels: ["low", "medium", "high", "critical"],
  evidence_states: ["single_source", "contextual_support", "multi_source"],
  max_cooldown_minutes: 10080,
};

const AREAS = [{ id: "area-1", name: "Harghita Block" }];
const CHANNELS = [
  {
    id: "chan-1",
    name: "Operations inbox",
    channel_type: "email",
    enabled: true,
    config: { recipients: ["ops@example.com"] },
  },
];

const POLICY = {
  id: "policy-1",
  name: "Harghita concession watch",
  enabled: true,
  incident_categories: ["forest_disturbance"],
  minimum_investigation_priority: "high",
  minimum_severity: "medium",
  minimum_evidence_state: null,
  monitored_area_ids: ["area-1"],
  notification_channel_ids: ["chan-1"],
  cooldown_minutes: 120,
};

describe("AlertPolicyList", () => {
  it("presents the policy in customer language", () => {
    render(
      <AlertPolicyList policies={[POLICY]} options={OPTIONS} monitoredAreas={AREAS} channels={CHANNELS} canManage />
    );
    expect(screen.getByText("Harghita concession watch")).toBeInTheDocument();
    expect(screen.getByTestId("alert-policy-policy-1-status")).toHaveTextContent("Active");
    expect(screen.getByText(/Watches Forest Disturbance/)).toBeInTheDocument();
    expect(screen.getByText("High priority")).toBeInTheDocument();
  });

  it("resolves monitored area and channel names rather than ids", () => {
    render(
      <AlertPolicyList policies={[POLICY]} options={OPTIONS} monitoredAreas={AREAS} channels={CHANNELS} canManage />
    );
    expect(screen.getByTestId("alert-policy-policy-1-areas")).toHaveTextContent("Harghita Block");
    expect(screen.getByTestId("alert-policy-policy-1-channels")).toHaveTextContent(
      "Operations inbox (Email channel)"
    );
    expect(screen.queryByText("area-1")).not.toBeInTheDocument();
  });

  it("describes an unscoped policy as covering all monitored areas", () => {
    render(
      <AlertPolicyList
        policies={[{ ...POLICY, monitored_area_ids: [] }]}
        options={OPTIONS}
        monitoredAreas={AREAS}
        channels={CHANNELS}
        canManage
      />
    );
    expect(screen.getByTestId("alert-policy-policy-1-areas")).toHaveTextContent(
      "All monitored areas"
    );
  });

  it("shows a readable cooldown interval", () => {
    render(<AlertPolicyList policies={[POLICY]} options={OPTIONS} canManage />);
    expect(screen.getByText("2 hr")).toBeInTheDocument();
  });

  it("labels a paused policy without developer wording", () => {
    render(
      <AlertPolicyList policies={[{ ...POLICY, enabled: false }]} options={OPTIONS} canManage />
    );
    expect(screen.getByTestId("alert-policy-policy-1-status")).toHaveTextContent("Paused");
    expect(screen.queryByText(/enabled: false/)).not.toBeInTheDocument();
  });

  it("hides management controls for view-only members", () => {
    render(<AlertPolicyList policies={[POLICY]} options={OPTIONS} canManage={false} />);
    expect(screen.getByTestId("alert-policy-read-only")).toBeInTheDocument();
    expect(screen.queryByTestId("alert-policy-create-btn")).not.toBeInTheDocument();
    expect(screen.queryByTestId("alert-policy-policy-1-edit")).not.toBeInTheDocument();
    expect(screen.queryByTestId("alert-policy-policy-1-delete")).not.toBeInTheDocument();
  });

  it("explains when alert delivery is not available for the organization", () => {
    render(
      <AlertPolicyList policies={[]} options={OPTIONS} canManage alertDeliveryAvailable={false} />
    );
    expect(screen.getByTestId("alert-delivery-unavailable")).toBeInTheDocument();
    expect(screen.getByText("Not available")).toBeInTheDocument();
    expect(screen.queryByTestId("alert-policy-create-btn")).not.toBeInTheDocument();
  });

  it("never renders raw entitlement flag names", () => {
    const { container } = render(
      <AlertPolicyList policies={[POLICY]} options={OPTIONS} canManage alertDeliveryAvailable={false} />
    );
    expect(container.textContent).not.toMatch(/alert_delivery_enabled/);
    expect(container.textContent).not.toMatch(/tenant/i);
  });

  it("shows an empty state that explains the value of a policy", () => {
    render(<AlertPolicyList policies={[]} options={OPTIONS} canManage />);
    expect(screen.getByTestId("alert-policy-empty")).toHaveTextContent(/monitored forests/);
  });

  it("invokes the management callbacks", async () => {
    const onCreate = jest.fn();
    const onEdit = jest.fn();
    const onToggle = jest.fn();
    const onDelete = jest.fn();
    render(
      <AlertPolicyList
        policies={[POLICY]}
        options={OPTIONS}
        canManage
        onCreate={onCreate}
        onEdit={onEdit}
        onToggle={onToggle}
        onDelete={onDelete}
      />
    );
    await userEvent.click(screen.getByTestId("alert-policy-create-btn"));
    await userEvent.click(screen.getByTestId("alert-policy-policy-1-edit"));
    await userEvent.click(screen.getByTestId("alert-policy-policy-1-toggle"));
    await userEvent.click(screen.getByTestId("alert-policy-policy-1-delete"));
    expect(onCreate).toHaveBeenCalled();
    expect(onEdit).toHaveBeenCalledWith(POLICY);
    expect(onToggle).toHaveBeenCalledWith(POLICY);
    expect(onDelete).toHaveBeenCalledWith(POLICY);
  });
});

describe("AlertPolicyForm", () => {
  it("submits a new policy with the configured thresholds", async () => {
    const onSubmit = jest.fn();
    render(
      <AlertPolicyForm
        options={OPTIONS}
        monitoredAreas={AREAS}
        channels={CHANNELS}
        onSubmit={onSubmit}
        onCancel={jest.fn()}
      />
    );
    await userEvent.type(screen.getByTestId("policy-name-input"), "New watch");
    await userEvent.selectOptions(screen.getByTestId("policy-priority-select"), "critical");
    await userEvent.click(screen.getByTestId("policy-area-area-1"));
    await userEvent.click(screen.getByTestId("policy-channel-chan-1"));
    await userEvent.click(screen.getByTestId("policy-submit-btn"));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "New watch",
        minimum_investigation_priority: "critical",
        monitored_area_ids: ["area-1"],
        notification_channel_ids: ["chan-1"],
      })
    );
  });

  it("prefills the form when editing an existing policy", () => {
    render(
      <AlertPolicyForm
        policy={POLICY}
        options={OPTIONS}
        monitoredAreas={AREAS}
        channels={CHANNELS}
        onSubmit={jest.fn()}
        onCancel={jest.fn()}
      />
    );
    expect(screen.getByTestId("policy-name-input")).toHaveValue("Harghita concession watch");
    expect(screen.getByTestId("policy-cooldown-input")).toHaveValue(120);
    expect(screen.getByTestId("policy-area-area-1")).toBeChecked();
    expect(screen.getByText("Edit alert policy")).toBeInTheDocument();
  });

  it("normalizes an empty evidence threshold to null", async () => {
    const onSubmit = jest.fn();
    render(
      <AlertPolicyForm options={OPTIONS} onSubmit={onSubmit} onCancel={jest.fn()} />
    );
    await userEvent.type(screen.getByTestId("policy-name-input"), "Any evidence");
    await userEvent.click(screen.getByTestId("policy-submit-btn"));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ minimum_evidence_state: null })
    );
  });

  it("toggles watched categories", async () => {
    const onSubmit = jest.fn();
    render(<AlertPolicyForm options={OPTIONS} onSubmit={onSubmit} onCancel={jest.fn()} />);
    await userEvent.type(screen.getByTestId("policy-name-input"), "Two categories");
    await userEvent.click(screen.getByTestId("policy-category-wildfire"));
    await userEvent.click(screen.getByTestId("policy-submit-btn"));
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        incident_categories: ["forest_disturbance", "wildfire"],
      })
    );
  });

  it("surfaces a validation message from the backend", () => {
    render(
      <AlertPolicyForm
        options={OPTIONS}
        error="Cooldown must be between 0 and 10080 minutes"
        onSubmit={jest.fn()}
        onCancel={jest.fn()}
      />
    );
    expect(screen.getByTestId("alert-policy-form-error")).toHaveTextContent(
      "Cooldown must be between 0 and 10080 minutes"
    );
  });

  it("prompts to add a channel when none exist", () => {
    render(<AlertPolicyForm options={OPTIONS} channels={[]} onSubmit={jest.fn()} onCancel={jest.fn()} />);
    expect(screen.getByTestId("policy-no-channels")).toBeInTheDocument();
  });
});

describe("NotificationChannelList", () => {
  it("shows the email destination", () => {
    render(<NotificationChannelList channels={CHANNELS} canManage />);
    expect(screen.getByTestId("channel-chan-1-destination")).toHaveTextContent(
      "ops@example.com"
    );
    expect(screen.getByText("Email channel")).toBeInTheDocument();
  });

  it("reports a stored webhook secret without revealing it", () => {
    render(
      <NotificationChannelList
        channels={[
          {
            id: "chan-2",
            name: "Dispatch webhook",
            channel_type: "webhook",
            enabled: true,
            config: { url: "https://example.com/hook", secret_configured: true },
          },
        ]}
        canManage
      />
    );
    expect(screen.getByTestId("notification-channel-chan-2-secret")).toHaveTextContent(
      "Signing secret stored — hidden for security"
    );
  });

  it("reports a webhook without a signing secret", () => {
    render(
      <NotificationChannelList
        channels={[
          {
            id: "chan-3",
            name: "Open webhook",
            channel_type: "webhook",
            enabled: true,
            config: { url: "https://example.com/hook", secret_configured: false },
          },
        ]}
        canManage
      />
    );
    expect(screen.getByTestId("notification-channel-chan-3-secret")).toHaveTextContent(
      "No signing secret configured"
    );
  });

  it("labels a paused channel", () => {
    render(
      <NotificationChannelList channels={[{ ...CHANNELS[0], enabled: false }]} canManage />
    );
    expect(screen.getByTestId("notification-channel-chan-1-status")).toHaveTextContent("Paused");
  });

  it("is read-only for members", () => {
    render(<NotificationChannelList channels={CHANNELS} canManage={false} />);
    expect(screen.getByTestId("channel-read-only")).toBeInTheDocument();
    expect(screen.queryByTestId("channel-create-btn")).not.toBeInTheDocument();
    expect(screen.queryByTestId("notification-channel-chan-1-delete")).not.toBeInTheDocument();
  });

  it("shows an empty state", () => {
    render(<NotificationChannelList channels={[]} canManage />);
    expect(screen.getByTestId("channel-empty")).toBeInTheDocument();
  });

  it("only offers email and webhook", () => {
    const { container } = render(<NotificationChannelList channels={CHANNELS} canManage />);
    expect(container.textContent).not.toMatch(/SMS|push notification/i);
  });
});

describe("NotificationChannelForm", () => {
  it("creates an email channel from comma-separated recipients", async () => {
    const onSubmit = jest.fn();
    render(<NotificationChannelForm onSubmit={onSubmit} onCancel={jest.fn()} />);
    await userEvent.type(screen.getByTestId("channel-name-input"), "Field inbox");
    await userEvent.type(
      screen.getByTestId("channel-recipients-input"),
      "a@example.com, b@example.com"
    );
    await userEvent.click(screen.getByTestId("channel-submit-btn"));

    expect(onSubmit).toHaveBeenCalledWith({
      channel_type: "email",
      name: "Field inbox",
      enabled: true,
      config: { recipients: ["a@example.com", "b@example.com"] },
    });
  });

  it("creates a webhook channel with a write-only secret", async () => {
    const onSubmit = jest.fn();
    render(<NotificationChannelForm onSubmit={onSubmit} onCancel={jest.fn()} />);
    await userEvent.click(screen.getByTestId("channel-type-webhook"));
    await userEvent.type(screen.getByTestId("channel-name-input"), "Dispatch");
    await userEvent.type(screen.getByTestId("channel-url-input"), "https://example.com/hook");
    await userEvent.type(screen.getByTestId("channel-secret-input"), "top-secret");
    await userEvent.click(screen.getByTestId("channel-submit-btn"));

    expect(onSubmit).toHaveBeenCalledWith({
      channel_type: "webhook",
      name: "Dispatch",
      enabled: true,
      config: { url: "https://example.com/hook", secret_token: "top-secret" },
    });
  });

  it("masks the secret field", async () => {
    render(<NotificationChannelForm onSubmit={jest.fn()} onCancel={jest.fn()} />);
    await userEvent.click(screen.getByTestId("channel-type-webhook"));
    expect(screen.getByTestId("channel-secret-input")).toHaveAttribute("type", "password");
  });

  it("never prefills an existing secret when editing", async () => {
    render(
      <NotificationChannelForm
        channel={{
          id: "chan-2",
          name: "Dispatch",
          channel_type: "webhook",
          enabled: true,
          config: { url: "https://example.com/hook", secret_configured: true },
        }}
        onSubmit={jest.fn()}
        onCancel={jest.fn()}
      />
    );
    expect(screen.getByTestId("channel-secret-input")).toHaveValue("");
    expect(screen.getByText(/leave blank to keep it/)).toBeInTheDocument();
  });

  it("omits the secret from an edit that leaves the field blank", async () => {
    const onSubmit = jest.fn();
    render(
      <NotificationChannelForm
        channel={{
          id: "chan-2",
          name: "Dispatch",
          channel_type: "webhook",
          enabled: true,
          config: { url: "https://example.com/hook", secret_configured: true },
        }}
        onSubmit={onSubmit}
        onCancel={jest.fn()}
      />
    );
    await userEvent.click(screen.getByTestId("channel-submit-btn"));
    expect(onSubmit).toHaveBeenCalledWith({
      name: "Dispatch",
      enabled: true,
      config: { url: "https://example.com/hook" },
    });
  });

  it("does not offer a channel type switch when editing", () => {
    render(
      <NotificationChannelForm
        channel={{ id: "chan-1", name: "Inbox", channel_type: "email", enabled: true, config: {} }}
        onSubmit={jest.fn()}
        onCancel={jest.fn()}
      />
    );
    expect(screen.queryByTestId("channel-type-options")).not.toBeInTheDocument();
  });

  it("surfaces a backend validation message", () => {
    render(
      <NotificationChannelForm
        error="Webhook URL must use HTTPS"
        onSubmit={jest.fn()}
        onCancel={jest.fn()}
      />
    );
    expect(screen.getByTestId("channel-form-error")).toHaveTextContent(
      "Webhook URL must use HTTPS"
    );
  });
});
