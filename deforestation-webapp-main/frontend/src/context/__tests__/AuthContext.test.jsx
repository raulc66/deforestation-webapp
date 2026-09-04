import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { AuthProvider, useAuth } from "../AuthContext";

const mockStartDemoSession = jest.fn();
const mockApiGet = jest.fn();
const mockApiPost = jest.fn();
const mockSetOrganizationHeader = jest.fn();

jest.mock("@/api/demo", () => ({
  startDemoSession: (...args) => mockStartDemoSession(...args),
}));

jest.mock("@/lib/api", () => ({
  api: {
    get: (...args) => mockApiGet(...args),
    post: (...args) => mockApiPost(...args),
  },
  formatApiErrorDetail: (detail) => (typeof detail === "string" ? detail : "Something went wrong. Please try again."),
}));

jest.mock("@/api/organizations", () => ({
  setOrganizationHeader: (...args) => mockSetOrganizationHeader(...args),
}));

function Probe() {
  const { user, login, register, logout, startDemo } = useAuth();
  return (
    <div>
      <div data-testid="auth-user">{user === null ? "hydrating" : user === false ? "anonymous" : user.id}</div>
      <button type="button" data-testid="login" onClick={() => login("ada@org.org", "secret1")}>
        login
      </button>
      <button
        type="button"
        data-testid="register"
        onClick={() => register({ email: "ada@org.org", password: "secret1", name: "Ada" })}
      >
        register
      </button>
      <button type="button" data-testid="logout" onClick={() => logout()}>
        logout
      </button>
      <button type="button" data-testid="start-demo" onClick={() => startDemo()}>
        start demo
      </button>
    </div>
  );
}

describe("AuthProvider session transitions", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    sessionStorage.clear();
    mockApiGet.mockRejectedValue({ response: { status: 401 } });
    mockApiPost.mockResolvedValue({ data: { ok: true } });
    mockStartDemoSession.mockReset();
  });

  it("treats a failed /auth/me as a logged-out visitor and clears workspace state", async () => {
    sessionStorage.setItem("forestwatch.selectedOrganizationId", "stale-org");
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByTestId("auth-user")).toHaveTextContent("anonymous"));
    expect(mockSetOrganizationHeader).toHaveBeenCalledWith(null);
    expect(sessionStorage.getItem("forestwatch.selectedOrganizationId")).toBeNull();
  });

  it("treats anonymous /auth/me 401 as expected probing, not a thrown user-facing error", async () => {
    mockApiGet.mockResolvedValue({ data: null, status: 401 });
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByTestId("auth-user")).toHaveTextContent("anonymous"));
    expect(mockApiGet).toHaveBeenCalledWith(
      "/auth/me",
      expect.objectContaining({ validateStatus: expect.any(Function) })
    );
    const [, options] = mockApiGet.mock.calls[0];
    expect(options.validateStatus(401)).toBe(true);
    expect(options.validateStatus(500)).toBe(false);
  });

  it("clears organization context before login and register", async () => {
    mockApiGet.mockRejectedValue({ response: { status: 401 } });
    mockApiPost.mockImplementation((url) => {
      if (url === "/auth/login") {
        return Promise.resolve({ data: { id: "user-1", email: "ada@org.org", name: "Ada" } });
      }
      if (url === "/auth/register") {
        return Promise.resolve({ data: { id: "user-2", email: "ada@org.org", name: "Ada" } });
      }
      return Promise.resolve({ data: { ok: true } });
    });
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByTestId("auth-user")).toHaveTextContent("anonymous"));
    fireEvent.click(screen.getByTestId("login"));
    await waitFor(() => expect(screen.getByTestId("auth-user")).toHaveTextContent("user-1"));
    expect(mockSetOrganizationHeader).toHaveBeenCalledWith(null);

    mockSetOrganizationHeader.mockClear();
    fireEvent.click(screen.getByTestId("register"));
    await waitFor(() => expect(screen.getByTestId("auth-user")).toHaveTextContent("user-2"));
    expect(mockSetOrganizationHeader).toHaveBeenCalledWith(null);
  });

  it("clears organization context on logout", async () => {
    mockApiGet.mockResolvedValueOnce({
      data: { id: "user-1", email: "ada@org.org", name: "Ada" },
    });
    sessionStorage.setItem("forestwatch.selectedOrganizationId", "trial-org");
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByTestId("auth-user")).toHaveTextContent("user-1"));
    fireEvent.click(screen.getByTestId("logout"));
    await waitFor(() => expect(screen.getByTestId("auth-user")).toHaveTextContent("anonymous"));
    expect(mockApiPost).toHaveBeenCalledWith("/auth/logout");
    expect(mockSetOrganizationHeader).toHaveBeenCalledWith(null);
    expect(sessionStorage.getItem("forestwatch.selectedOrganizationId")).toBeNull();
  });

  it("retries demo start after a leftover real session cookie is cleared", async () => {
    const signOutError = {
      response: {
        status: 403,
        data: { detail: "Sign out before starting the interactive demonstration", code: "forbidden" },
      },
    };
    mockStartDemoSession
      .mockRejectedValueOnce(signOutError)
      .mockResolvedValueOnce({ id: "demo:sess-2", provider: "demo", name: "Demonstration visitor" });
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByTestId("auth-user")).toHaveTextContent("anonymous"));
    fireEvent.click(screen.getByTestId("start-demo"));
    await waitFor(() => expect(screen.getByTestId("auth-user")).toHaveTextContent("demo:sess-2"));
    expect(mockApiPost).toHaveBeenCalledWith("/auth/logout");
    expect(mockStartDemoSession).toHaveBeenCalledTimes(2);
  });

  it("does not tell an already logged-out visitor to sign out again", async () => {
    const signOutError = {
      response: {
        status: 403,
        data: { detail: "Sign out before starting the interactive demonstration", code: "forbidden" },
      },
    };
    mockStartDemoSession.mockRejectedValue(signOutError);
    let startResult;
    function Capture() {
      const { startDemo } = useAuth();
      return (
        <button
          type="button"
          data-testid="capture-start"
          onClick={async () => {
            startResult = await startDemo();
          }}
        >
          start
        </button>
      );
    }
    render(
      <AuthProvider>
        <Probe />
        <Capture />
      </AuthProvider>
    );
    await waitFor(() => expect(screen.getByTestId("auth-user")).toHaveTextContent("anonymous"));
    fireEvent.click(screen.getByTestId("capture-start"));
    await waitFor(() => expect(startResult).toBeTruthy());
    expect(startResult.ok).toBe(false);
    expect(startResult.error).not.toMatch(/sign out/i);
    expect(startResult.error).toMatch(/could not be started/i);
  });
});
