import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import AppLayout from "../AppLayout";

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    user: { name: "Ada Forester", email: "ada@org.org" },
    logout: jest.fn(),
  }),
}));

const mockDemoState = { isDemo: false };

jest.mock("@/context/DemoContext", () => ({
  useDemo: () => mockDemoState,
}));

jest.mock("@/lib/demo", () => ({
  isDemoUser: () => false,
}));

jest.mock("@/components/organization/OrganizationSelector", () => () => (
  <div data-testid="organization-selector-stub" />
));

jest.mock("@/components/trial/TrialStatusBar", () => () => (
  <div data-testid="trial-status-bar-stub" />
));

describe("AppLayout customer navigation", () => {
  beforeEach(() => {
    mockDemoState.isDemo = false;
  });

  it("leads with Command Center and hides architecture and unscoped map links", () => {
    render(
      <MemoryRouter>
        <AppLayout>
          <div>content</div>
        </AppLayout>
      </MemoryRouter>
    );
    expect(screen.getByTestId("nav-dashboard")).toHaveTextContent("Command Center");
    expect(screen.getByTestId("app-subtitle")).toHaveTextContent("Forest intelligence");
    expect(screen.queryByTestId("nav-modules")).not.toBeInTheDocument();
    expect(screen.queryByTestId("nav-map")).not.toBeInTheDocument();
    expect(screen.getByTestId("nav-alerts")).toBeInTheDocument();
    expect(screen.getByTestId("nav-billing")).toBeInTheDocument();
  });
});
