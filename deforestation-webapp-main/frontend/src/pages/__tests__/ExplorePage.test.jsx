import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import ExplorePage from "../ExplorePage";
import DemoGuideRail from "@/components/demo/DemoGuideRail";
import DemoBudgetBar from "@/components/demo/DemoBudgetBar";
import DemoConversionCta from "@/components/demo/DemoConversionCta";
import DemoScenarioSwitcher from "@/components/demo/DemoScenarioSwitcher";
import DisturbanceInvestigationPanel from "@/components/intelligence/DisturbanceInvestigationPanel";
import IntelligenceCommandCenter from "@/components/intelligence/IntelligenceCommandCenter";

const mockStartDemo = jest.fn();
const mockAuth = {
  user: false,
  startDemo: mockStartDemo,
};
const mockDemo = {
  isDemo: false,
  status: null,
  lastSimulation: null,
  recordEvent: jest.fn(),
  simulateAlert: jest.fn(),
  setGuideStep: jest.fn(),
  refresh: jest.fn(),
};

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => mockAuth,
}));

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

const GUIDE = [
  { id: "forests", title: "Your monitored forests", body: "These stands are watched." },
  { id: "changed", title: "What changed", body: "Signals appear on the map." },
];

const STATUS = {
  budget: {
    remaining: { investigation: 3, alert_simulation: 2, report: 2, intelligence_query: 10 },
    limits: { investigation: 5, alert_simulation: 2, report: 2, intelligence_query: 10 },
    exhausted: false,
  },
};

const EVIDENCE_ITEM = {
  event_id: "ie-1",
  region: "Harghita",
  incident_category: "forest_disturbance",
  disturbance_assessment: {
    assessment_label: "Potential Unauthorized Forest Activity",
    probable_driver: "selective_logging_candidate",
    driver_confidence: 0.86,
    investigation_priority: "high",
    authorization_status: "unknown",
    affected_area_ha: 12.4,
    repeat_activity: false,
  },
  monitored_area: {
    name: "Harghita Forest Reserve",
    relevance: "inside_monitored_area",
    inside_monitored_area: true,
  },
  evidence_summary: {
    providers: ["GFW", "EFFIS"],
    evidence_state: "contextual_support",
    strongest_correlation_strength: 0.74,
  },
};

describe("ExplorePage", () => {
  beforeEach(() => {
    mockStartDemo.mockReset();
    mockDemo.refresh.mockReset();
    mockAuth.user = false;
    mockDemo.isDemo = false;
    mockDemo.status = null;
  });

  it("renders the demonstration entry and primary CTA", () => {
    render(
      <MemoryRouter>
        <ExplorePage />
      </MemoryRouter>
    );
    expect(screen.getByTestId("explore-page")).toBeInTheDocument();
    expect(
      screen.getByText(/turns environmental observations into prioritized forest intelligence/i)
    ).toBeInTheDocument();
    expect(screen.getByTestId("start-interactive-demo")).toHaveTextContent(/Start interactive demo/i);
    expect(screen.getByTestId("explore-create-organization")).toHaveTextContent(/Start a 14-day trial/i);
    expect(screen.getByTestId("explore-create-organization")).toHaveAttribute("href", "/register?from=demo");
  });

  it("starts the interactive demo", async () => {
    mockStartDemo.mockResolvedValue({ ok: true, user: { provider: "demo" } });
    render(
      <MemoryRouter>
        <ExplorePage />
      </MemoryRouter>
    );
    fireEvent.click(screen.getByTestId("start-interactive-demo"));
    await waitFor(() => expect(mockStartDemo).toHaveBeenCalled());
  });

  it("does not resume an exhausted demo session from Continue", () => {
    mockAuth.user = { id: "demo:sess-1", provider: "demo", name: "Demonstration visitor" };
    mockDemo.isDemo = true;
    mockDemo.status = {
      budget: {
        remaining: { investigation: 0, alert_simulation: 0, report: 0, intelligence_query: 0 },
        limits: { investigation: 5, alert_simulation: 2, report: 2, intelligence_query: 10 },
        exhausted: true,
      },
    };
    render(
      <MemoryRouter>
        <ExplorePage />
      </MemoryRouter>
    );
    expect(screen.queryByTestId("explore-resume-demo")).not.toBeInTheDocument();
    expect(screen.getByTestId("start-interactive-demo")).toHaveTextContent(/Start interactive demo/i);
  });

  it("lets a visitor with remaining budget continue or restart", async () => {
    mockStartDemo.mockResolvedValue({ ok: true, user: { provider: "demo" } });
    mockAuth.user = { id: "demo:sess-1", provider: "demo", name: "Demonstration visitor" };
    mockDemo.isDemo = true;
    mockDemo.status = STATUS;
    render(
      <MemoryRouter>
        <ExplorePage />
      </MemoryRouter>
    );
    expect(screen.getByTestId("explore-resume-demo")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("explore-restart-demo"));
    await waitFor(() => expect(mockStartDemo).toHaveBeenCalled());
  });
});

describe("Demo guided flow", () => {
  it("lets the visitor pick a guide step without forcing a slideshow", () => {
    const onSelect = jest.fn();
    render(
      <DemoGuideRail guide={GUIDE} currentStep="forests" onSelect={onSelect} />
    );
    expect(screen.getByTestId("demo-guide-rail")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("demo-guide-step-changed"));
    expect(onSelect).toHaveBeenCalledWith("changed");
  });

  it("switches demonstration scenarios", () => {
    const onSelect = jest.fn();
    render(
      <DemoScenarioSwitcher
        scenarios={[
          { id: "high-priority", title: "High-priority forest disturbance", summary: "Investigate first." },
          { id: "informational", title: "Informational observation", summary: "Not urgent." },
        ]}
        focused="high-priority"
        onSelect={onSelect}
      />
    );
    fireEvent.click(screen.getByTestId("demo-scenario-informational"));
    expect(onSelect).toHaveBeenCalledWith("informational");
  });
});

describe("Demo budget", () => {
  it("shows remaining analyses", () => {
    render(<DemoBudgetBar status={STATUS} />);
    expect(screen.getByTestId("demo-budget-investigation")).toHaveTextContent("3 / 5");
  });

  it("shows exhaustion conversion copy", () => {
    render(
      <MemoryRouter>
        <DemoConversionCta moment="exhausted" />
      </MemoryRouter>
    );
    expect(screen.getByTestId("demo-conversion-exhausted")).toHaveTextContent(/Create your trial organization/i);
    expect(screen.getByTestId("demo-conversion-cta")).toHaveAttribute("href", "/register?from=demo");
  });
});

describe("Demo investigation surface", () => {
  it("separates observation, inference, evidence, unknown, and action", () => {
    render(<DisturbanceInvestigationPanel item={EVIDENCE_ITEM} onInvestigate={jest.fn()} />);
    expect(screen.getByTestId("investigation-observation")).toBeInTheDocument();
    expect(screen.getByTestId("investigation-inference")).toBeInTheDocument();
    expect(screen.getByTestId("investigation-evidence")).toBeInTheDocument();
    expect(screen.getByTestId("investigation-unknown")).toBeInTheDocument();
    expect(screen.getByTestId("investigation-action")).toBeInTheDocument();
    expect(screen.queryByText(/illegal logging detected/i)).not.toBeInTheDocument();
  });

  it("shows ForestWatch Demo kicker on the command center", () => {
    render(
      <MemoryRouter>
      <IntelligenceCommandCenter
        isDemo
        monitoringStatus={{
          organization: { name: "ForestWatch Demonstration", role: "admin" },
          entitlements: { monitored_area_count: 3, monitoring_enabled: true },
          disturbance_summary: { high_critical_investigation_count: 1, inside_monitored_area_count: 3 },
        }}
        commandCenter={{ intelligence_evidence: { items: [EVIDENCE_ITEM] } }}
        events={{ active: [{ id: "ie-1" }, { id: "ie-2" }, { id: "ie-3" }] }}
        loading={false}
      />
      </MemoryRouter>
    );
    expect(screen.getByTestId("intelligence-command-center")).toBeInTheDocument();
    expect(screen.getByTestId("command-center-org-name")).toHaveTextContent("ForestWatch Demonstration");
    expect(screen.getByTestId("command-center-area-metric")).toHaveTextContent("3");
    expect(screen.getByTestId("command-center-high-metric")).toHaveTextContent("1");
  });
});
