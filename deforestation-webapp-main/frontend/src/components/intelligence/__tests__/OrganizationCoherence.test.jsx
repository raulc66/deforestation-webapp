import { render, screen, waitFor } from "@testing-library/react";
import IntelligenceSection from "../IntelligenceSection";

jest.mock("../IntelligenceMap", () => () => (
  <div data-testid="intelligence-map-mock" />
));

jest.mock("../NotificationsStatusCard", () => () => null);
jest.mock("../LandCoverDistributionCard", () => () => null);
jest.mock("../HistoricalIntelligenceSection", () => () => null);
jest.mock("../RegionalRiskSection", () => () => null);
jest.mock("../RegionalWeatherSection", () => () => null);
jest.mock("@/components/investigations/InvestigationsCommandCenterCard", () => () => null);
jest.mock("../OperationalStatusCard", () => () => null);

jest.mock("@/lib/api", () => ({
  api: { get: jest.fn() },
  formatApiErrorDetail: (d) => (typeof d === "string" ? d : null),
}));

jest.mock("@/api/analytics", () => ({
  fetchIntelligenceSummary: jest.fn(),
  fetchIntelligenceEvents: jest.fn(),
  fetchIngestionStatus: jest.fn(),
  fetchNotificationsStatus: jest.fn(),
  fetchLandCoverDistribution: jest.fn(),
  fetchRegionalRisk: jest.fn(),
  fetchCommandCenter: jest.fn(),
  fetchOperationalStatus: jest.fn(),
}));

jest.mock("@/api/monitoringAreas", () => ({
  fetchMonitoringAreas: jest.fn(),
  fetchMonitoringStatus: jest.fn(),
}));

jest.mock("@/api/customerAlerts", () => ({
  fetchAlertOverview: jest.fn(),
}));

const mockOrgState = {
  selectedOrgId: "org-a",
  organizationVersion: 1,
  setSelectedOrgId: jest.fn(),
};

jest.mock("@/context/OrganizationContext", () => ({
  useOrganization: () => mockOrgState,
}));

jest.mock("@/context/TrialContext", () => ({
  useTrial: () => ({
    status: null,
    isTrial: false,
    isExpired: false,
    startTrial: jest.fn(),
    reload: jest.fn(),
  }),
}));

jest.mock("react-router-dom", () => ({
  ...jest.requireActual("react-router-dom"),
  useNavigate: () => jest.fn(),
}));

const analytics = require("@/api/analytics");
const monitoring = require("@/api/monitoringAreas");
const customerAlerts = require("@/api/customerAlerts");

describe("IntelligenceSection organization coherence", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockOrgState.selectedOrgId = "org-a";
    mockOrgState.organizationVersion = 1;
    analytics.fetchIntelligenceSummary.mockResolvedValue({ active_count: 1 });
    analytics.fetchIntelligenceEvents.mockResolvedValue({ active: [] });
    analytics.fetchIngestionStatus.mockResolvedValue({});
    analytics.fetchNotificationsStatus.mockResolvedValue({});
    analytics.fetchLandCoverDistribution.mockResolvedValue({});
    analytics.fetchRegionalRisk.mockResolvedValue({});
    analytics.fetchCommandCenter.mockResolvedValue({ intelligence_evidence: { items: [] } });
    analytics.fetchOperationalStatus.mockResolvedValue({});
    monitoring.fetchMonitoringAreas.mockResolvedValue({
      items: [{ id: "area-a", name: "Org A Forest", intelligence_summary: { active_intelligence_count: 2 } }],
    });
    monitoring.fetchMonitoringStatus.mockResolvedValue({ organization: { id: "org-a", name: "Org A" } });
    customerAlerts.fetchAlertOverview.mockResolvedValue({
      alert_delivery_available: true,
      can_manage: true,
      active_policy_count: 1,
      enabled_channel_count: 1,
      sent_count: 1,
      attention_count: 0,
      channel_states: [],
      recent_deliveries: [],
    });
  });

  const renderSection = () => render(<IntelligenceSection />);

  it("loads org-a monitoring data on mount", async () => {
    renderSection();
    await waitFor(() => {
      expect(monitoring.fetchMonitoringAreas).toHaveBeenCalled();
    });
    expect(await screen.findByText("Org A Forest")).toBeInTheDocument();
  });

  it("reloads when switching from org A to org B", async () => {
    const { rerender } = renderSection();
    await waitFor(() => expect(monitoring.fetchMonitoringAreas).toHaveBeenCalledTimes(1));

    monitoring.fetchMonitoringAreas.mockResolvedValue({
      items: [{ id: "area-b", name: "Org B Forest", intelligence_summary: { active_intelligence_count: 5 } }],
    });
    monitoring.fetchMonitoringStatus.mockResolvedValue({ organization: { id: "org-b", name: "Org B" } });
    mockOrgState.selectedOrgId = "org-b";
    mockOrgState.organizationVersion = 2;
    rerender(<IntelligenceSection />);

    await waitFor(() => expect(monitoring.fetchMonitoringAreas).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Org B Forest")).toBeInTheDocument();
    expect(screen.queryByText("Org A Forest")).not.toBeInTheDocument();
  });
});
