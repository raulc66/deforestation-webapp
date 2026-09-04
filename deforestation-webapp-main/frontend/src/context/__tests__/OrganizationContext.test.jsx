import { render, screen, waitFor } from "@testing-library/react";
import { OrganizationProvider, useOrganization } from "../OrganizationContext";
import { SELECTED_ORG_STORAGE_KEY } from "@/lib/sessionState";

let mockAuthUser = false;

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ user: mockAuthUser }),
}));

const mockFetchOrganizations = jest.fn();
const mockSetOrganizationHeader = jest.fn();

jest.mock("@/api/organizations", () => ({
  fetchOrganizations: (...args) => mockFetchOrganizations(...args),
  setOrganizationHeader: (...args) => mockSetOrganizationHeader(...args),
}));

function Probe() {
  const { selectedOrgId, currentOrganization, loading } = useOrganization();
  return (
    <div>
      <div data-testid="selected-org">{selectedOrgId || "none"}</div>
      <div data-testid="org-name">{currentOrganization?.name || "none"}</div>
      <div data-testid="org-loading">{loading ? "loading" : "idle"}</div>
    </div>
  );
}

describe("OrganizationProvider identity transitions", () => {
  beforeEach(() => {
    mockAuthUser = false;
    sessionStorage.clear();
    mockFetchOrganizations.mockReset();
    mockSetOrganizationHeader.mockReset();
  });

  it("clears organization context after logout", async () => {
    mockAuthUser = { id: "user-1", email: "ada@org.org", name: "Ada" };
    mockFetchOrganizations.mockResolvedValue({
      items: [{ id: "trial-org", name: "Carpathian Watch" }],
    });
    const { rerender } = render(
      <OrganizationProvider>
        <Probe />
      </OrganizationProvider>
    );
    await waitFor(() => expect(screen.getByTestId("selected-org")).toHaveTextContent("trial-org"));
    expect(sessionStorage.getItem(SELECTED_ORG_STORAGE_KEY)).toBe("trial-org");

    mockAuthUser = false;
    rerender(
      <OrganizationProvider>
        <Probe />
      </OrganizationProvider>
    );
    await waitFor(() => expect(screen.getByTestId("selected-org")).toHaveTextContent("none"));
    expect(mockSetOrganizationHeader).toHaveBeenCalledWith(null);
    expect(sessionStorage.getItem(SELECTED_ORG_STORAGE_KEY)).toBeNull();
  });

  it("does not keep a demonstration org header after the visitor registers", async () => {
    mockAuthUser = { id: "demo:sess-1", provider: "demo", name: "Demonstration visitor" };
    mockFetchOrganizations.mockResolvedValue({
      items: [{ id: "demo-org", name: "ForestWatch Demonstration", slug: "forestwatch-demo", kind: "demo" }],
    });
    const { rerender } = render(
      <OrganizationProvider>
        <Probe />
      </OrganizationProvider>
    );
    await waitFor(() => expect(screen.getByTestId("selected-org")).toHaveTextContent("demo-org"));

    mockFetchOrganizations.mockResolvedValue({
      items: [{ id: "trial-org", name: "Carpathian Watch" }],
    });
    mockAuthUser = { id: "user-1", email: "ada@org.org", name: "Ada", provider: "local" };
    rerender(
      <OrganizationProvider>
        <Probe />
      </OrganizationProvider>
    );
    await waitFor(() => expect(screen.getByTestId("selected-org")).toHaveTextContent("trial-org"));
    expect(mockSetOrganizationHeader).toHaveBeenCalledWith(null);
    expect(mockSetOrganizationHeader).toHaveBeenCalledWith("trial-org");
    expect(sessionStorage.getItem(SELECTED_ORG_STORAGE_KEY)).toBe("trial-org");
  });

  it("ignores a stale stored organization id after logout", async () => {
    sessionStorage.setItem(SELECTED_ORG_STORAGE_KEY, "stale-demo-org");
    mockAuthUser = false;
    render(
      <OrganizationProvider>
        <Probe />
      </OrganizationProvider>
    );
    await waitFor(() => expect(screen.getByTestId("selected-org")).toHaveTextContent("none"));
    expect(sessionStorage.getItem(SELECTED_ORG_STORAGE_KEY)).toBeNull();
    expect(mockFetchOrganizations).not.toHaveBeenCalled();
    expect(mockSetOrganizationHeader).toHaveBeenCalledWith(null);
  });
});
