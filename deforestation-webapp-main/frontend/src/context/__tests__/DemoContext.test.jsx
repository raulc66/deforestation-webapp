import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { DemoProvider, useDemo } from "../DemoContext";

const mockFetchStatus = jest.fn();
const mockConsume = jest.fn();
const mockSimulate = jest.fn();
const mockReset = jest.fn();
const mockSetGuide = jest.fn();

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ user: { id: "demo:sess-1", provider: "demo" } }),
}));

jest.mock("@/api/demo", () => ({
  fetchDemoStatus: (...args) => mockFetchStatus(...args),
  consumeDemoInvestigation: (...args) => mockConsume(...args),
  simulateDemoAlert: (...args) => mockSimulate(...args),
  resetDemoSession: (...args) => mockReset(...args),
  setDemoGuideStep: (...args) => mockSetGuide(...args),
  openDemoScenario: jest.fn(),
  recordDemoEvent: jest.fn(),
}));

const FRESH_BUDGET = {
  remaining: { investigation: 5, alert_simulation: 2 },
  limits: { investigation: 5, alert_simulation: 2 },
  exhausted: false,
};

function Probe() {
  const demo = useDemo();
  return (
    <div>
      <div data-testid="opened">{demo.openedInvestigationEventId || ""}</div>
      <div data-testid="conversion">{demo.conversion || ""}</div>
      <div data-testid="remaining">{demo.status?.budget?.remaining?.investigation ?? ""}</div>
      <button type="button" data-testid="investigate" onClick={() => demo.investigate("evt-001")}>
        investigate
      </button>
      <button type="button" data-testid="simulate" onClick={() => demo.simulateAlert("evt-001")}>
        simulate
      </button>
      <button type="button" data-testid="reset" onClick={() => demo.resetDemo()}>
        reset
      </button>
    </div>
  );
}

describe("DemoContext investigation and conversion", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFetchStatus.mockResolvedValue({ budget: FRESH_BUDGET, reset_count: 0 });
    mockConsume.mockResolvedValue({
      ok: true,
      action: "investigation",
      demo: {
        budget: {
          remaining: { investigation: 4, alert_simulation: 2 },
          limits: { investigation: 5, alert_simulation: 2 },
          exhausted: false,
        },
      },
    });
    mockSimulate.mockResolvedValue({
      id: "delivery-1",
      simulated: true,
      demo: { budget: FRESH_BUDGET },
    });
    mockReset.mockResolvedValue({ budget: FRESH_BUDGET, reset_count: 1 });
  });

  it("opens an investigation without treating the first action as demo finished", async () => {
    render(
      <DemoProvider>
        <Probe />
      </DemoProvider>
    );
    await waitFor(() => expect(screen.getByTestId("remaining")).toHaveTextContent("5"));
    fireEvent.click(screen.getByTestId("investigate"));
    await waitFor(() => expect(screen.getByTestId("opened")).toHaveTextContent("evt-001"));
    expect(mockConsume).toHaveBeenCalledTimes(1);
    expect(mockConsume).toHaveBeenCalledWith("evt-001");
    expect(screen.getByTestId("remaining")).toHaveTextContent("4");
    expect(screen.getByTestId("conversion")).toHaveTextContent("");
  });

  it("may show conversion after a simulated alert, not in place of investigation", async () => {
    render(
      <DemoProvider>
        <Probe />
      </DemoProvider>
    );
    await waitFor(() => expect(screen.getByTestId("remaining")).toHaveTextContent("5"));
    fireEvent.click(screen.getByTestId("investigate"));
    await waitFor(() => expect(screen.getByTestId("opened")).toHaveTextContent("evt-001"));
    fireEvent.click(screen.getByTestId("simulate"));
    await waitFor(() => expect(screen.getByTestId("conversion")).toHaveTextContent("alert"));
    expect(screen.getByTestId("opened")).toHaveTextContent("evt-001");
  });

  it("clears opened investigation and conversion on reset", async () => {
    render(
      <DemoProvider>
        <Probe />
      </DemoProvider>
    );
    await waitFor(() => expect(screen.getByTestId("remaining")).toHaveTextContent("5"));
    fireEvent.click(screen.getByTestId("investigate"));
    await waitFor(() => expect(screen.getByTestId("opened")).toHaveTextContent("evt-001"));
    fireEvent.click(screen.getByTestId("simulate"));
    await waitFor(() => expect(screen.getByTestId("conversion")).toHaveTextContent("alert"));
    fireEvent.click(screen.getByTestId("reset"));
    await waitFor(() => expect(screen.getByTestId("opened")).toHaveTextContent(""));
    expect(screen.getByTestId("conversion")).toHaveTextContent("");
  });
});
