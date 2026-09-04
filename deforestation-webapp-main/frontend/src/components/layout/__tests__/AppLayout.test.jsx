import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import AppLayout from "../AppLayout";

const mockLogout = jest.fn();
const mockAuth = {
  user: { name: "Ada Forester", email: "ada@org.org" },
  logout: (...args) => mockLogout(...args),
};

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => mockAuth,
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

const { __mockNavigate, __resetRouterMocks } = require("react-router-dom");

describe("AppLayout customer navigation", () => {
  beforeEach(() => {
    mockDemoState.isDemo = false;
    mockLogout.mockReset();
    mockLogout.mockResolvedValue(undefined);
    __resetRouterMocks();
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

  it("returns trial operators to the public demo entry after sign out", async () => {
    render(
      <MemoryRouter>
        <AppLayout>
          <div>content</div>
        </AppLayout>
      </MemoryRouter>
    );
    fireEvent.click(screen.getByTestId("logout-btn"));
    await waitFor(() => expect(mockLogout).toHaveBeenCalled());
    expect(__mockNavigate).toHaveBeenCalledWith("/explore");
  });
});
