import { render, screen, waitFor } from "@testing-library/react";
import { TrialProvider } from "../TrialContext";

const mockFetchTrialStatus = jest.fn();
const mockStartTrial = jest.fn();

jest.mock("@/api/trial", () => ({
  fetchTrialStatus: (...args) => mockFetchTrialStatus(...args),
  startTrial: (...args) => mockStartTrial(...args),
}));

let mockAuthUser = { id: "user-1", email: "ada@org.org", name: "Ada" };
let mockOrgState = {
  selectedOrgId: null,
  organizationVersion: 0,
  currentOrganization: null,
  loading: true,
  reload: jest.fn(),
};

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ user: mockAuthUser }),
}));

jest.mock("@/context/OrganizationContext", () => ({
  useOrganization: () => mockOrgState,
}));

function Probe() {
  return <div data-testid="trial-probe" />;
}

describe("TrialProvider request gating", () => {
  beforeEach(() => {
    mockFetchTrialStatus.mockReset();
    mockStartTrial.mockReset();
    mockAuthUser = { id: "user-1", email: "ada@org.org", name: "Ada" };
    mockOrgState = {
      selectedOrgId: null,
      organizationVersion: 0,
      currentOrganization: null,
      loading: true,
      reload: jest.fn(),
    };
  });

  it("does not fetch trial status before organization context is ready", async () => {
    render(
      <TrialProvider>
        <Probe />
      </TrialProvider>
    );
    await waitFor(() => expect(screen.getByTestId("trial-probe")).toBeInTheDocument());
    expect(mockFetchTrialStatus).not.toHaveBeenCalled();
  });

  it("does not fetch trial status against leftover demonstration organization context", async () => {
    mockOrgState = {
      selectedOrgId: "demo-org",
      organizationVersion: 1,
      currentOrganization: {
        id: "demo-org",
        slug: "forestwatch-demo",
        kind: "demo",
        name: "ForestWatch Demonstration",
      },
      loading: false,
      reload: jest.fn(),
    };
    render(
      <TrialProvider>
        <Probe />
      </TrialProvider>
    );
    await waitFor(() => expect(screen.getByTestId("trial-probe")).toBeInTheDocument());
    expect(mockFetchTrialStatus).not.toHaveBeenCalled();
  });
});
