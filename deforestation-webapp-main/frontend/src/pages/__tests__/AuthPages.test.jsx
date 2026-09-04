import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import LoginPage from "../LoginPage";
import RegisterPage from "../RegisterPage";

const mockLogin = jest.fn();
const mockRegister = jest.fn();
const { __mockNavigate, __resetRouterMocks, __setMockSearchParams } = require("react-router-dom");

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    login: (...args) => mockLogin(...args),
    register: (...args) => mockRegister(...args),
  }),
}));

jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

describe("LoginPage", () => {
  beforeEach(() => {
    mockLogin.mockReset();
    __resetRouterMocks();
  });

  it("does not publish admin credentials", () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );
    expect(screen.getByTestId("login-form")).toBeInTheDocument();
    expect(screen.queryByText(/Demo credentials/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/ForestAdmin2026/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/admin@forestwatch.io/i)).not.toBeInTheDocument();
  });

  it("describes forest intelligence rather than a generic dashboard", () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );
    expect(screen.getByText(/forests for your organization/i)).toBeInTheDocument();
    expect(screen.queryByText(/Defend every tree/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/clean-architecture/i)).not.toBeInTheDocument();
  });
});

describe("RegisterPage", () => {
  beforeEach(() => {
    mockRegister.mockReset();
    __resetRouterMocks();
  });

  it("sends new accounts into trial setup", async () => {
    mockRegister.mockResolvedValue({ ok: true, user: { name: "Ada" } });
    render(
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    );
    fireEvent.change(screen.getByTestId("register-name"), { target: { value: "Ada Forester" } });
    fireEvent.change(screen.getByTestId("register-email"), { target: { value: "ada@org.org" } });
    fireEvent.change(screen.getByTestId("register-password"), { target: { value: "secret1" } });
    fireEvent.click(screen.getByTestId("register-submit"));
    await waitFor(() => expect(mockRegister).toHaveBeenCalled());
    expect(__mockNavigate).toHaveBeenCalledWith("/trial/setup", { replace: true });
  });

  it("explains that demo conversion starts a real trial organization", () => {
    __setMockSearchParams("from=demo");
    render(
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    );
    expect(screen.getByTestId("register-intro")).toHaveTextContent(
      /Create a free trial organization to continue with your own monitored areas/i
    );
    expect(screen.getByTestId("register-intro")).toHaveTextContent(/14-day trial/i);
  });
});
