import { render, screen } from "@testing-library/react";
import OperationalStatusCard from "../OperationalStatusCard";

describe("OperationalStatusCard", () => {
  it("renders scope, cycle, and provider execution modes", () => {
    render(
      <OperationalStatusCard
        status={{
          geographic_scope: "europe",
          intelligence_cycle: { intelligence_cycle_id: "cycle-123" },
          correlation: { state: "current" },
          providers: [
            {
              provider_id: "eea.air_quality",
              display_name: "EEA Air Quality",
              current_status: "healthy",
              execution_mode: "fixture",
            },
          ],
          regions: [{ country: "Germany" }],
        }}
        loading={false}
      />
    );
    expect(screen.getByTestId("operational-status-card")).toBeInTheDocument();
    expect(screen.getByText(/europe/i)).toBeInTheDocument();
    expect(screen.getByText(/cycle-123/i)).toBeInTheDocument();
    expect(screen.getByTestId("provider-eea.air_quality")).toHaveTextContent("EEA Air Quality");
    expect(screen.getByTestId("operational-system-badge")).toHaveTextContent("Operational");
  });
});
