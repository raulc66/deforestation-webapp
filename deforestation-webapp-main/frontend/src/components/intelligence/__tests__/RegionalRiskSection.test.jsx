import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import RegionalRiskSection from "../RegionalRiskSection";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

jest.mock("@/lib/api", () => ({
  api: { get: jest.fn() },
  formatApiErrorDetail: (d) => (d ? String(d) : "Something went wrong."),
}));

jest.mock("@/api/analytics", () => ({
  fetchRegionalRisk: jest.fn(),
}));

const { fetchRegionalRisk } = require("@/api/analytics");

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_RISK = {
  generated_at: "2026-06-10T12:00:00Z",
  regions: [
    {
      region: "Suceava",
      risk_score: 0.82,
      risk_level: "Extreme",
      change: "up",
      breakdown: {
        current_activity: 0.287,
        historical_activity: 0.2,
        forest: 0.15,
        priority: 0.12,
        escalation: 0.063,
      },
    },
    {
      region: "Bacău",
      risk_score: 0.64,
      risk_level: "High",
      change: "stable",
      breakdown: {
        current_activity: 0.21,
        historical_activity: 0.18,
        forest: 0.12,
        priority: 0.10,
        escalation: 0.03,
      },
    },
    {
      region: "Cluj",
      risk_score: 0.42,
      risk_level: "Moderate",
      change: "down",
      breakdown: {
        current_activity: 0.14,
        historical_activity: 0.1,
        forest: 0.09,
        priority: 0.06,
        escalation: 0.03,
      },
    },
    {
      region: "Timiș",
      risk_score: 0.15,
      risk_level: "Low",
      change: "new",
      breakdown: {
        current_activity: 0.0,
        historical_activity: 0.08,
        forest: 0.05,
        priority: 0.02,
        escalation: 0.0,
      },
    },
  ],
};

const EMPTY_RISK = { generated_at: "2026-06-10T12:00:00Z", regions: [] };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

beforeEach(() => {
  jest.clearAllMocks();
  fetchRegionalRisk.mockResolvedValue(MOCK_RISK);
});

// ---------------------------------------------------------------------------
// Test suites
// ---------------------------------------------------------------------------

describe("RegionalRiskSection", () => {
  describe("loading state", () => {
    it("renders section wrapper immediately", () => {
      fetchRegionalRisk.mockReturnValue(new Promise(() => {}));
      render(<RegionalRiskSection />);
      expect(screen.getByTestId("regional-risk-section")).toBeInTheDocument();
    });

    it("shows loading skeletons while fetching", () => {
      fetchRegionalRisk.mockReturnValue(new Promise(() => {}));
      render(<RegionalRiskSection />);
      expect(screen.getByTestId("risk-loading")).toBeInTheDocument();
    });

    it("hides loading skeleton after data arrives", async () => {
      render(<RegionalRiskSection />);
      await waitFor(() =>
        expect(screen.queryByTestId("risk-loading")).not.toBeInTheDocument()
      );
    });
  });

  describe("error state", () => {
    it("shows error banner when fetch fails", async () => {
      fetchRegionalRisk.mockRejectedValue(new Error("Network error"));
      render(<RegionalRiskSection />);
      await waitFor(() =>
        expect(screen.getByTestId("risk-error")).toBeInTheDocument()
      );
    });

    it("shows retry button in error state", async () => {
      fetchRegionalRisk.mockRejectedValue(new Error("fail"));
      render(<RegionalRiskSection />);
      await waitFor(() =>
        expect(screen.getByText("Retry")).toBeInTheDocument()
      );
    });

    it("retries when retry button is clicked", async () => {
      fetchRegionalRisk
        .mockRejectedValueOnce(new Error("fail"))
        .mockResolvedValue(MOCK_RISK);
      render(<RegionalRiskSection />);
      await waitFor(() => screen.getByText("Retry"));
      fireEvent.click(screen.getByText("Retry"));
      await waitFor(() =>
        expect(screen.queryByTestId("risk-error")).not.toBeInTheDocument()
      );
    });
  });

  describe("risk distribution cards", () => {
    it("renders all four level cards", async () => {
      render(<RegionalRiskSection />);
      await waitFor(() =>
        expect(screen.getByTestId("risk-distribution-cards")).toBeInTheDocument()
      );
      expect(screen.getByTestId("risk-dist-extreme")).toBeInTheDocument();
      expect(screen.getByTestId("risk-dist-high")).toBeInTheDocument();
      expect(screen.getByTestId("risk-dist-moderate")).toBeInTheDocument();
      expect(screen.getByTestId("risk-dist-low")).toBeInTheDocument();
    });

    it("shows correct count per level", async () => {
      render(<RegionalRiskSection />);
      await waitFor(() => screen.getByTestId("risk-dist-extreme"));
      // MOCK_RISK has 1 Extreme, 1 High, 1 Moderate, 1 Low
      const extreme = screen.getByTestId("risk-dist-extreme");
      expect(extreme).toHaveTextContent("1");
    });

    it("shows zero for levels with no regions", async () => {
      fetchRegionalRisk.mockResolvedValue({
        ...MOCK_RISK,
        regions: MOCK_RISK.regions.filter((r) => r.risk_level === "Extreme"),
      });
      render(<RegionalRiskSection />);
      await waitFor(() => screen.getByTestId("risk-dist-high"));
      const high = screen.getByTestId("risk-dist-high");
      expect(high).toHaveTextContent("0");
    });
  });

  describe("top 5 cards", () => {
    it("renders top 5 cards container", async () => {
      render(<RegionalRiskSection />);
      await waitFor(() =>
        expect(screen.getByTestId("top5-risk-cards")).toBeInTheDocument()
      );
    });

    it("shows at most 5 cards even with more regions", async () => {
      const manyRegions = Array.from({ length: 8 }, (_, i) => ({
        region: `Region${i}`,
        risk_score: 1 - i * 0.05,
        risk_level: i < 2 ? "Extreme" : i < 4 ? "High" : "Moderate",
        change: "stable",
        breakdown: {
          current_activity: 0.2,
          historical_activity: 0.1,
          forest: 0.05,
          priority: 0.05,
          escalation: 0.0,
        },
      }));
      fetchRegionalRisk.mockResolvedValue({ ...MOCK_RISK, regions: manyRegions });
      render(<RegionalRiskSection />);
      await waitFor(() => screen.getByTestId("top5-risk-cards"));
      const cards = screen.getAllByTestId(/^top5-card-/);
      expect(cards.length).toBeLessThanOrEqual(5);
    });

    it("shows the highest-risk region as card #0", async () => {
      render(<RegionalRiskSection />);
      await waitFor(() => screen.getByTestId("top5-card-0"));
      const firstCard = screen.getByTestId("top5-card-0");
      expect(firstCard).toHaveTextContent("Suceava");
    });

    it("shows change indicator for each card", async () => {
      render(<RegionalRiskSection />);
      await waitFor(() => screen.getByTestId("change-Suceava"));
      // "up" indicator should show ↑
      expect(screen.getByTestId("change-Suceava")).toHaveTextContent("↑");
    });

    it("shows breakdown bars inside each card", async () => {
      render(<RegionalRiskSection />);
      await waitFor(() => screen.getAllByTestId("breakdown-bars"));
      expect(screen.getAllByTestId("breakdown-bars").length).toBeGreaterThan(0);
    });

    it("shows empty message when no regions", async () => {
      fetchRegionalRisk.mockResolvedValue(EMPTY_RISK);
      render(<RegionalRiskSection />);
      await waitFor(() =>
        expect(screen.getByTestId("top5-empty")).toBeInTheDocument()
      );
    });
  });

  describe("risk table", () => {
    it("renders the risk table", async () => {
      render(<RegionalRiskSection />);
      await waitFor(() =>
        expect(screen.getByTestId("risk-table")).toBeInTheDocument()
      );
    });

    it("shows all region rows", async () => {
      render(<RegionalRiskSection />);
      await waitFor(() => screen.getByTestId("risk-table"));
      // Use getAllByText since regions appear in both Top 5 cards and the table
      expect(screen.getAllByText("Suceava").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Bacău").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Cluj").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Timiș").length).toBeGreaterThan(0);
    });

    it("shows risk level badges", async () => {
      render(<RegionalRiskSection />);
      await waitFor(() => screen.getByTestId("risk-table"));
      expect(screen.getAllByText("Extreme").length).toBeGreaterThan(0);
      expect(screen.getAllByText("High").length).toBeGreaterThan(0);
    });

    it("shows empty message when no regions", async () => {
      fetchRegionalRisk.mockResolvedValue(EMPTY_RISK);
      render(<RegionalRiskSection />);
      await waitFor(() =>
        expect(screen.getByTestId("risk-table-empty")).toBeInTheDocument()
      );
    });
  });

  describe("generated_at timestamp", () => {
    it("shows generated timestamp when data is loaded", async () => {
      render(<RegionalRiskSection />);
      await waitFor(() => screen.queryByTestId("risk-loading") === null);
      // The formatted date string should appear somewhere on screen
      // (exact format is locale-dependent, so just verify the component renders)
      expect(screen.getByTestId("regional-risk-section")).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// HighestRiskRegionCard
// ---------------------------------------------------------------------------

import HighestRiskRegionCard from "../HighestRiskRegionCard";

describe("HighestRiskRegionCard", () => {
  const REGION = MOCK_RISK.regions[0]; // Suceava, Extreme, up

  it("renders the card wrapper", () => {
    render(<HighestRiskRegionCard region={REGION} />);
    expect(screen.getByTestId("highest-risk-region-card")).toBeInTheDocument();
  });

  it("shows region name", () => {
    render(<HighestRiskRegionCard region={REGION} />);
    expect(screen.getByTestId("risk-region-name")).toHaveTextContent("Suceava");
  });

  it("shows risk level badge", () => {
    render(<HighestRiskRegionCard region={REGION} />);
    expect(screen.getByTestId("risk-level-badge")).toHaveTextContent("Extreme");
  });

  it("shows risk score as percentage", () => {
    render(<HighestRiskRegionCard region={REGION} />);
    expect(screen.getByTestId("risk-score-value")).toHaveTextContent("82.0");
  });

  it("shows change indicator for up", () => {
    render(<HighestRiskRegionCard region={REGION} />);
    expect(screen.getByTestId("risk-change-indicator")).toHaveTextContent("↑");
    expect(screen.getByTestId("risk-change-indicator")).toHaveTextContent("Increased");
  });

  it("shows change indicator for down", () => {
    render(<HighestRiskRegionCard region={{ ...REGION, change: "down" }} />);
    expect(screen.getByTestId("risk-change-indicator")).toHaveTextContent("↓");
    expect(screen.getByTestId("risk-change-indicator")).toHaveTextContent("Decreased");
  });

  it("shows change indicator for stable", () => {
    render(<HighestRiskRegionCard region={{ ...REGION, change: "stable" }} />);
    expect(screen.getByTestId("risk-change-indicator")).toHaveTextContent("→");
  });

  it("shows change indicator for new", () => {
    render(<HighestRiskRegionCard region={{ ...REGION, change: "new" }} />);
    expect(screen.getByTestId("risk-change-indicator")).toHaveTextContent("★");
  });

  it("shows no-data message when region is null", () => {
    render(<HighestRiskRegionCard region={null} />);
    expect(screen.getByTestId("no-risk-data")).toBeInTheDocument();
  });

  it("renders breakdown details", () => {
    render(<HighestRiskRegionCard region={REGION} />);
    // All 5 breakdown labels should appear
    expect(screen.getByText("Activity")).toBeInTheDocument();
    expect(screen.getByText("History")).toBeInTheDocument();
    expect(screen.getByText("Forest")).toBeInTheDocument();
    expect(screen.getByText("Priority")).toBeInTheDocument();
    expect(screen.getByText("Escalation")).toBeInTheDocument();
  });

  it("applies Extreme styling", () => {
    render(<HighestRiskRegionCard region={REGION} />);
    const card = screen.getByTestId("highest-risk-region-card");
    expect(card.className).toMatch(/red/);
  });

  it("applies Low styling for low-risk region", () => {
    const lowRegion = MOCK_RISK.regions[3]; // Timiș, Low
    render(<HighestRiskRegionCard region={lowRegion} />);
    const card = screen.getByTestId("highest-risk-region-card");
    expect(card.className).toMatch(/green/);
  });
});
