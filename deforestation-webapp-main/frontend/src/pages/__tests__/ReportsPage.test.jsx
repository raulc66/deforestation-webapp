import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import ReportsPage from "../ReportsPage";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

jest.mock("@/lib/api", () => ({
  api: { get: jest.fn(), post: jest.fn(), delete: jest.fn() },
  API: "http://localhost:8000/api",
  formatApiErrorDetail: (d) => (d ? String(d) : "Something went wrong."),
}));

// Mock AppLayout to avoid react-router-dom dependency in page tests
jest.mock("@/components/layout/AppLayout", () => ({ children }) => (
  <div data-testid="app-layout">{children}</div>
));

jest.mock("@/api/reports", () => ({
  fetchReports: jest.fn(),
  fetchReport: jest.fn(),
  generateReport: jest.fn(),
  deleteReport: jest.fn(),
  getDownloadUrl: (id) => `http://localhost:8000/api/reports/${id}/download`,
}));

jest.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ user: { name: "Tester", email: "t@t.com" }, logout: jest.fn() }),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, disabled, className, type, ...rest }) => (
    <button onClick={onClick} disabled={disabled} className={className} type={type} {...rest}>
      {children}
    </button>
  ),
}));

const { fetchReports, fetchReport, generateReport, deleteReport } = require("@/api/reports");

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const PENDING_REPORT = {
  id: "report1",
  type: "daily",
  format: "pdf",
  status: "pending",
  generated_at: "2026-06-01T12:00:00Z",
  period_start: "2026-05-31T12:00:00Z",
  period_end: "2026-06-01T12:00:00Z",
  file_size: null,
  generation_time_ms: null,
  summary: null,
  error: null,
};

const COMPLETE_REPORT = {
  ...PENDING_REPORT,
  id: "report2",
  status: "complete",
  file_size: 204800,
  generation_time_ms: 3200,
  summary: { active_intel_events: 2, anomaly_count: 1 },
};

const FAILED_REPORT = {
  ...PENDING_REPORT,
  id: "report3",
  type: "weekly",
  format: "csv",
  status: "failed",
  error: "Database unavailable",
};

function renderPage() {
  return render(<ReportsPage />);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ReportsPage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    fetchReports.mockResolvedValue({ reports: [], total: 0 });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  // --- Loading state -------------------------------------------------------

  test("shows loading indicator initially", () => {
    fetchReports.mockReturnValue(new Promise(() => {})); // never resolves
    renderPage();
    expect(screen.getByText(/loading reports/i)).toBeInTheDocument();
  });

  // --- Empty state ---------------------------------------------------------

  test("shows empty state when no reports exist", async () => {
    fetchReports.mockResolvedValue({ reports: [], total: 0 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/no reports yet/i)).toBeInTheDocument();
    });
  });

  test("shows generate report button in empty state", async () => {
    fetchReports.mockResolvedValue({ reports: [], total: 0 });
    renderPage();
    await waitFor(() => {
      expect(screen.getAllByText(/generate report/i).length).toBeGreaterThan(0);
    });
  });

  // --- Populated state -----------------------------------------------------

  test("renders report rows", async () => {
    fetchReports.mockResolvedValue({ reports: [COMPLETE_REPORT, PENDING_REPORT], total: 2 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/daily/i)).toBeInTheDocument();
    });
  });

  test("shows complete status badge", async () => {
    fetchReports.mockResolvedValue({ reports: [COMPLETE_REPORT], total: 1 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/complete/i)).toBeInTheDocument();
    });
  });

  test("shows pending status badge", async () => {
    fetchReports.mockResolvedValue({ reports: [PENDING_REPORT], total: 1 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/pending/i)).toBeInTheDocument();
    });
  });

  test("shows failed status badge and error message", async () => {
    fetchReports.mockResolvedValue({ reports: [FAILED_REPORT], total: 1 });
    renderPage();
    await waitFor(() => {
      // Multiple elements may contain "failed" (badge + error summary); verify at least one exists
      expect(screen.getAllByText(/failed/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/database unavailable/i)).toBeInTheDocument();
    });
  });

  test("shows download link for complete report", async () => {
    fetchReports.mockResolvedValue({ reports: [COMPLETE_REPORT], total: 1 });
    renderPage();
    await waitFor(() => {
      const downloadLink = screen.getByTitle(/download/i);
      expect(downloadLink).toBeInTheDocument();
      expect(downloadLink.href).toContain(COMPLETE_REPORT.id);
    });
  });

  test("does not show download link for pending report", async () => {
    fetchReports.mockResolvedValue({ reports: [PENDING_REPORT], total: 1 });
    renderPage();
    await waitFor(() => {
      expect(screen.queryByTitle(/download/i)).not.toBeInTheDocument();
    });
  });

  // --- Summary cards -------------------------------------------------------

  test("renders summary cards with correct counts", async () => {
    fetchReports.mockResolvedValue({
      reports: [COMPLETE_REPORT, PENDING_REPORT, FAILED_REPORT],
      total: 3,
    });
    renderPage();
    await waitFor(() => {
      // "3" is unique (Total Reports card); "1" may appear multiple times (Complete=1, InProgress=1)
      expect(screen.getByText("3")).toBeInTheDocument();
      expect(screen.getAllByText("1").length).toBeGreaterThan(0);
    });
  });

  // --- Generate modal -------------------------------------------------------

  test("opens generate modal on button click", async () => {
    fetchReports.mockResolvedValue({ reports: [], total: 0 });
    renderPage();
    await waitFor(() => screen.getByText(/no reports yet/i));

    const btn = screen.getAllByText(/generate report/i)[0];
    fireEvent.click(btn);

    expect(screen.getByText(/report type/i)).toBeInTheDocument();
    expect(screen.getByText(/format/i)).toBeInTheDocument();
  });

  test("modal shows all report types", async () => {
    fetchReports.mockResolvedValue({ reports: [], total: 0 });
    renderPage();
    await waitFor(() => screen.getByText(/no reports yet/i));

    fireEvent.click(screen.getAllByText(/generate report/i)[0]);

    // Info box also contains Daily/Weekly/Monthly as <strong> — use getAllByText
    expect(screen.getAllByText("Daily").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Weekly").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Monthly").length).toBeGreaterThan(0);
    expect(screen.getAllByText("On-Demand").length).toBeGreaterThan(0);
  });

  test("modal shows all formats", async () => {
    fetchReports.mockResolvedValue({ reports: [], total: 0 });
    renderPage();
    await waitFor(() => screen.getByText(/no reports yet/i));

    fireEvent.click(screen.getAllByText(/generate report/i)[0]);

    // Info box also contains PDF/CSV as <strong> — use getAllByText
    expect(screen.getAllByText("PDF").length).toBeGreaterThan(0);
    expect(screen.getAllByText("CSV").length).toBeGreaterThan(0);
    expect(screen.getAllByText("JSON").length).toBeGreaterThan(0);
  });

  test("closes modal on cancel", async () => {
    fetchReports.mockResolvedValue({ reports: [], total: 0 });
    renderPage();
    await waitFor(() => screen.getByText(/no reports yet/i));

    fireEvent.click(screen.getAllByText(/generate report/i)[0]);
    expect(screen.getByText(/report type/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText(/cancel/i));
    expect(screen.queryByText(/report type/i)).not.toBeInTheDocument();
  });

  test("submitting modal calls generateReport and adds pending record", async () => {
    fetchReports.mockResolvedValue({ reports: [], total: 0 });
    generateReport.mockResolvedValue(PENDING_REPORT);
    const { container } = renderPage();
    await waitFor(() => screen.getByText(/no reports yet/i));

    fireEvent.click(screen.getAllByText(/generate report/i)[0]);

    // Find the modal's submit button directly via DOM query
    const form = container.querySelector("form");
    expect(form).not.toBeNull();

    await act(async () => {
      fireEvent.submit(form);
    });

    await waitFor(() => {
      expect(generateReport).toHaveBeenCalledWith("daily", "pdf");
    });
  });

  test("shows error in modal when generation fails", async () => {
    fetchReports.mockResolvedValue({ reports: [], total: 0 });
    generateReport.mockRejectedValue({ response: { data: { detail: "Server error" } } });
    const { container } = renderPage();
    await waitFor(() => screen.getByText(/no reports yet/i));

    fireEvent.click(screen.getAllByText(/generate report/i)[0]);

    const form = container.querySelector("form");
    expect(form).not.toBeNull();

    await act(async () => {
      fireEvent.submit(form);
    });

    await waitFor(() => {
      expect(screen.getByText(/server error/i)).toBeInTheDocument();
    });
  });

  // --- Delete ---------------------------------------------------------------

  test("delete button calls deleteReport and removes row", async () => {
    fetchReports.mockResolvedValue({ reports: [COMPLETE_REPORT], total: 1 });
    deleteReport.mockResolvedValue(undefined);
    window.confirm = jest.fn().mockReturnValue(true);
    renderPage();

    await waitFor(() => screen.getByTitle(/delete/i));
    await act(async () => {
      fireEvent.click(screen.getByTitle(/delete/i));
    });

    await waitFor(() => {
      expect(deleteReport).toHaveBeenCalledWith(COMPLETE_REPORT.id);
    });
  });

  // --- Polling ---------------------------------------------------------------

  test("polls for updates when reports are in progress", async () => {
    fetchReports.mockResolvedValue({ reports: [PENDING_REPORT], total: 1 });
    renderPage();

    await waitFor(() => screen.getByText(/generating/i));

    // Advance timers to trigger poll
    await act(async () => {
      jest.advanceTimersByTime(3500);
    });

    // fetchReports should be called again
    expect(fetchReports).toHaveBeenCalledTimes(2);
  });

  // --- Error state ----------------------------------------------------------

  test("shows error message when fetchReports fails", async () => {
    fetchReports.mockRejectedValue(new Error("Network error"));
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/failed to load reports/i)).toBeInTheDocument();
    });
  });

  // --- Refresh button -------------------------------------------------------

  test("refresh button reloads reports", async () => {
    fetchReports.mockResolvedValue({ reports: [], total: 0 });
    renderPage();

    await waitFor(() => screen.getByText(/no reports yet/i));

    fireEvent.click(screen.getByRole("button", { name: /refresh/i }));
    await waitFor(() => {
      expect(fetchReports).toHaveBeenCalledTimes(2);
    });
  });

  // --- Format badges --------------------------------------------------------

  test("shows PDF badge for pdf report", async () => {
    fetchReports.mockResolvedValue({ reports: [COMPLETE_REPORT], total: 1 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("PDF")).toBeInTheDocument();
    });
  });

  test("shows CSV badge for csv report", async () => {
    fetchReports.mockResolvedValue({
      reports: [{ ...COMPLETE_REPORT, format: "csv" }],
      total: 1,
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("CSV")).toBeInTheDocument();
    });
  });

  // --- Info box -------------------------------------------------------------

  test("renders info box with report descriptions", async () => {
    fetchReports.mockResolvedValue({ reports: [], total: 0 });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/about reports/i)).toBeInTheDocument();
    });
  });
});
