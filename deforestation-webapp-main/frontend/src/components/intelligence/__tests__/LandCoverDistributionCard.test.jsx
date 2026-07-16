import React from "react";
import { render, screen } from "@testing-library/react";
import LandCoverDistributionCard from "../LandCoverDistributionCard";

const MOCK_DATA = {
  generated_at: "2026-06-10T12:00:00Z",
  distribution: [
    { land_cover: "forest",      events: 52 },
    { land_cover: "near_forest", events: 31 },
    { land_cover: "agriculture", events: 18 },
    { land_cover: "urban",       events: 5 },
    { land_cover: "water",       events: 3 },
    { land_cover: "unknown",     events: 121 },
  ],
};

const MOCK_DATA_WITH_DATASET = {
  ...MOCK_DATA,
  dataset: {
    source: "Copernicus Land Monitoring Service",
    version: "2018-Romania-Simplified-v1",
    last_updated: "2024-01-01",
    feature_count: 50,
  },
};

describe("LandCoverDistributionCard", () => {
  // ── Loading state ─────────────────────────────────────────────────────────

  it("renders loading skeleton when loading=true", () => {
    render(<LandCoverDistributionCard data={null} loading={true} />);
    expect(screen.getByTestId("land-cover-loading")).toBeInTheDocument();
  });

  it("does not render the card body while loading", () => {
    render(<LandCoverDistributionCard data={null} loading={true} />);
    expect(screen.queryByTestId("land-cover-card")).not.toBeInTheDocument();
  });

  // ── Empty / null state ────────────────────────────────────────────────────

  it("renders empty state when data is null", () => {
    render(<LandCoverDistributionCard data={null} loading={false} />);
    expect(screen.getByTestId("land-cover-empty")).toBeInTheDocument();
  });

  it("renders empty state when data has no distribution", () => {
    render(
      <LandCoverDistributionCard
        data={{ generated_at: "2026-06-10T12:00:00Z" }}
        loading={false}
      />
    );
    expect(screen.getByTestId("land-cover-empty")).toBeInTheDocument();
  });

  // ── Loaded state ──────────────────────────────────────────────────────────

  it("renders the card when data is provided", () => {
    render(<LandCoverDistributionCard data={MOCK_DATA} loading={false} />);
    expect(screen.getByTestId("land-cover-card")).toBeInTheDocument();
  });

  it("renders a row for each of the six land-cover types", () => {
    render(<LandCoverDistributionCard data={MOCK_DATA} loading={false} />);
    const types = ["forest", "near_forest", "agriculture", "urban", "water", "unknown"];
    for (const t of types) {
      expect(screen.getByTestId(`land-cover-row-${t}`)).toBeInTheDocument();
    }
  });

  it("displays correct event count for forest", () => {
    render(<LandCoverDistributionCard data={MOCK_DATA} loading={false} />);
    expect(screen.getByTestId("land-cover-count-forest").textContent).toBe("52");
  });

  it("displays correct event count for near_forest", () => {
    render(<LandCoverDistributionCard data={MOCK_DATA} loading={false} />);
    expect(screen.getByTestId("land-cover-count-near_forest").textContent).toBe("31");
  });

  it("displays correct event count for unknown", () => {
    render(<LandCoverDistributionCard data={MOCK_DATA} loading={false} />);
    expect(screen.getByTestId("land-cover-count-unknown").textContent).toBe("121");
  });

  it("shows zero for a land-cover type missing from distribution", () => {
    const partialData = {
      generated_at: "2026-06-10T12:00:00Z",
      distribution: [
        { land_cover: "forest", events: 10 },
        // other types omitted
      ],
    };
    render(<LandCoverDistributionCard data={partialData} loading={false} />);
    expect(screen.getByTestId("land-cover-count-urban").textContent).toBe("0");
    expect(screen.getByTestId("land-cover-count-water").textContent).toBe("0");
  });

  it("renders the total events classified count", () => {
    render(<LandCoverDistributionCard data={MOCK_DATA} loading={false} />);
    // total = 52+31+18+5+3+121 = 230
    expect(screen.getByText(/230/)).toBeInTheDocument();
  });

  it("renders all six human-readable labels", () => {
    render(<LandCoverDistributionCard data={MOCK_DATA} loading={false} />);
    expect(screen.getByText("Forest")).toBeInTheDocument();
    expect(screen.getByText("Near Forest")).toBeInTheDocument();
    expect(screen.getByText("Agriculture")).toBeInTheDocument();
    expect(screen.getByText("Urban")).toBeInTheDocument();
    expect(screen.getByText("Water")).toBeInTheDocument();
    expect(screen.getByText("Unknown")).toBeInTheDocument();
  });

  it("shows the distribution list element", () => {
    render(<LandCoverDistributionCard data={MOCK_DATA} loading={false} />);
    expect(screen.getByTestId("land-cover-list")).toBeInTheDocument();
  });

  it("handles zero total gracefully (no NaN)", () => {
    const zeroData = {
      generated_at: "2026-06-10T12:00:00Z",
      distribution: [],
    };
    render(<LandCoverDistributionCard data={zeroData} loading={false} />);
    // Should render without crashing, all counts should be 0
    expect(screen.getByTestId("land-cover-count-forest").textContent).toBe("0");
  });

  // ── Dataset metadata section ──────────────────────────────────────────────

  it("renders dataset info section when dataset prop is present", () => {
    render(<LandCoverDistributionCard data={MOCK_DATA_WITH_DATASET} loading={false} />);
    expect(screen.getByTestId("land-cover-dataset-info")).toBeInTheDocument();
  });

  it("does not render dataset info section when dataset is absent", () => {
    render(<LandCoverDistributionCard data={MOCK_DATA} loading={false} />);
    expect(screen.queryByTestId("land-cover-dataset-info")).not.toBeInTheDocument();
  });

  it("displays the dataset source", () => {
    render(<LandCoverDistributionCard data={MOCK_DATA_WITH_DATASET} loading={false} />);
    expect(screen.getByTestId("dataset-source").textContent).toBe(
      "Copernicus Land Monitoring Service"
    );
  });

  it("displays the dataset version", () => {
    render(<LandCoverDistributionCard data={MOCK_DATA_WITH_DATASET} loading={false} />);
    expect(screen.getByTestId("dataset-version").textContent).toBe(
      "2018-Romania-Simplified-v1"
    );
  });

  it("displays the last updated date", () => {
    render(<LandCoverDistributionCard data={MOCK_DATA_WITH_DATASET} loading={false} />);
    expect(screen.getByTestId("dataset-last-updated").textContent).toBe("2024-01-01");
  });

  it("hides version when version is 'unknown'", () => {
    const dataWithUnknownVersion = {
      ...MOCK_DATA,
      dataset: {
        source: "Copernicus Land Monitoring Service",
        version: "unknown",
        last_updated: "2024-01-01",
      },
    };
    render(<LandCoverDistributionCard data={dataWithUnknownVersion} loading={false} />);
    expect(screen.queryByTestId("dataset-version")).not.toBeInTheDocument();
  });

  it("hides last_updated when last_updated is 'unknown'", () => {
    const dataWithUnknownDate = {
      ...MOCK_DATA,
      dataset: {
        source: "Copernicus Land Monitoring Service",
        version: "2018",
        last_updated: "unknown",
      },
    };
    render(<LandCoverDistributionCard data={dataWithUnknownDate} loading={false} />);
    expect(screen.queryByTestId("dataset-last-updated")).not.toBeInTheDocument();
  });
});
