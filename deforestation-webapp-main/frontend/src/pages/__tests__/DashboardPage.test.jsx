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
const mockDemo = { isDemo: false };
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
    expect(screen.getByTestId("intelligence-section")).toBeInTheDocument();
    expect(screen.queryByText(/Welcome,/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Watcher/i)).not.toBeInTheDocument();
    expect(screen.queryByTestId("analytics-section")).not.toBeInTheDocument();
    expect(screen.queryByTestId("recent-alerts-table")).not.toBeInTheDocument();
    expect(screen.queryByTestId("module-card-ai_predictions")).not.toBeInTheDocument();
    expect(screen.queryByTestId("open-map-link")).not.toBeInTheDocument();
  });
});
