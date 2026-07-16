import { render, screen, waitFor } from "@testing-library/react";
import InvestigationsCommandCenterCard from "../InvestigationsCommandCenterCard";

jest.mock("@/api/investigations", () => ({
  fetchInvestigationStatistics: jest.fn(),
}));

const { fetchInvestigationStatistics } = require("@/api/investigations");

describe("InvestigationsCommandCenterCard", () => {
  beforeEach(() => {
    fetchInvestigationStatistics.mockReset();
  });

  it("renders loading state", () => {
    fetchInvestigationStatistics.mockReturnValue(new Promise(() => {}));
    render(<InvestigationsCommandCenterCard />);
    expect(screen.getByTestId("investigations-cc-loading")).toBeInTheDocument();
  });

  it("renders investigation stats", async () => {
    fetchInvestigationStatistics.mockResolvedValue({
      open_investigations: 4,
      critical_investigations: 1,
      average_resolution_time_hours: 6.5,
      investigations_by_region: { Suceava: 2, Harghita: 2 },
    });
    render(<InvestigationsCommandCenterCard />);
    await waitFor(() => {
      expect(screen.getByTestId("investigations-open-count")).toHaveTextContent("4");
    });
    expect(screen.getByTestId("investigations-critical-count")).toHaveTextContent("1");
    expect(screen.getByTestId("investigations-avg-resolution")).toHaveTextContent("6.5h");
    expect(screen.getByTestId("investigations-region-Suceava")).toBeInTheDocument();
  });
});
