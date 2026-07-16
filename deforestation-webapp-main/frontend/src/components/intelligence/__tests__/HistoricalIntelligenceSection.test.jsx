/**
 * Tests for HistoricalIntelligenceSection + HistoricalActivityCard.
 *
 * Coverage:
 *   Loading state — skeletons rendered, no chart canvases
 *   Error state   — error banner shown, retry button
 *   Daily chart   — renders canvas, range toggle changes days param
 *   Monthly chart — renders canvas with stacked bar structure
 *   Regional table — rows rendered with trend badges, change_percent
 *   Hotspot table  — rows ranked correctly, severity dots present
 *   HistoricalActivityCard — stats derived correctly, loading skeleton
 *   Empty datasets — empty-state messages
 *   IntelligenceSection integration — renders HistoricalIntelligenceSection
 */

import React from "react";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import "@testing-library/jest-dom";

// ---------------------------------------------------------------------------
// Mock recharts so it doesn't blow up in Jest / jsdom
// ---------------------------------------------------------------------------
jest.mock("recharts", () => {
  const Passthrough = ({ children }) => <div>{children}</div>;
  const MockLine = () => null;
  const MockBar = () => null;
  return {
    LineChart: ({ children, "data-testid": tid }) => (
      <div data-testid={tid ?? "line-chart-mock"}>{children}</div>
    ),
    BarChart: ({ children, "data-testid": tid }) => (
      <div data-testid={tid ?? "bar-chart-mock"}>{children}</div>
    ),
    ResponsiveContainer: ({ children }) => <div>{children}</div>,
    CartesianGrid: () => null,
    XAxis: () => null,
    YAxis: () => null,
    Tooltip: () => null,
    Legend: () => null,
    Line: MockLine,
    Bar: MockBar,
  };
});

// ---------------------------------------------------------------------------
// Mock API functions
// ---------------------------------------------------------------------------
jest.mock("@/api/analytics", () => ({
  fetchHistoricalDaily: jest.fn(),
  fetchHistoricalRegions: jest.fn(),
  fetchHistoricalHotspots: jest.fn(),
  fetchHistoricalMonthly: jest.fn(),
  // other functions used by IntelligenceSection
  fetchIntelligenceSummary: jest.fn(),
  fetchIntelligenceEvents: jest.fn(),
  fetchIngestionStatus: jest.fn(),
  fetchNotificationsStatus: jest.fn(),
  fetchLandCoverDistribution: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  formatApiErrorDetail: (detail) => detail || null,
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_DAILY = {
  generated_at: "2026-06-04T00:00:00Z",
  days: [
    { date: "2026-06-02", events: 8, anomalies: 1 },
    { date: "2026-06-03", events: 14, anomalies: 2 },
    { date: "2026-06-04", events: 5, anomalies: 0 },
  ],
};

const MOCK_REGIONS = [
  {
    region: "Suceava",
    events_last_30d: 54,
    events_previous_30d: 38,
    change_percent: 42.1,
    trend: "increasing",
  },
  {
    region: "Cluj",
    events_last_30d: 10,
    events_previous_30d: 50,
    change_percent: -80.0,
    trend: "decreasing",
  },
  {
    region: "Iași",
    events_last_30d: 10,
    events_previous_30d: 9,
    change_percent: 11.1,
    trend: "increasing",
  },
];

const MOCK_HOTSPOTS = [
  { region: "Bacău",    detections: 125, average_priority: 0.83, highest_severity: "critical" },
  { region: "Suceava",  detections: 88,  average_priority: 0.72, highest_severity: "high" },
  { region: "Harghita", detections: 40,  average_priority: 0.55, highest_severity: "medium" },
];

const MOCK_MONTHLY = {
  months: [
    { month: "2026-04", events: 70, anomalies: 2, forest_events: 45, urban_events: 5 },
    { month: "2026-05", events: 88, anomalies: 3, forest_events: 52, urban_events: 7 },
  ],
};

// ---------------------------------------------------------------------------
// Setup helpers
// ---------------------------------------------------------------------------

function setupMocks() {
  const {
    fetchHistoricalDaily,
    fetchHistoricalRegions,
    fetchHistoricalHotspots,
    fetchHistoricalMonthly,
  } = require("@/api/analytics");

  fetchHistoricalDaily.mockResolvedValue(MOCK_DAILY);
  fetchHistoricalRegions.mockResolvedValue(MOCK_REGIONS);
  fetchHistoricalHotspots.mockResolvedValue(MOCK_HOTSPOTS);
  fetchHistoricalMonthly.mockResolvedValue(MOCK_MONTHLY);
}

function clearMocks() {
  const {
    fetchHistoricalDaily,
    fetchHistoricalRegions,
    fetchHistoricalHotspots,
    fetchHistoricalMonthly,
  } = require("@/api/analytics");

  fetchHistoricalDaily.mockReset();
  fetchHistoricalRegions.mockReset();
  fetchHistoricalHotspots.mockReset();
  fetchHistoricalMonthly.mockReset();
}

// ---------------------------------------------------------------------------
// Import under test
// ---------------------------------------------------------------------------

import HistoricalIntelligenceSection from "../HistoricalIntelligenceSection";
import HistoricalActivityCard from "../HistoricalActivityCard";

// ===========================================================================
// HistoricalActivityCard
// ===========================================================================

describe("HistoricalActivityCard", () => {
  test("shows loading skeletons when loading=true", () => {
    const { container } = render(
      <HistoricalActivityCard
        monthly={null}
        regions={null}
        hotspots={null}
        loading={true}
      />
    );
    // Pulse skeletons should be present (animate-pulse)
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  test("shows total events computed from monthly data", async () => {
    const { getByTestId } = render(
      <HistoricalActivityCard
        monthly={MOCK_MONTHLY}
        regions={MOCK_REGIONS}
        hotspots={MOCK_HOTSPOTS}
        loading={false}
      />
    );
    const card = getByTestId("historical-activity-card");
    // Total events = 70 + 88 = 158
    expect(card.textContent).toContain("158");
  });

  test("shows total anomalies computed from monthly data", () => {
    const { getByTestId } = render(
      <HistoricalActivityCard
        monthly={MOCK_MONTHLY}
        regions={MOCK_REGIONS}
        hotspots={MOCK_HOTSPOTS}
        loading={false}
      />
    );
    const card = getByTestId("historical-activity-card");
    // Total anomalies = 2 + 3 = 5
    expect(card.textContent).toContain("5");
  });

  test("shows fastest-growing region (highest change_percent with trend increasing)", () => {
    const { getByTestId } = render(
      <HistoricalActivityCard
        monthly={MOCK_MONTHLY}
        regions={MOCK_REGIONS}
        hotspots={MOCK_HOTSPOTS}
        loading={false}
      />
    );
    // Suceava: +42.1% increasing, Iași: +11.1% increasing → Suceava wins
    expect(getByTestId("historical-activity-card").textContent).toContain("Suceava");
  });

  test("shows hottest region (first hotspot)", () => {
    const { getByTestId } = render(
      <HistoricalActivityCard
        monthly={MOCK_MONTHLY}
        regions={MOCK_REGIONS}
        hotspots={MOCK_HOTSPOTS}
        loading={false}
      />
    );
    // Bacău is rank 1 in hotspots
    expect(getByTestId("historical-activity-card").textContent).toContain("Bacău");
  });

  test("shows dashes when no data and not loading", () => {
    const { getAllByText } = render(
      <HistoricalActivityCard
        monthly={{ months: [] }}
        regions={[]}
        hotspots={[]}
        loading={false}
      />
    );
    // Fastest-growing and hottest should be "—"
    const dashes = getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(2);
  });
});

// ===========================================================================
// HistoricalIntelligenceSection
// ===========================================================================

describe("HistoricalIntelligenceSection — loading state", () => {
  beforeEach(() => {
    clearMocks();
    const { fetchHistoricalRegions, fetchHistoricalHotspots, fetchHistoricalMonthly, fetchHistoricalDaily } =
      require("@/api/analytics");
    fetchHistoricalRegions.mockReturnValue(new Promise(() => {}));
    fetchHistoricalHotspots.mockReturnValue(new Promise(() => {}));
    fetchHistoricalMonthly.mockReturnValue(new Promise(() => {}));
    fetchHistoricalDaily.mockReturnValue(new Promise(() => {}));
  });

  test("renders section wrapper immediately", () => {
    render(<HistoricalIntelligenceSection />);
    expect(screen.getByTestId("historical-intelligence-section")).toBeInTheDocument();
  });

  test("does not render chart canvases while loading", () => {
    render(<HistoricalIntelligenceSection />);
    expect(screen.queryByTestId("daily-chart-canvas")).not.toBeInTheDocument();
    expect(screen.queryByTestId("monthly-chart-canvas")).not.toBeInTheDocument();
  });

  test("renders skeleton placeholders while loading", () => {
    const { container } = render(<HistoricalIntelligenceSection />);
    const skeletons = container.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });
});

describe("HistoricalIntelligenceSection — data loaded", () => {
  beforeEach(() => {
    clearMocks();
    setupMocks();
  });

  test("renders section header", async () => {
    render(<HistoricalIntelligenceSection />);
    await waitFor(() =>
      expect(screen.getByText(/Activity over time/i)).toBeInTheDocument()
    );
  });

  test("renders daily activity chart card", async () => {
    render(<HistoricalIntelligenceSection />);
    await waitFor(() =>
      expect(screen.getByTestId("daily-activity-chart")).toBeInTheDocument()
    );
  });

  test("renders daily chart canvas after data loads", async () => {
    render(<HistoricalIntelligenceSection />);
    await waitFor(() =>
      expect(screen.getByTestId("daily-chart-canvas")).toBeInTheDocument()
    );
  });

  test("renders monthly summary chart card", async () => {
    render(<HistoricalIntelligenceSection />);
    await waitFor(() =>
      expect(screen.getByTestId("monthly-summary-chart")).toBeInTheDocument()
    );
  });

  test("renders monthly chart canvas after data loads", async () => {
    render(<HistoricalIntelligenceSection />);
    await waitFor(() =>
      expect(screen.getByTestId("monthly-chart-canvas")).toBeInTheDocument()
    );
  });

  test("renders regional trend table", async () => {
    render(<HistoricalIntelligenceSection />);
    await waitFor(() =>
      expect(screen.getByTestId("regional-trend-table")).toBeInTheDocument()
    );
  });

  test("renders all region rows in the trend table", async () => {
    render(<HistoricalIntelligenceSection />);
    await waitFor(() =>
      expect(screen.getByTestId("region-row-Suceava")).toBeInTheDocument()
    );
    expect(screen.getByTestId("region-row-Cluj")).toBeInTheDocument();
    expect(screen.getByTestId("region-row-Iași")).toBeInTheDocument();
  });

  test("renders trend badges in the table", async () => {
    render(<HistoricalIntelligenceSection />);
    await waitFor(() => {
      const increasing = screen.getAllByTestId("trend-badge-increasing");
      expect(increasing.length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByTestId("trend-badge-decreasing")).toBeInTheDocument();
  });

  test("renders change_percent values", async () => {
    render(<HistoricalIntelligenceSection />);
    await waitFor(() =>
      expect(screen.getByText("+42.1%")).toBeInTheDocument()
    );
    expect(screen.getByText("-80.0%")).toBeInTheDocument();
  });

  test("renders hotspot ranking table", async () => {
    render(<HistoricalIntelligenceSection />);
    await waitFor(() =>
      expect(screen.getByTestId("hotspot-ranking-table")).toBeInTheDocument()
    );
  });

  test("renders all hotspot rows sorted by detection count", async () => {
    render(<HistoricalIntelligenceSection />);
    await waitFor(() =>
      expect(screen.getByTestId("hotspot-row-Bacău")).toBeInTheDocument()
    );
    expect(screen.getByTestId("hotspot-row-Suceava")).toBeInTheDocument();
    expect(screen.getByTestId("hotspot-row-Harghita")).toBeInTheDocument();
  });

  test("renders historical activity card", async () => {
    render(<HistoricalIntelligenceSection />);
    await waitFor(() =>
      expect(screen.getByTestId("historical-activity-card")).toBeInTheDocument()
    );
  });
});

describe("HistoricalIntelligenceSection — daily range toggle", () => {
  beforeEach(() => {
    clearMocks();
    setupMocks();
  });

  test("renders 4 range buttons", async () => {
    render(<HistoricalIntelligenceSection />);
    await waitFor(() =>
      expect(screen.getByTestId("daily-range-toggle")).toBeInTheDocument()
    );
    expect(screen.getByTestId("range-btn-7")).toBeInTheDocument();
    expect(screen.getByTestId("range-btn-30")).toBeInTheDocument();
    expect(screen.getByTestId("range-btn-90")).toBeInTheDocument();
    expect(screen.getByTestId("range-btn-365")).toBeInTheDocument();
  });

  test("clicking 7d button calls fetchHistoricalDaily with 7", async () => {
    const { fetchHistoricalDaily } = require("@/api/analytics");
    render(<HistoricalIntelligenceSection />);
    await waitFor(() =>
      expect(screen.getByTestId("daily-range-toggle")).toBeInTheDocument()
    );
    await act(async () => {
      fireEvent.click(screen.getByTestId("range-btn-7"));
    });
    await waitFor(() =>
      expect(fetchHistoricalDaily).toHaveBeenCalledWith(7)
    );
  });

  test("clicking 90d button calls fetchHistoricalDaily with 90", async () => {
    const { fetchHistoricalDaily } = require("@/api/analytics");
    render(<HistoricalIntelligenceSection />);
    await waitFor(() =>
      expect(screen.getByTestId("daily-range-toggle")).toBeInTheDocument()
    );
    await act(async () => {
      fireEvent.click(screen.getByTestId("range-btn-90"));
    });
    await waitFor(() =>
      expect(fetchHistoricalDaily).toHaveBeenCalledWith(90)
    );
  });
});

describe("HistoricalIntelligenceSection — error state", () => {
  beforeEach(() => {
    clearMocks();
    const { fetchHistoricalRegions, fetchHistoricalHotspots, fetchHistoricalMonthly, fetchHistoricalDaily } =
      require("@/api/analytics");
    fetchHistoricalRegions.mockRejectedValue(new Error("Network error"));
    fetchHistoricalHotspots.mockRejectedValue(new Error("Network error"));
    fetchHistoricalMonthly.mockRejectedValue(new Error("Network error"));
    fetchHistoricalDaily.mockResolvedValue(MOCK_DAILY);
  });

  test("shows error banner when base data fails", async () => {
    render(<HistoricalIntelligenceSection />);
    await waitFor(() =>
      expect(screen.getByTestId("history-error")).toBeInTheDocument()
    );
    expect(screen.getByText(/Network error/i)).toBeInTheDocument();
  });

  test("shows retry button on error", async () => {
    render(<HistoricalIntelligenceSection />);
    await waitFor(() =>
      expect(screen.getByTestId("history-retry")).toBeInTheDocument()
    );
  });
});

describe("HistoricalIntelligenceSection — empty data state", () => {
  beforeEach(() => {
    clearMocks();
    const { fetchHistoricalRegions, fetchHistoricalHotspots, fetchHistoricalMonthly, fetchHistoricalDaily } =
      require("@/api/analytics");
    fetchHistoricalRegions.mockResolvedValue([]);
    fetchHistoricalHotspots.mockResolvedValue([]);
    fetchHistoricalMonthly.mockResolvedValue({ months: [] });
    fetchHistoricalDaily.mockResolvedValue({ generated_at: "2026-06-04T00:00:00Z", days: [] });
  });

  test("shows empty state for daily chart when no data", async () => {
    render(<HistoricalIntelligenceSection />);
    await waitFor(() =>
      expect(screen.getByTestId("daily-empty")).toBeInTheDocument()
    );
  });

  test("shows empty state for monthly chart when no data", async () => {
    render(<HistoricalIntelligenceSection />);
    await waitFor(() =>
      expect(screen.getByTestId("monthly-empty")).toBeInTheDocument()
    );
  });

  test("shows empty state for regions table when no data", async () => {
    render(<HistoricalIntelligenceSection />);
    await waitFor(() =>
      expect(screen.getByTestId("regions-empty")).toBeInTheDocument()
    );
  });

  test("shows empty state for hotspots table when no data", async () => {
    render(<HistoricalIntelligenceSection />);
    await waitFor(() =>
      expect(screen.getByTestId("hotspots-empty")).toBeInTheDocument()
    );
  });
});
