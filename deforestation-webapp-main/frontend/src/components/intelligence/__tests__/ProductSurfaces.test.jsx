import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import IntelligenceCommandCenter from "../IntelligenceCommandCenter";
import DisturbanceInvestigationPanel from "../DisturbanceInvestigationPanel";

const mockDemo = {
  isDemo: false,
  lastSimulation: null,
  status: { guide_step: "forests" },
  recordEvent: jest.fn(),
  simulateAlert: jest.fn(),
  setGuideStep: jest.fn(),
};

jest.mock("@/context/DemoContext", () => ({
  useDemo: () => mockDemo,
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

const MOCK_MONITORING = {
  organization: { id: "org-1", name: "Acme Forestry Group", role: "owner" },
  entitlements: {
    monitored_area_limit: 1,
    monitored_area_count: 1,
    monitoring_enabled: true,
    forest_disturbance_enabled: true,
    evidence_correlation_enabled: false,
    live_sources_enabled: false,
    alert_delivery_enabled: false,
  },
  monitored_areas: { enabled_count: 1 },
  disturbance_summary: {
    inside_monitored_area_count: 1,
    high_critical_investigation_count: 1,
    authorization_status_default: "unknown",
  },
};

const MOCK_EVIDENCE_ITEM = {
  event_id: "ie-1",
  region: "Harghita",
  incident_category: "forest_disturbance",
  disturbance_assessment: {
    assessment_label: "Potential Unauthorized Forest Activity",
    probable_driver: "selective_logging_candidate",
    driver_confidence: 0.78,
    investigation_priority: "high",
    authorization_status: "unknown",
    affected_area_ha: 17.4,
  },
  monitored_area: {
    name: "Valea X Forest",
    relevance: "inside_monitored_area",
    inside_monitored_area: true,
  },
  evidence_summary: {
    providers: ["GFW", "EFFIS"],
    evidence_state: "multi_source",
    strongest_correlation_strength: 0.81,
  },
};

describe("IntelligenceCommandCenter", () => {
  it("shows organization identity and metrics", () => {
    render(
      <MemoryRouter>
        <IntelligenceCommandCenter
          monitoringStatus={MOCK_MONITORING}
          commandCenter={{ intelligence_evidence: { items: [MOCK_EVIDENCE_ITEM] } }}
          events={{ active: [{ id: "ie-1", region: "Harghita" }] }}
          loading={false}
        />
      </MemoryRouter>
    );
    expect(screen.getByTestId("command-center-org-name")).toHaveTextContent("Acme Forestry Group");
    expect(screen.getByTestId("command-center-area-metric")).toHaveTextContent("1 / 1");
    expect(screen.getByTestId("command-center-high-metric")).toHaveTextContent("1");
  });

  it("lists priority queue and opens investigation panel", () => {
    render(
      <MemoryRouter>
        <IntelligenceCommandCenter
          monitoringStatus={MOCK_MONITORING}
          commandCenter={{ intelligence_evidence: { items: [MOCK_EVIDENCE_ITEM] } }}
          events={{ active: [] }}
          loading={false}
        />
      </MemoryRouter>
    );
    expect(screen.getByTestId("command-center-priority-queue")).toBeInTheDocument();
    expect(screen.getByTestId("disturbance-investigation-panel")).toBeInTheDocument();
    expect(screen.getByText(/Potential Unauthorized Forest Activity/i)).toBeInTheDocument();
  });

  it("focuses the existing investigation panel when a demo investigation is opened", () => {
    render(
      <MemoryRouter>
        <IntelligenceCommandCenter
          monitoringStatus={MOCK_MONITORING}
          commandCenter={{ intelligence_evidence: { items: [MOCK_EVIDENCE_ITEM] } }}
          events={{ active: [] }}
          loading={false}
          isDemo
          openedInvestigationEventId="ie-1"
          onInvestigate={jest.fn()}
        />
      </MemoryRouter>
    );
    expect(screen.getByTestId("investigation-opened")).toBeInTheDocument();
    expect(screen.getByTestId("investigation-opened-copy")).toBeInTheDocument();
    expect(screen.getByTestId("disturbance-investigate-btn")).toHaveTextContent("Investigation open");
    expect(screen.getByTestId("investigation-opened")).toHaveClass("scroll-mt-16");
    expect(screen.getByTestId("command-center-queue-name-ie-1")).toHaveTextContent("Harghita");
    expect(screen.getByTestId("command-center-detail-column")).toHaveClass("order-1", "xl:order-2");
    expect(screen.getByTestId("command-center-queue-column")).toHaveClass("order-2", "xl:order-1");
  });

  it("gives long queue names word-wrapping space beside the priority badge", () => {
    render(
      <MemoryRouter>
        <IntelligenceCommandCenter
          monitoringStatus={MOCK_MONITORING}
          commandCenter={{
            intelligence_evidence: {
              items: [
                {
                  ...MOCK_EVIDENCE_ITEM,
                  region: "Maramureș Conservation Stand",
                  monitored_area: {
                    ...MOCK_EVIDENCE_ITEM.monitored_area,
                    name: "Harghita Forest Reserve Working Block",
                  },
                },
              ],
            },
          }}
          events={{ active: [] }}
          loading={false}
        />
      </MemoryRouter>
    );
    const name = screen.getByTestId("command-center-queue-name-ie-1");
    expect(name).toHaveTextContent("Maramureș Conservation Stand");
    expect(name).toHaveClass("fw-name");
    expect(name.className).not.toMatch(/break-all|break-words/);
  });

  it("explains the next action when no forests are monitored", () => {
    render(
      <MemoryRouter>
        <IntelligenceCommandCenter
          monitoringStatus={{
            ...MOCK_MONITORING,
            entitlements: { ...MOCK_MONITORING.entitlements, monitored_area_count: 0 },
            monitored_areas: { enabled_count: 0 },
            disturbance_summary: {
              inside_monitored_area_count: 0,
              high_critical_investigation_count: 0,
            },
          }}
          commandCenter={{ intelligence_evidence: { items: [] } }}
          events={{ active: [] }}
          loading={false}
        />
      </MemoryRouter>
    );
    expect(screen.getByTestId("command-center-queue-empty")).toHaveTextContent(
      /No forests are being monitored yet/i
    );
    expect(screen.getByTestId("command-center-add-forest")).toHaveAttribute("href", "/trial/setup");
    expect(screen.getByTestId("command-center-detail-empty")).toBeInTheDocument();
  });

  it("explains that an empty queue is expected when forests are watched", () => {
    render(
      <MemoryRouter>
        <IntelligenceCommandCenter
          monitoringStatus={MOCK_MONITORING}
          commandCenter={{ intelligence_evidence: { items: [] } }}
          events={{ active: [] }}
          loading={false}
        />
      </MemoryRouter>
    );
    expect(screen.getByTestId("command-center-queue-empty")).toHaveTextContent(
      /No disturbances currently require attention/i
    );
    expect(screen.getByTestId("command-center-queue-empty")).toHaveTextContent(/Empty is not a failure/i);
    expect(screen.queryByTestId("command-center-add-forest")).not.toBeInTheDocument();
  });
});

describe("DisturbanceInvestigationPanel", () => {
  beforeEach(() => {
    mockDemo.status = { guide_step: "forests" };
    mockDemo.isDemo = false;
  });
  it("preserves safe assessment language", () => {
    render(<DisturbanceInvestigationPanel item={MOCK_EVIDENCE_ITEM} />);
    expect(screen.getByText(/Potential Unauthorized Forest Activity/i)).toBeInTheDocument();
    expect(screen.queryByText(/illegal logging detected/i)).not.toBeInTheDocument();
    expect(screen.getByTestId("authorization-badge")).toHaveTextContent(/verification/i);
  });

  it("calls investigate handler", () => {
    const handler = jest.fn();
    render(
      <DisturbanceInvestigationPanel item={MOCK_EVIDENCE_ITEM} onInvestigate={handler} />
    );
    fireEvent.click(screen.getByTestId("disturbance-investigate-btn"));
    expect(handler).toHaveBeenCalledWith(MOCK_EVIDENCE_ITEM);
  });

  it("separates observation, inference, evidence, unknown, and action", () => {
    render(<DisturbanceInvestigationPanel item={MOCK_EVIDENCE_ITEM} onInvestigate={jest.fn()} />);
    expect(screen.getByTestId("investigation-observation")).toBeInTheDocument();
    expect(screen.getByTestId("investigation-inference")).toBeInTheDocument();
    expect(screen.getByTestId("investigation-evidence")).toBeInTheDocument();
    expect(screen.getByTestId("investigation-unknown")).toBeInTheDocument();
    expect(screen.getByTestId("investigation-action")).toBeInTheDocument();
  });

  it("visibly opens the existing investigation panel when opened", () => {
    render(
      <DisturbanceInvestigationPanel
        item={MOCK_EVIDENCE_ITEM}
        onInvestigate={jest.fn()}
        isDemo
        opened
      />
    );
    expect(screen.getByTestId("investigation-opened")).toBeInTheDocument();
    expect(screen.getByTestId("investigation-opened-copy")).toBeInTheDocument();
    expect(screen.getByTestId("disturbance-investigate-btn")).toHaveTextContent("Investigation open");
    expect(screen.getByTestId("investigation-observation")).toBeInTheDocument();
    expect(screen.getByTestId("investigation-evidence")).toBeInTheDocument();
  });

  it("moves the action block before evidence below xl without duplicating handlers", () => {
    const handler = jest.fn();
    render(
      <DisturbanceInvestigationPanel item={MOCK_EVIDENCE_ITEM} onInvestigate={handler} isDemo />
    );
    const action = screen.getByTestId("investigation-action");
    expect(action).toHaveClass("order-2", "xl:order-6", "scroll-mt-20");
    expect(screen.getByTestId("investigation-observation")).toHaveClass("order-3", "xl:order-2");
    fireEvent.click(screen.getByTestId("disturbance-investigate-btn"));
    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler).toHaveBeenCalledWith(MOCK_EVIDENCE_ITEM);
    expect(screen.getAllByTestId("disturbance-investigate-btn")).toHaveLength(1);
    expect(screen.getAllByTestId("demo-simulate-alert")).toHaveLength(1);
  });

  it("scrolls the window to the action section on sub-xl after a deliberate investigation focus", () => {
    const originalMatchMedia = window.matchMedia;
    const originalScrollTo = window.scrollTo;
    window.matchMedia = jest.fn((query) => ({
      matches: String(query).includes("max-width: 1279px"),
      media: query,
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
    }));
    window.scrollTo = jest.fn();
    try {
      const { rerender } = render(
        <DisturbanceInvestigationPanel item={MOCK_EVIDENCE_ITEM} onInvestigate={jest.fn()} isDemo />
      );
      expect(window.scrollTo).not.toHaveBeenCalled();

      const action = screen.getByTestId("investigation-action");
      action.getBoundingClientRect = () => ({
        top: 1400,
        bottom: 1528,
        left: 0,
        right: 320,
        width: 320,
        height: 128,
        x: 0,
        y: 1400,
        toJSON: () => {},
      });
      action.scrollIntoView = jest.fn();

      rerender(
        <DisturbanceInvestigationPanel
          item={MOCK_EVIDENCE_ITEM}
          onInvestigate={jest.fn()}
          isDemo
          opened
        />
      );
      expect(action.scrollIntoView).not.toHaveBeenCalled();
      expect(window.scrollTo).toHaveBeenCalledWith({ top: 1320, behavior: "smooth" });
    } finally {
      window.matchMedia = originalMatchMedia;
      window.scrollTo = originalScrollTo;
    }
  });

  it("scrolls the window to actions when a queue item is selected below xl", () => {
    const originalMatchMedia = window.matchMedia;
    const originalScrollTo = window.scrollTo;
    window.matchMedia = jest.fn((query) => ({
      matches: String(query).includes("max-width: 1279px"),
      media: query,
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
    }));
    window.scrollTo = jest.fn();
    try {
      const { rerender } = render(
        <DisturbanceInvestigationPanel item={MOCK_EVIDENCE_ITEM} onInvestigate={jest.fn()} isDemo />
      );
      window.scrollTo.mockClear();
      const nextItem = { ...MOCK_EVIDENCE_ITEM, event_id: "ie-2", region: "Suceava" };
      rerender(
        <DisturbanceInvestigationPanel item={nextItem} onInvestigate={jest.fn()} isDemo />
      );
      expect(window.scrollTo).toHaveBeenCalledWith(
        expect.objectContaining({ behavior: "smooth" })
      );
    } finally {
      window.matchMedia = originalMatchMedia;
      window.scrollTo = originalScrollTo;
    }
  });

  it("scrolls the window when the Investigate guide step is activated below xl", () => {
    const originalMatchMedia = window.matchMedia;
    const originalScrollTo = window.scrollTo;
    window.matchMedia = jest.fn((query) => ({
      matches: String(query).includes("max-width: 1279px"),
      media: query,
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
    }));
    window.scrollTo = jest.fn();
    mockDemo.status = { guide_step: "forests" };
    try {
      const { rerender } = render(
        <DisturbanceInvestigationPanel item={MOCK_EVIDENCE_ITEM} onInvestigate={jest.fn()} isDemo />
      );
      window.scrollTo.mockClear();
      mockDemo.status = { guide_step: "changed" };
      rerender(
        <DisturbanceInvestigationPanel item={MOCK_EVIDENCE_ITEM} onInvestigate={jest.fn()} isDemo />
      );
      expect(window.scrollTo).not.toHaveBeenCalled();
      mockDemo.status = { guide_step: "investigate" };
      rerender(
        <DisturbanceInvestigationPanel item={MOCK_EVIDENCE_ITEM} onInvestigate={jest.fn()} isDemo />
      );
      expect(window.scrollTo).toHaveBeenCalledWith(
        expect.objectContaining({ behavior: "smooth" })
      );
    } finally {
      mockDemo.status = { guide_step: "forests" };
      window.matchMedia = originalMatchMedia;
      window.scrollTo = originalScrollTo;
    }
  });
});
