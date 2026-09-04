import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import DashboardPage from "../DashboardPage";

jest.mock("@/components/layout/AppLayout", () => ({ children }) => (
  <div data-testid="app-layout">{children}</div>
));

jest.mock("@/components/intelligence/IntelligenceSection", () => () => (
  <div data-testid="intelligence-section" />
));

const mockAuth = { user: { name: "Ada Forester", email: "ada@org.org" } };
const mockDemo = {
  isDemo: false,
  conversion: null,
  exhaustedMessage: null,
  status: { guide: [], scenarios: [], budget: { remaining: {}, limits: {} } },
  resetDemo: jest.fn(),
  setGuideStep: jest.fn(),
  openScenario: jest.fn(),
  recordEvent: jest.fn(),
};
const mockOrg = { currentOrganization: { id: "org-1", name: "Carpathian Watch" } };
let mockTrial = {
  status: { commercial_lifecycle: "trial", onboarding: { complete: true } },
  isTrial: true,
  isExpired: false,
};

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => mockAuth,
}));

jest.mock("@/context/DemoContext", () => ({
  useDemo: () => mockDemo,
}));

jest.mock("@/lib/demo", () => ({
  ...jest.requireActual("@/lib/demo"),
  isDemoUser: () => false,
}));

jest.mock("@/context/OrganizationContext", () => ({
  useOrganization: () => mockOrg,
}));

jest.mock("@/context/TrialContext", () => ({
  useTrial: () => mockTrial,
}));

describe("Operator dashboard", () => {
  beforeEach(() => {
    mockDemo.isDemo = false;
    mockDemo.conversion = null;
    mockDemo.exhaustedMessage = null;
    mockTrial = {
      status: { commercial_lifecycle: "trial", onboarding: { complete: true } },
      isTrial: true,
      isExpired: false,
    };
  });

  it("leads with organization identity and command center, not a generic SaaS home", () => {
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    );
    expect(screen.getByTestId("operator-org-name")).toHaveTextContent("Carpathian Watch");
    expect(screen.getByTestId("trial-workspace-kicker")).toHaveTextContent(/not demonstration data/i);
    expect(screen.getByTestId("intelligence-section")).toBeInTheDocument();
    expect(screen.queryByText(/Welcome,/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Watcher/i)).not.toBeInTheDocument();
    expect(screen.queryByTestId("analytics-section")).not.toBeInTheDocument();
    expect(screen.queryByTestId("recent-alerts-table")).not.toBeInTheDocument();
    expect(screen.queryByTestId("module-card-ai_predictions")).not.toBeInTheDocument();
    expect(screen.queryByTestId("open-map-link")).not.toBeInTheDocument();
  });
});

describe("Demo dashboard conversion timing", () => {
  beforeEach(() => {
    mockDemo.isDemo = true;
    mockDemo.conversion = null;
    mockDemo.exhaustedMessage = null;
    mockDemo.status = {
      guide: [],
      scenarios: [],
      budget: { remaining: { investigation: 5 }, limits: { investigation: 5 } },
    };
  });

  it("does not show the conversion CTA after investigation alone", () => {
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    );
    expect(screen.getByTestId("intelligence-section")).toBeInTheDocument();
    expect(screen.queryByTestId("demo-conversion-cta")).not.toBeInTheDocument();
  });

  it("shows a non-blocking conversion prompt after a simulated alert", () => {
    mockDemo.conversion = "alert";
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    );
    expect(screen.getByTestId("intelligence-section")).toBeInTheDocument();
    expect(screen.getByTestId("demo-conversion-cta")).toBeInTheDocument();
    expect(screen.getByTestId("demo-conversion-alert")).toBeInTheDocument();
  });
});
