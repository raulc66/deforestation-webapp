import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import InvestigationsPage from "../InvestigationsPage";
import {
  __mockNavigate,
  __resetRouterMocks,
  __setMockParams,
} from "@/test-utils/reactRouterDomMock";

jest.mock("@/lib/api", () => ({
  api: { get: jest.fn(), post: jest.fn(), patch: jest.fn(), delete: jest.fn() },
  API: "http://localhost:8000/api",
  formatApiErrorDetail: (d) => (d ? String(d) : "Something went wrong."),
}));

jest.mock("@/components/layout/AppLayout", () => ({ children }) => (
  <div data-testid="app-layout">{children}</div>
));

jest.mock("@/api/investigations", () => ({
  fetchInvestigations: jest.fn(),
  fetchInvestigation: jest.fn(),
  createInvestigation: jest.fn(),
  closeInvestigation: jest.fn(),
  archiveInvestigation: jest.fn(),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, disabled, type, ...rest }) => (
    <button onClick={onClick} disabled={disabled} type={type} {...rest}>
      {children}
    </button>
  ),
}));

const {
  fetchInvestigations,
  fetchInvestigation,
} = require("@/api/investigations");

const SAMPLE = {
  id: "inv1",
  title: "Wildfire follow-up",
  description: "Check anomaly",
  status: "open",
  priority: "high",
  region: "Suceava",
  assigned_to: null,
  organization: "",
  created_by: "user1",
  created_at: "2026-07-07T10:00:00Z",
  updated_at: "2026-07-07T10:00:00Z",
  closed_at: null,
  resolution: null,
  tags: [],
  recommended_actions: [],
  actual_actions: [],
  outcome: null,
};

describe("InvestigationsPage", () => {
  beforeEach(() => {
    __resetRouterMocks();
    __setMockParams({});
    fetchInvestigations.mockReset();
    fetchInvestigation.mockReset();
  });

  it("renders list page with investigations", async () => {
    fetchInvestigations.mockResolvedValue({ investigations: [SAMPLE], total: 1 });
    render(<InvestigationsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("investigations-page")).toBeInTheDocument();
      expect(screen.getByTestId("investigation-row-inv1")).toBeInTheDocument();
    });
    expect(screen.getByText("Wildfire follow-up")).toBeInTheDocument();
  });

  it("shows empty state", async () => {
    fetchInvestigations.mockResolvedValue({ investigations: [], total: 0 });
    render(<InvestigationsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("investigations-empty")).toBeInTheDocument();
    });
  });

  it("opens create modal from button", async () => {
    fetchInvestigations.mockResolvedValue({ investigations: [], total: 0 });
    render(<InvestigationsPage />);
    await waitFor(() => screen.getByTestId("create-investigation-btn"));
    fireEvent.click(screen.getByTestId("create-investigation-btn"));
    expect(screen.getByTestId("create-investigation-modal")).toBeInTheDocument();
  });

  it("renders detail view with timeline", async () => {
    __setMockParams({ id: "inv1" });
    fetchInvestigation.mockResolvedValue({
      investigation: SAMPLE,
      timeline: [
        {
          id: "t1",
          event_type: "investigation_created",
          message: "Investigation created",
          actor: "user1",
          created_at: "2026-07-07T10:00:00Z",
        },
      ],
    });
    render(<InvestigationsPage />);
    await waitFor(() => {
      expect(screen.getByTestId("investigation-detail")).toBeInTheDocument();
    });
    expect(screen.getByTestId("detail-title")).toHaveTextContent("Wildfire follow-up");
    expect(screen.getByTestId("investigation-timeline")).toBeInTheDocument();
  });

  it("navigates to detail after row click", async () => {
    fetchInvestigations.mockResolvedValue({ investigations: [SAMPLE], total: 1 });
    render(<InvestigationsPage />);
    await waitFor(() => screen.getByTestId("investigation-row-inv1"));
    fireEvent.click(screen.getByTestId("investigation-row-inv1"));
    expect(__mockNavigate).toHaveBeenCalledWith("/investigations/inv1");
  });
});
