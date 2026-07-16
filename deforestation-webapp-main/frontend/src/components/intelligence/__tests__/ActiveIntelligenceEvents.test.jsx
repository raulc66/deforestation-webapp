import { render, screen, within, fireEvent } from "@testing-library/react";
import ActiveIntelligenceEvents from "../ActiveIntelligenceEvents";

const EVT_HIGH = {
  id: "evt-001",
  region: "Carpathian Forest",
  severity: "high",
  trend: "worsening",
  escalation_level: "persistent",
  priority_score: 0.76,
  detection_count: 4,
  current_score: 0.70,
  last_detected_at: "2026-06-13T19:00:00Z",
};

const EVT_MEDIUM = {
  id: "evt-002",
  region: "Transylvania",
  severity: "medium",
  trend: "stable",
  escalation_level: "normal",
  priority_score: 0.42,
  detection_count: 2,
  current_score: 0.50,
  last_detected_at: "2026-06-12T15:00:00Z",
};

const EVT_CRITICAL = {
  id: "evt-003",
  region: "Dobrogea",
  severity: "critical",
  trend: "new",
  escalation_level: "persistent",
  priority_score: 0.91,
  detection_count: 1,
  current_score: 0.90,
  last_detected_at: "2026-06-14T10:00:00Z",
};

describe("ActiveIntelligenceEvents", () => {
  describe("loading state", () => {
    it("renders loading row while loading", () => {
      render(<ActiveIntelligenceEvents loading={true} events={null} />);
      expect(
        screen.getByTestId("intelligence-events-loading")
      ).toBeInTheDocument();
    });

    it("shows loading message text", () => {
      render(<ActiveIntelligenceEvents loading={true} events={null} />);
      expect(screen.getByText(/loading intelligence events/i)).toBeInTheDocument();
    });

    it("table is always rendered (not null)", () => {
      render(<ActiveIntelligenceEvents loading={true} events={null} />);
      expect(
        screen.getByTestId("intelligence-events-table")
      ).toBeInTheDocument();
    });
  });

  describe("empty state", () => {
    it("shows empty row when events list is empty", () => {
      render(<ActiveIntelligenceEvents loading={false} events={[]} />);
      expect(screen.getByTestId("intelligence-events-empty")).toBeInTheDocument();
    });

    it("displays friendly empty message", () => {
      render(<ActiveIntelligenceEvents loading={false} events={[]} />);
      expect(
        screen.getByText(/no active intelligence events/i)
      ).toBeInTheDocument();
    });

    it("handles null events without crashing", () => {
      render(<ActiveIntelligenceEvents loading={false} events={null} />);
      expect(screen.getByTestId("intelligence-events-empty")).toBeInTheDocument();
    });
  });

  describe("active event rendering", () => {
    it("renders a row for each active event", () => {
      render(
        <ActiveIntelligenceEvents
          loading={false}
          events={[EVT_HIGH, EVT_MEDIUM]}
        />
      );
      expect(screen.getByTestId("intelligence-event-row-evt-001")).toBeInTheDocument();
      expect(screen.getByTestId("intelligence-event-row-evt-002")).toBeInTheDocument();
    });

    it("displays region name in each row", () => {
      render(
        <ActiveIntelligenceEvents loading={false} events={[EVT_HIGH]} />
      );
      expect(screen.getByText("Carpathian Forest")).toBeInTheDocument();
    });

    it("displays priority score formatted to 4 decimals", () => {
      render(
        <ActiveIntelligenceEvents loading={false} events={[EVT_HIGH]} />
      );
      expect(screen.getByText("0.7600")).toBeInTheDocument();
    });

    it("displays detection count", () => {
      render(
        <ActiveIntelligenceEvents loading={false} events={[EVT_HIGH]} />
      );
      expect(screen.getByText("4")).toBeInTheDocument();
    });
  });

  describe("trend visualization", () => {
    it("renders worsening badge for worsening trend", () => {
      render(
        <ActiveIntelligenceEvents loading={false} events={[EVT_HIGH]} />
      );
      expect(screen.getByTestId("trend-badge-worsening")).toBeInTheDocument();
    });

    it("renders stable badge for stable trend", () => {
      render(
        <ActiveIntelligenceEvents loading={false} events={[EVT_MEDIUM]} />
      );
      expect(screen.getByTestId("trend-badge-stable")).toBeInTheDocument();
    });

    it("renders new badge for new trend", () => {
      render(
        <ActiveIntelligenceEvents loading={false} events={[EVT_CRITICAL]} />
      );
      expect(screen.getByTestId("trend-badge-new")).toBeInTheDocument();
    });
  });

  describe("escalation visualization", () => {
    it("renders persistent escalation badge", () => {
      render(
        <ActiveIntelligenceEvents loading={false} events={[EVT_HIGH]} />
      );
      expect(screen.getByTestId("escalation-badge-persistent")).toBeInTheDocument();
    });

    it("renders normal escalation badge", () => {
      render(
        <ActiveIntelligenceEvents loading={false} events={[EVT_MEDIUM]} />
      );
      expect(screen.getByTestId("escalation-badge-normal")).toBeInTheDocument();
    });
  });

  describe("sorting behavior", () => {
    it("renders highest priority event first", () => {
      render(
        <ActiveIntelligenceEvents
          loading={false}
          events={[EVT_MEDIUM, EVT_HIGH, EVT_CRITICAL]}
        />
      );
      const rows = screen.getAllByRole("row").filter((r) =>
        r.dataset.testid?.startsWith("intelligence-event-row")
      );
      // EVT_CRITICAL has priority 0.91 — should be first
      expect(rows[0]).toHaveAttribute(
        "data-testid",
        "intelligence-event-row-evt-003"
      );
    });

    it("renders second-highest priority event second", () => {
      render(
        <ActiveIntelligenceEvents
          loading={false}
          events={[EVT_MEDIUM, EVT_HIGH, EVT_CRITICAL]}
        />
      );
      const rows = screen.getAllByRole("row").filter((r) =>
        r.dataset.testid?.startsWith("intelligence-event-row")
      );
      // EVT_HIGH has priority 0.76 — should be second
      expect(rows[1]).toHaveAttribute(
        "data-testid",
        "intelligence-event-row-evt-001"
      );
    });

    it("renders lowest priority event last", () => {
      render(
        <ActiveIntelligenceEvents
          loading={false}
          events={[EVT_MEDIUM, EVT_HIGH, EVT_CRITICAL]}
        />
      );
      const rows = screen.getAllByRole("row").filter((r) =>
        r.dataset.testid?.startsWith("intelligence-event-row")
      );
      expect(rows[2]).toHaveAttribute(
        "data-testid",
        "intelligence-event-row-evt-002"
      );
    });

    it("sorts by last_detected_at DESC when priority scores tie", () => {
      const evtA = { ...EVT_MEDIUM, id: "tie-a", last_detected_at: "2026-06-10T00:00:00Z" };
      const evtB = { ...EVT_MEDIUM, id: "tie-b", last_detected_at: "2026-06-14T00:00:00Z" };
      render(
        <ActiveIntelligenceEvents loading={false} events={[evtA, evtB]} />
      );
      const rows = screen.getAllByRole("row").filter((r) =>
        r.dataset.testid?.startsWith("intelligence-event-row")
      );
      // evtB is more recent — should be first
      expect(rows[0]).toHaveAttribute("data-testid", "intelligence-event-row-tie-b");
    });

    it("does not mutate the original events array", () => {
      const events = [EVT_MEDIUM, EVT_HIGH];
      const originalOrder = events.map((e) => e.id);
      render(<ActiveIntelligenceEvents loading={false} events={events} />);
      expect(events.map((e) => e.id)).toEqual(originalOrder);
    });

    it("calls onCreateInvestigation when Investigate clicked", () => {
      const handler = jest.fn();
      render(
        <ActiveIntelligenceEvents
          loading={false}
          events={[EVT_HIGH]}
          onCreateInvestigation={handler}
        />
      );
      fireEvent.click(screen.getByTestId("create-investigation-evt-001"));
      expect(handler).toHaveBeenCalledWith(EVT_HIGH);
    });
  });
});
