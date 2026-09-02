import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import DisturbanceInvestigationPanel from "../../intelligence/DisturbanceInvestigationPanel";

const mockSimulateAlert = jest.fn().mockResolvedValue({ ok: true });
const mockSetGuideStep = jest.fn();

jest.mock("@/context/DemoContext", () => ({
  useDemo: () => ({
    isDemo: true,
    lastSimulation: { simulated: true },
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
  it("simulates a notification without implying real delivery", () => {
    render(
      <MemoryRouter>
        <DisturbanceInvestigationPanel item={ITEM} isDemo onInvestigate={jest.fn()} />
      </MemoryRouter>
    );
    expect(screen.getByTestId("demo-simulate-alert")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("demo-simulate-alert"));
    expect(mockSimulateAlert).toHaveBeenCalledWith("ie-demo");
    expect(screen.getByTestId("demo-simulated-delivery")).toHaveTextContent(/no message was sent/i);
    expect(screen.getByTestId("disturbance-repeat")).toBeInTheDocument();
  });
});
