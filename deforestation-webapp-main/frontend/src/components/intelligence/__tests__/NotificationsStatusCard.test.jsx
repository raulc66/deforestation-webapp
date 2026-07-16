import React from "react";
import { render, screen } from "@testing-library/react";
import NotificationsStatusCard from "../NotificationsStatusCard";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const MOCK_STATUS_ENABLED = {
  enabled: true,
  providers: ["discord", "generic"],
  last_notification: {
    id: "notif-1",
    provider: "discord",
    event_type: "new_anomaly",
    region: "Bacău",
    sent_at: new Date(Date.now() - 5 * 60 * 1000).toISOString(), // 5 min ago
    success: true,
    error: null,
  },
  notifications_sent: 42,
  notifications_failed: 1,
};

const MOCK_STATUS_DISABLED = {
  enabled: false,
  providers: [],
  last_notification: null,
  notifications_sent: 0,
  notifications_failed: 0,
};

const MOCK_STATUS_NO_PROVIDERS = {
  enabled: false,
  providers: [],
  last_notification: null,
  notifications_sent: 0,
  notifications_failed: 0,
};

const MOCK_STATUS_LAST_FAILED = {
  enabled: true,
  providers: ["discord"],
  last_notification: {
    id: "notif-2",
    provider: "discord",
    event_type: "escalation_change",
    region: "Cluj",
    sent_at: new Date(Date.now() - 2 * 60 * 1000).toISOString(),
    success: false,
    error: "Connection timeout",
  },
  notifications_sent: 5,
  notifications_failed: 3,
};

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

describe("NotificationsStatusCard — loading state", () => {
  it("renders loading skeleton when loading=true", () => {
    render(<NotificationsStatusCard status={null} loading={true} />);
    expect(screen.getByTestId("notifications-status-loading")).toBeInTheDocument();
  });

  it("does not render card content while loading", () => {
    render(<NotificationsStatusCard status={null} loading={true} />);
    expect(screen.queryByTestId("notifications-status-card")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Empty state (no status data)
// ---------------------------------------------------------------------------

describe("NotificationsStatusCard — empty state", () => {
  it("renders empty state when status is null and not loading", () => {
    render(<NotificationsStatusCard status={null} loading={false} />);
    expect(screen.getByTestId("notifications-status-empty")).toBeInTheDocument();
  });

  it("shows 'No status available' message", () => {
    render(<NotificationsStatusCard status={null} loading={false} />);
    expect(screen.getByText(/no status available/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Enabled state
// ---------------------------------------------------------------------------

describe("NotificationsStatusCard — enabled with providers", () => {
  beforeEach(() => {
    render(<NotificationsStatusCard status={MOCK_STATUS_ENABLED} loading={false} />);
  });

  it("renders the main card element", () => {
    expect(screen.getByTestId("notifications-status-card")).toBeInTheDocument();
  });

  it("shows enabled badge", () => {
    expect(screen.getByTestId("notifications-badge-enabled")).toBeInTheDocument();
  });

  it("does not show disabled badge", () => {
    expect(screen.queryByTestId("notifications-badge-disabled")).not.toBeInTheDocument();
  });

  it("displays provider names", () => {
    const providers = screen.getByTestId("notifications-providers");
    expect(providers).toHaveTextContent("discord");
    expect(providers).toHaveTextContent("generic");
  });

  it("displays sent count", () => {
    expect(screen.getByTestId("notifications-sent")).toHaveTextContent("42");
  });

  it("displays failed count", () => {
    expect(screen.getByTestId("notifications-failed")).toHaveTextContent("1");
  });

  it("displays last sent time as relative label", () => {
    const lastSent = screen.getByTestId("notifications-last-sent");
    expect(lastSent).toHaveTextContent(/min ago|just now/i);
  });

  it("displays last event type formatted", () => {
    const lastType = screen.getByTestId("notifications-last-event-type");
    expect(lastType).toHaveTextContent(/new anomaly/i);
  });

  it("does not show error message when last notification succeeded", () => {
    expect(screen.queryByTestId("notifications-last-error")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Disabled state
// ---------------------------------------------------------------------------

describe("NotificationsStatusCard — disabled", () => {
  beforeEach(() => {
    render(<NotificationsStatusCard status={MOCK_STATUS_DISABLED} loading={false} />);
  });

  it("shows disabled badge", () => {
    expect(screen.getByTestId("notifications-badge-disabled")).toBeInTheDocument();
  });

  it("shows 'None' for providers when empty", () => {
    expect(screen.getByTestId("notifications-providers")).toHaveTextContent("None");
  });

  it("shows zero sent count", () => {
    expect(screen.getByTestId("notifications-sent")).toHaveTextContent("0");
  });

  it("shows dash for last sent when no notifications", () => {
    expect(screen.getByTestId("notifications-last-sent")).toHaveTextContent("—");
  });

  it("shows dash for last event type when no notifications", () => {
    expect(screen.getByTestId("notifications-last-event-type")).toHaveTextContent("—");
  });
});

// ---------------------------------------------------------------------------
// Last notification failed
// ---------------------------------------------------------------------------

describe("NotificationsStatusCard — last notification failed", () => {
  beforeEach(() => {
    render(<NotificationsStatusCard status={MOCK_STATUS_LAST_FAILED} loading={false} />);
  });

  it("shows error message when last notification failed", () => {
    expect(screen.getByTestId("notifications-last-error")).toBeInTheDocument();
  });

  it("displays the error text", () => {
    expect(screen.getByTestId("notifications-last-error")).toHaveTextContent(
      "Connection timeout"
    );
  });

  it("displays failed count", () => {
    expect(screen.getByTestId("notifications-failed")).toHaveTextContent("3");
  });

  it("displays correct event type for escalation_change", () => {
    expect(screen.getByTestId("notifications-last-event-type")).toHaveTextContent(
      /escalation change/i
    );
  });
});

// ---------------------------------------------------------------------------
// Single provider
// ---------------------------------------------------------------------------

describe("NotificationsStatusCard — single provider", () => {
  it("shows single provider name without comma", () => {
    const status = { ...MOCK_STATUS_ENABLED, providers: ["discord"] };
    render(<NotificationsStatusCard status={status} loading={false} />);
    const providers = screen.getByTestId("notifications-providers");
    expect(providers).toHaveTextContent("discord");
    expect(providers).not.toHaveTextContent(",");
  });
});

// ---------------------------------------------------------------------------
// Heading / label always present
// ---------------------------------------------------------------------------

describe("NotificationsStatusCard — heading", () => {
  it("always shows 'Notifications' label in enabled state", () => {
    render(<NotificationsStatusCard status={MOCK_STATUS_ENABLED} loading={false} />);
    expect(screen.getByText("Notifications")).toBeInTheDocument();
  });

  it("always shows 'Notifications' label in empty state", () => {
    render(<NotificationsStatusCard status={null} loading={false} />);
    expect(screen.getByText("Notifications")).toBeInTheDocument();
  });
});
