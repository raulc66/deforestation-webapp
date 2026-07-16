import { render, screen } from "@testing-library/react";
import IntelligenceSummaryCards from "../IntelligenceSummaryCards";

const SUMMARY = {
  active: 5,
  resolved: 12,
  persistent: 3,
  critical: 1,
  worsening: 2,
  stable: 2,
  improving: 1,
  highest_priority_score: 0.85,
  highest_priority_region: "Carpathian Forest",
};

describe("IntelligenceSummaryCards", () => {
  describe("loading state", () => {
    it("renders skeleton placeholders while loading", () => {
      render(<IntelligenceSummaryCards loading={true} summary={null} />);
      expect(
        screen.getByTestId("intelligence-summary-loading")
      ).toBeInTheDocument();
    });

    it("does not render the stat cards during loading", () => {
      render(<IntelligenceSummaryCards loading={true} summary={null} />);
      expect(
        screen.queryByTestId("intelligence-summary-cards")
      ).not.toBeInTheDocument();
    });
  });

  describe("summary rendering", () => {
    it("renders the card grid when not loading", () => {
      render(<IntelligenceSummaryCards loading={false} summary={SUMMARY} />);
      expect(
        screen.getByTestId("intelligence-summary-cards")
      ).toBeInTheDocument();
    });

    it("displays active event count", () => {
      render(<IntelligenceSummaryCards loading={false} summary={SUMMARY} />);
      const card = screen.getByTestId("intel-stat-active");
      expect(card).toHaveTextContent("5");
    });

    it("displays resolved event count", () => {
      render(<IntelligenceSummaryCards loading={false} summary={SUMMARY} />);
      expect(screen.getByTestId("intel-stat-resolved")).toHaveTextContent("12");
    });

    it("displays persistent event count", () => {
      render(<IntelligenceSummaryCards loading={false} summary={SUMMARY} />);
      expect(screen.getByTestId("intel-stat-persistent")).toHaveTextContent("3");
    });

    it("displays critical event count", () => {
      render(<IntelligenceSummaryCards loading={false} summary={SUMMARY} />);
      expect(screen.getByTestId("intel-stat-critical")).toHaveTextContent("1");
    });

    it("renders four stat cards total", () => {
      render(<IntelligenceSummaryCards loading={false} summary={SUMMARY} />);
      const grid = screen.getByTestId("intelligence-summary-cards");
      expect(grid.querySelectorAll("[data-testid^='intel-stat-']")).toHaveLength(4);
    });
  });

  describe("empty state", () => {
    it("displays zeros when summary provides zero counts", () => {
      const empty = { active: 0, resolved: 0, persistent: 0, critical: 0 };
      render(<IntelligenceSummaryCards loading={false} summary={empty} />);
      expect(screen.getByTestId("intel-stat-active")).toHaveTextContent("0");
      expect(screen.getByTestId("intel-stat-resolved")).toHaveTextContent("0");
    });

    it("renders without crashing when summary is null", () => {
      render(<IntelligenceSummaryCards loading={false} summary={null} />);
      expect(screen.getByTestId("intel-stat-active")).toHaveTextContent("0");
    });
  });
});
