import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import TrialStatusBar from "../TrialStatusBar";
import TrialOnboarding from "../TrialOnboarding";
import TrialConversionCta from "../TrialConversionCta";
import TrialSetupPage from "@/pages/TrialSetupPage";

const mockStartTrial = jest.fn();
const mockReloadTrial = jest.fn();
const mockOrgReload = jest.fn();
let mockTrialState = {
  status: null,
  isTrial: false,
  isExpired: false,
  startTrial: (...args) => mockStartTrial(...args),
  reload: (...args) => mockReloadTrial(...args),
};

jest.mock("@/context/TrialContext", () => ({
  useTrial: () => mockTrialState,
}));

jest.mock("@/context/OrganizationContext", () => ({
  useOrganization: () => ({
    currentOrganization: { id: "org-1", name: "Personal Workspace" },
    reload: (...args) => mockOrgReload(...args),
  }),
}));

jest.mock("@/components/layout/AppLayout", () => ({ children }) => (
  <div data-testid="app-layout">{children}</div>
));

jest.mock("@/api/monitoringAreas", () => ({
  createMonitoringArea: jest.fn(),
}));

jest.mock("@/api/organizations", () => ({
  updateOrganization: jest.fn(),
}));

const areasApi = require("@/api/monitoringAreas");
const orgsApi = require("@/api/organizations");

function trialStatus(overrides = {}) {
  return {
    organization_id: "org-1",
    organization_name: "Carpathian Watch",
    commercial_lifecycle: "trial",
    days_remaining: 12,
    usage: { monitored_areas: 1, monitored_area_limit: 2 },
    onboarding: { has_monitored_area: false, complete: false },
    upgrade_cta: { visible: false },
    alert_delivery_mode: "account_email",
    ...overrides,
  };
}

describe("TrialStatusBar", () => {
  beforeEach(() => {
    mockTrialState = {
      status: trialStatus(),
      isTrial: true,
      isExpired: false,
      startTrial: mockStartTrial,
      reload: mockReloadTrial,
    };
  });

  it("shows remaining days and usage", () => {
    render(
      <MemoryRouter>
        <TrialStatusBar />
      </MemoryRouter>
    );
    expect(screen.getByTestId("trial-status-label")).toHaveTextContent("Trial · 12 days remaining");
    expect(screen.getByTestId("trial-usage-summary")).toHaveTextContent("1 / 2 monitored forests");
  });

  it("shows expiration continue CTA", () => {
    mockTrialState = {
      ...mockTrialState,
      status: trialStatus({ commercial_lifecycle: "trial_expired", days_remaining: 0 }),
      isTrial: false,
      isExpired: true,
    };
    render(
      <MemoryRouter>
        <TrialStatusBar />
      </MemoryRouter>
    );
    expect(screen.getByTestId("trial-status-label")).toHaveTextContent("Trial ended");
    expect(screen.getByTestId("trial-continue-cta")).toHaveAttribute("href", "/billing");
  });
});

describe("TrialOnboarding", () => {
  it("prompts for a monitored area during trial setup", () => {
    render(
      <MemoryRouter>
        <TrialOnboarding status={trialStatus()} />
      </MemoryRouter>
    );
    expect(screen.getByTestId("trial-onboarding")).toHaveTextContent(/Add a forest to monitor/i);
    expect(screen.getByTestId("trial-onboarding-continue")).toHaveAttribute("href", "/trial/setup");
  });

  it("hides once a monitored area exists", () => {
    const { container } = render(
      <TrialOnboarding
        status={trialStatus({ onboarding: { has_monitored_area: true, complete: true } })}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });
});

describe("TrialConversionCta", () => {
  it("uses contextual copy without dominating the page", () => {
    render(
      <MemoryRouter>
        <TrialConversionCta moment="investigation" />
      </MemoryRouter>
    );
    expect(screen.getByTestId("trial-conversion-investigation")).toHaveTextContent(
      /Monitor a forest like this/i
    );
    expect(screen.getByTestId("trial-conversion-cta")).toHaveAttribute("href", "/register?from=demo");
  });
});

describe("TrialSetupPage", () => {
  beforeEach(() => {
    mockStartTrial.mockReset();
    mockReloadTrial.mockReset();
    mockOrgReload.mockReset();
    areasApi.createMonitoringArea.mockReset();
    orgsApi.updateOrganization.mockReset();
    mockStartTrial.mockResolvedValue(trialStatus());
    mockReloadTrial.mockResolvedValue(trialStatus({ onboarding: { complete: true } }));
    mockOrgReload.mockResolvedValue(undefined);
    areasApi.createMonitoringArea.mockResolvedValue({ id: "area-1" });
    orgsApi.updateOrganization.mockResolvedValue({ id: "org-1" });
    mockTrialState = {
      status: trialStatus(),
      isTrial: true,
      isExpired: false,
      startTrial: mockStartTrial,
      reload: mockReloadTrial,
    };
  });

  it("creates a real monitored area through the existing API", async () => {
    render(
      <MemoryRouter>
        <TrialSetupPage />
      </MemoryRouter>
    );
    fireEvent.change(screen.getByTestId("trial-org-name"), {
      target: { value: "Carpathian Watch" },
    });
    fireEvent.change(screen.getByTestId("trial-area-name"), {
      target: { value: "Harghita stand" },
    });
    fireEvent.click(screen.getByTestId("trial-setup-submit"));
    await waitFor(() => {
      expect(areasApi.createMonitoringArea).toHaveBeenCalled();
    });
    const payload = areasApi.createMonitoringArea.mock.calls[0][0];
    expect(payload.geometry.type).toBe("Polygon");
    expect(payload.name).toBe("Harghita stand");
    expect(screen.getByTestId("trial-setup-briefing")).toHaveTextContent(/account email/i);
    expect(screen.getByTestId("trial-workspace-notice")).toHaveTextContent(/left demonstration data/i);
  });

  it("shows expiration without fabricating a subscription", () => {
    mockTrialState = {
      status: trialStatus({ commercial_lifecycle: "trial_expired" }),
      isTrial: false,
      isExpired: true,
      startTrial: mockStartTrial,
      reload: mockReloadTrial,
    };
    render(
      <MemoryRouter>
        <TrialSetupPage />
      </MemoryRouter>
    );
    expect(screen.getByTestId("trial-setup-page")).toHaveTextContent(/Continue monitoring/i);
    expect(screen.queryByTestId("trial-setup-form")).not.toBeInTheDocument();
  });
});
