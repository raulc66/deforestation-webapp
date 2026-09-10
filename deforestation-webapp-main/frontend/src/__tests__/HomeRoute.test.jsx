import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import HomeRoute from "@/pages/HomeRoute";

const mockAuth = { user: false };

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => mockAuth,
}));

describe("HomeRoute public and operator entry", () => {
  beforeEach(() => {
    mockAuth.user = false;
  });

  it("shows the commercial page for an anonymous visitor", () => {
    render(
      <MemoryRouter>
        <HomeRoute />
      </MemoryRouter>
    );
    expect(screen.getByTestId("sales-page")).toBeInTheDocument();
    expect(screen.queryByTestId("navigate")).not.toBeInTheDocument();
  });

  it("does not enter the demo dashboard because a demo cookie exists", () => {
    mockAuth.user = {
      id: "demo:sess-1",
      provider: "demo",
      name: "Demonstration visitor",
    };
    render(
      <MemoryRouter>
        <HomeRoute />
      </MemoryRouter>
    );
    expect(screen.getByTestId("sales-page")).toBeInTheDocument();
    expect(screen.queryByTestId("navigate")).not.toBeInTheDocument();
  });

  it("still sends a real authenticated operator to the workspace", () => {
    mockAuth.user = {
      id: "user-1",
      provider: "local",
      name: "Ada Forester",
      email: "ada@org.org",
    };
    render(
      <MemoryRouter>
        <HomeRoute />
      </MemoryRouter>
    );
    expect(screen.queryByTestId("sales-page")).not.toBeInTheDocument();
    expect(screen.getByTestId("navigate")).toHaveAttribute("data-to", "/dashboard");
  });
});
