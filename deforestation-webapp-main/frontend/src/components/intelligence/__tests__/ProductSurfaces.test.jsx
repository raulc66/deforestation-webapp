import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import IntelligenceCommandCenter from "../IntelligenceCommandCenter";
import DisturbanceInvestigationPanel from "../DisturbanceInvestigationPanel";

jest.mock("@/context/DemoContext", () => ({
  useDemo: () => ({
    isDemo: false,
    lastSimulation: null,
    recordEvent: jest.fn(),
    simulateAlert: jest.fn(),
    setGuideStep: jest.fn(),
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
});
