import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import IntelligenceSection from "../IntelligenceSection";

// Mock IntelligenceMap to prevent react-leaflet ESM from being parsed by Jest
jest.mock("../IntelligenceMap", () => () => (
  <div data-testid="intelligence-map-stub" />
));

// Mock NotificationsStatusCard to keep test isolation clean
jest.mock("../NotificationsStatusCard", () => ({ status, loading }) => (
  <div data-testid="notifications-status-card-stub" />
));

// Mock LandCoverDistributionCard to keep test isolation clean
jest.mock("../LandCoverDistributionCard", () => ({ data, loading }) => (
  <div data-testid="land-cover-card-stub" />
));

// Mock HistoricalIntelligenceSection to prevent it fetching its own data
jest.mock("../HistoricalIntelligenceSection", () => () => (
  <div data-testid="historical-intelligence-section-stub" />
));

// Mock RegionalRiskSection to prevent it fetching its own data
jest.mock("../RegionalRiskSection", () => () => (
  <div data-testid="regional-risk-section-stub" />
));

// Mock RegionalWeatherSection to prevent it fetching its own data
jest.mock("../RegionalWeatherSection", () => () => (
  <div data-testid="regional-weather-section-stub" />
));

// Mock HighestRiskRegionCard to keep sidebar test isolation
jest.mock("../HighestRiskRegionCard", () => ({ region }) => (
  <div data-testid="highest-risk-region-card-stub" />
));

jest.mock("@/components/investigations/InvestigationsCommandCenterCard", () => () => (
  <div data-testid="investigations-command-center-stub" />
));

jest.mock("@/context/OrganizationContext", () => ({
  useOrganization: () => ({
    selectedOrgId: "org-test-1",
    currentOrganization: { id: "org-test-1", name: "Test Organization", role: "owner" },
    organizations: [{ id: "org-test-1", name: "Test Organization", role: "owner" }],
    setSelectedOrgId: jest.fn(),
    loading: false,
  }),
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

jest.mock("../OperationalStatusCard", () => () => (
  <div data-testid="operational-status-card-stub" />
));

// Mock lib/api to avoid ESM axios resolving in Jest environment
jest.mock("@/lib/api", () => ({
  api: { get: jest.fn() },
  formatApiErrorDetail: (detail) =>
    detail ? String(detail) : "Something went wrong. Please try again.",
}));

// Mock the analytics API functions
jest.mock("@/api/analytics", () => ({
  fetchIntelligenceEvents: jest.fn(),
  fetchIntelligenceSummary: jest.fn(),
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

// Import mocks after jest.mock so we get the mocked versions
const {
  fetchIntelligenceEvents,
  fetchIntelligenceSummary,
  fetchIngestionStatus,
  fetchNotificationsStatus,
  fetchLandCoverDistribution,
  fetchRegionalRisk,
  fetchCommandCenter,
  fetchOperationalStatus,
} = require("@/api/analytics");

const {
  fetchMonitoringAreas,
  fetchMonitoringStatus,
} = require("@/api/monitoringAreas");

const { fetchAlertOverview } = require("@/api/customerAlerts");

const MOCK_SUMMARY = {
  active: 3,
  resolved: 5,
  persistent: 2,
  critical: 1,
  worsening: 1,
  stable: 1,
  improving: 1,
  highest_priority_score: 0.91,
  highest_priority_region: "Carpathian Forest",
};

const MOCK_EVENTS = {
  active: [
    {
      id: "evt-001",
      region: "Carpathian Forest",
      severity: "high",
      trend: "worsening",
      escalation_level: "persistent",
      priority_score: 0.91,
      detection_count: 3,
      current_score: 0.80,
      last_detected_at: "2026-06-13T19:00:00Z",
    },
  ],
  resolved: [],
};

const MOCK_INGESTION_STATUS = {
  scheduler_enabled: true,
  poll_interval_minutes: 60,
  latest_run: null,
  successful_runs: 0,
  failed_runs: 0,
};

const MOCK_NOTIFICATIONS_STATUS = {
  enabled: false,
  providers: [],
  last_notification: null,
  notifications_sent: 0,
  notifications_failed: 0,
};

const MOCK_LAND_COVER = {
  generated_at: "2026-06-10T12:00:00Z",
  distribution: [
    { land_cover: "forest", events: 52 },
    { land_cover: "unknown", events: 121 },
  ],
};

const MOCK_RISK = {
  generated_at: "2026-06-10T12:00:00Z",
  regions: [
    {
      region: "Suceava",
      risk_score: 0.82,
      risk_level: "Extreme",
      change: "up",
      breakdown: {
        current_activity: 0.28,
        historical_activity: 0.20,
        forest: 0.15,
        priority: 0.12,
        escalation: 0.07,
      },
    },
  ],
};

const MOCK_COMMAND_CENTER = {
  generated_at: "2026-06-10T12:00:00Z",
  domains: [],
  incident_aggregation: {},
};

const MOCK_OPERATIONAL_STATUS = {
  geographic_scope: "europe",
  intelligence_cycle_id: "cycle-fixture-1",
  correlation_state: "disabled",
  providers: [],
};

beforeEach(() => {
  jest.clearAllMocks();
  // Default status mocks so they don't interfere with other tests
  fetchIngestionStatus.mockResolvedValue(MOCK_INGESTION_STATUS);
  fetchNotificationsStatus.mockResolvedValue(MOCK_NOTIFICATIONS_STATUS);
  fetchLandCoverDistribution.mockResolvedValue(MOCK_LAND_COVER);
  fetchRegionalRisk.mockResolvedValue(MOCK_RISK);
  fetchCommandCenter.mockResolvedValue(MOCK_COMMAND_CENTER);
  fetchOperationalStatus.mockResolvedValue(MOCK_OPERATIONAL_STATUS);
  fetchMonitoringAreas.mockResolvedValue({ total: 0, items: [] });
  fetchMonitoringStatus.mockResolvedValue({
    monitored_areas: { enabled_count: 0 },
    disturbance_summary: { inside_monitored_area_count: 0, high_critical_investigation_count: 0 },
  });
  fetchAlertOverview.mockResolvedValue(null);
});

describe("IntelligenceSection", () => {
  describe("loading state", () => {
    it("shows loading skeletons before data arrives", async () => {
      // Keep the promise pending so loading stays true
      fetchIntelligenceSummary.mockReturnValue(new Promise(() => {}));
      fetchIntelligenceEvents.mockReturnValue(new Promise(() => {}));
      fetchIngestionStatus.mockReturnValue(new Promise(() => {}));
      fetchNotificationsStatus.mockReturnValue(new Promise(() => {}));
      fetchLandCoverDistribution.mockReturnValue(new Promise(() => {}));
      fetchRegionalRisk.mockReturnValue(new Promise(() => {}));
      fetchCommandCenter.mockReturnValue(new Promise(() => {}));
      fetchOperationalStatus.mockReturnValue(new Promise(() => {}));

      render(<IntelligenceSection />);

      expect(
        screen.getByTestId("intelligence-summary-loading")
      ).toBeInTheDocument();
    });

    it("renders the section wrapper immediately", async () => {
      fetchIntelligenceSummary.mockReturnValue(new Promise(() => {}));
      fetchIntelligenceEvents.mockReturnValue(new Promise(() => {}));
      fetchIngestionStatus.mockReturnValue(new Promise(() => {}));
      fetchNotificationsStatus.mockReturnValue(new Promise(() => {}));
      fetchLandCoverDistribution.mockReturnValue(new Promise(() => {}));
      fetchRegionalRisk.mockReturnValue(new Promise(() => {}));
      fetchCommandCenter.mockReturnValue(new Promise(() => {}));
      fetchOperationalStatus.mockReturnValue(new Promise(() => {}));

      render(<IntelligenceSection />);
      expect(screen.getByTestId("intelligence-section")).toBeInTheDocument();
    });
  });

  describe("error state", () => {
    it("shows error banner when API call fails", async () => {
      fetchIntelligenceSummary.mockRejectedValue(new Error("Network error"));
      fetchIntelligenceEvents.mockRejectedValue(new Error("Network error"));

      render(<IntelligenceSection />);

      await waitFor(() => {
        expect(screen.getByTestId("intelligence-error")).toBeInTheDocument();
      });
    });

    it("shows retry button when an error occurs", async () => {
      fetchIntelligenceSummary.mockRejectedValue(new Error("fail"));
      fetchIntelligenceEvents.mockRejectedValue(new Error("fail"));

      render(<IntelligenceSection />);

      await waitFor(() => {
        expect(screen.getByTestId("intelligence-retry")).toBeInTheDocument();
      });
    });

    it("retries fetch when retry button is clicked", async () => {
      fetchIntelligenceSummary
        .mockRejectedValueOnce(new Error("fail"))
        .mockResolvedValue(MOCK_SUMMARY);
      fetchIntelligenceEvents
        .mockRejectedValueOnce(new Error("fail"))
        .mockResolvedValue(MOCK_EVENTS);

      render(<IntelligenceSection />);

      await waitFor(() => {
        expect(screen.getByTestId("intelligence-retry")).toBeInTheDocument();
      });

      await userEvent.click(screen.getByTestId("intelligence-retry"));

      await waitFor(() => {
        expect(fetchIntelligenceSummary).toHaveBeenCalledTimes(2);
      });
    });

    it("hides error banner after successful retry", async () => {
      fetchIntelligenceSummary
        .mockRejectedValueOnce(new Error("fail"))
        .mockResolvedValue(MOCK_SUMMARY);
      fetchIntelligenceEvents
        .mockRejectedValueOnce(new Error("fail"))
        .mockResolvedValue(MOCK_EVENTS);

      render(<IntelligenceSection />);

      await waitFor(() =>
        expect(screen.getByTestId("intelligence-retry")).toBeInTheDocument()
      );
      await userEvent.click(screen.getByTestId("intelligence-retry"));

      await waitFor(() => {
        expect(screen.queryByTestId("intelligence-error")).not.toBeInTheDocument();
      });
    });
  });

  describe("summary rendering", () => {
    it("renders summary cards after successful fetch", async () => {
      fetchIntelligenceSummary.mockResolvedValue(MOCK_SUMMARY);
      fetchIntelligenceEvents.mockResolvedValue(MOCK_EVENTS);

      render(<IntelligenceSection />);

      await waitFor(() => {
        expect(
          screen.getByTestId("intelligence-summary-cards")
        ).toBeInTheDocument();
      });
    });

    it("shows correct active count from summary", async () => {
      fetchIntelligenceSummary.mockResolvedValue(MOCK_SUMMARY);
      fetchIntelligenceEvents.mockResolvedValue(MOCK_EVENTS);

      render(<IntelligenceSection />);

      await waitFor(() => {
        expect(screen.getByTestId("intel-stat-active")).toHaveTextContent("3");
      });
    });
  });

  describe("command center rendering", () => {
    it("renders command center after successful fetch", async () => {
      fetchIntelligenceSummary.mockResolvedValue(MOCK_SUMMARY);
      fetchIntelligenceEvents.mockResolvedValue(MOCK_EVENTS);

      render(<IntelligenceSection />);

      await waitFor(() => {
        expect(screen.getByTestId("intelligence-command-center")).toBeInTheDocument();
      });
    });
  });

  describe("active event rendering", () => {
    it("renders event rows from API response", async () => {
      fetchIntelligenceSummary.mockResolvedValue(MOCK_SUMMARY);
      fetchIntelligenceEvents.mockResolvedValue(MOCK_EVENTS);

      render(<IntelligenceSection />);

      await waitFor(() => {
        expect(
          screen.getByTestId("intelligence-event-row-evt-001")
        ).toBeInTheDocument();
      });
    });

    it("shows empty state when no active events returned", async () => {
      fetchIntelligenceSummary.mockResolvedValue({
        ...MOCK_SUMMARY,
        active: 0,
        highest_priority_score: null,
        highest_priority_region: null,
      });
      fetchIntelligenceEvents.mockResolvedValue({ active: [], resolved: [] });

      render(<IntelligenceSection />);

      await waitFor(() => {
        expect(
          screen.getByTestId("intelligence-events-empty")
        ).toBeInTheDocument();
      });
    });
  });
});
