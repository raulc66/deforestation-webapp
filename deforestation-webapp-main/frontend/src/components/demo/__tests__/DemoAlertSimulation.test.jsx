import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import DisturbanceInvestigationPanel from "../../intelligence/DisturbanceInvestigationPanel";
import { demoSimulationNotice } from "@/lib/demo";

const mockSimulateAlert = jest.fn().mockResolvedValue({ ok: true });
const mockSetGuideStep = jest.fn();

jest.mock("@/context/DemoContext", () => ({
  useDemo: () => ({
    isDemo: true,
    lastSimulation: { simulated: true, already_recorded: false },
    recordEvent: jest.fn(),
    simulateAlert: mockSimulateAlert,
    setGuideStep: mockSetGuideStep,
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

const ITEM = {
  event_id: "ie-demo",
  region: "Harghita",
  incident_category: "forest_disturbance",
  disturbance_assessment: {
    assessment_label: "Potential Unauthorized Forest Activity",
    probable_driver: "selective_logging_candidate",
    driver_confidence: 0.86,
    investigation_priority: "high",
    authorization_status: "unknown",
    affected_area_ha: 12.4,
    repeat_activity: true,
  },
  monitored_area: {
    name: "Harghita Forest Reserve",
    inside_monitored_area: true,
  },
  evidence_summary: {
    providers: ["GFW"],
    evidence_state: "single_source",
  },
};

describe("Demo investigation and simulated alert", () => {
  beforeEach(() => {
    mockSimulateAlert.mockClear();
    mockSetGuideStep.mockClear();
    mockSimulateAlert.mockResolvedValue({ ok: true });
  });

  it("interprets a successful first simulation as Notification simulated", () => {
    expect(
      demoSimulationNotice({
        simulated: true,
        already_recorded: false,
        reason: "Demonstration notification simulated.",
        delivery_results: [{ status: "simulated" }],
      })
    ).toBe("Notification simulated");
  });

  it("interprets an idempotent repeat simulation as Notification simulated", () => {
    expect(
      demoSimulationNotice({
        simulated: true,
        already_recorded: true,
        id: "delivery-1",
      })
    ).toBe("Notification simulated");
  });

  it("does not treat a failed API result as a simulated notification", () => {
    expect(demoSimulationNotice({ ok: false, error: "Demonstration event was not found" })).toBeNull();
    expect(demoSimulationNotice(null)).toBeNull();
  });

  it("simulates a notification without implying real delivery", () => {
    render(
      <MemoryRouter>
        <DisturbanceInvestigationPanel item={ITEM} isDemo onInvestigate={jest.fn()} />
      </MemoryRouter>
    );
    expect(screen.getByTestId("demo-simulate-alert")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("demo-simulate-alert"));
    expect(mockSimulateAlert).toHaveBeenCalledWith("ie-demo");
    expect(screen.getByTestId("demo-simulated-delivery")).toHaveTextContent(/notification simulated/i);
    expect(screen.queryByText(/no message was sent/i)).not.toBeInTheDocument();
    expect(screen.getByTestId("disturbance-repeat")).toBeInTheDocument();
  });
});
