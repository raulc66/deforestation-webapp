import { render, screen } from "@testing-library/react";
import TopIntelligenceSignalCard from "../TopIntelligenceSignalCard";

const SUMMARY_WITH_SIGNAL = {
  active: 3,
  highest_priority_score: 0.8450,
  highest_priority_region: "Carpathian Forest",
};

const SUMMARY_NO_SIGNAL = {
  active: 0,
  highest_priority_score: null,
  highest_priority_region: null,
};

describe("TopIntelligenceSignalCard", () => {
  describe("loading state", () => {
    it("renders skeleton while loading", () => {
      render(<TopIntelligenceSignalCard loading={true} summary={null} />);
      expect(screen.getByTestId("top-signal-loading")).toBeInTheDocument();
    });

    it("does not render content while loading", () => {
      render(<TopIntelligenceSignalCard loading={true} summary={null} />);
      expect(screen.queryByTestId("top-signal-content")).not.toBeInTheDocument();
    });

    it("card wrapper is always present", () => {
      render(<TopIntelligenceSignalCard loading={true} summary={null} />);
      expect(screen.getByTestId("top-intelligence-signal-card")).toBeInTheDocument();
    });
  });

  describe("priority card rendering", () => {
    it("displays the highest priority region", () => {
      render(
        <TopIntelligenceSignalCard loading={false} summary={SUMMARY_WITH_SIGNAL} />
      );
      expect(screen.getByTestId("top-signal-region")).toHaveTextContent(
        "Carpathian Forest"
      );
    });

    it("displays the priority score formatted to 4 decimals", () => {
      render(
        <TopIntelligenceSignalCard loading={false} summary={SUMMARY_WITH_SIGNAL} />
      );
      expect(screen.getByTestId("top-signal-score")).toHaveTextContent("0.8450");
    });

    it("renders the signal content block", () => {
      render(
        <TopIntelligenceSignalCard loading={false} summary={SUMMARY_WITH_SIGNAL} />
      );
      expect(screen.getByTestId("top-signal-content")).toBeInTheDocument();
    });
  });

  describe("empty state", () => {
    it("shows no-signal message when no active events", () => {
      render(
        <TopIntelligenceSignalCard loading={false} summary={SUMMARY_NO_SIGNAL} />
      );
      expect(screen.getByTestId("top-signal-empty")).toBeInTheDocument();
      expect(screen.getByTestId("top-signal-empty")).toHaveTextContent(
        "No active intelligence signals"
      );
    });

    it("does not render content block when empty", () => {
      render(
        <TopIntelligenceSignalCard loading={false} summary={SUMMARY_NO_SIGNAL} />
      );
      expect(screen.queryByTestId("top-signal-content")).not.toBeInTheDocument();
    });

    it("shows empty state when summary is null", () => {
      render(<TopIntelligenceSignalCard loading={false} summary={null} />);
      expect(screen.getByTestId("top-signal-empty")).toBeInTheDocument();
    });
  });
});
