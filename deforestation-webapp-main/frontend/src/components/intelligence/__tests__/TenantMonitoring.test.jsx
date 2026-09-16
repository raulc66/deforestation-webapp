import { render, screen } from "@testing-library/react";
import MonitoredAreasCard from "../MonitoredAreasCard";
import CustomerMonitoringStatusCard from "../CustomerMonitoringStatusCard";

describe("MonitoredAreasCard", () => {
  it("renders loading state", () => {
    render(<MonitoredAreasCard loading />);
    expect(screen.getByTestId("monitored-areas-loading")).toBeInTheDocument();
  });

  it("renders area count and asset list", () => {
    render(
      <MonitoredAreasCard
        areas={{
          total: 2,
          items: [
            { id: "a1", name: "Harghita Block", country: "Romania", geometry_type: "Polygon" },
            { id: "a2", name: "Suceava Forest", country: "Romania", geometry_type: "Polygon" },
          ],
        }}
      />
    );
    expect(screen.getByTestId("monitored-areas-count")).toHaveTextContent("2");
    expect(screen.getByText("Harghita Block")).toBeInTheDocument();
  });

  it("keeps long monitored-forest names wrapping on word boundaries", () => {
    render(
      <MonitoredAreasCard
        areas={{
          total: 3,
          items: [
            { id: "a1", name: "Harghita Forest Reserve", country: "Romania", geometry_type: "Polygon" },
            { id: "a2", name: "Maramureș Conservation Stand", country: "Romania", geometry_type: "Polygon" },
            { id: "a3", name: "Suceava", country: "Romania", geometry_type: "Polygon" },
          ],
        }}
      />
    );
    const harghita = screen.getByTestId("monitored-area-name-a1");
    const maramures = screen.getByTestId("monitored-area-name-a2");
    const suceava = screen.getByTestId("monitored-area-name-a3");
    expect(harghita).toHaveTextContent("Harghita Forest Reserve");
    expect(maramures).toHaveTextContent("Maramureș Conservation Stand");
    expect(suceava).toHaveTextContent("Suceava");
    expect(harghita).toHaveClass("fw-name");
    expect(maramures).toHaveClass("fw-name");
    expect(harghita.className).not.toMatch(/break-all|break-words/);
    expect(harghita.parentElement.className).not.toMatch(/min-w-0/);
  });

  it("renders empty state", () => {
    render(<MonitoredAreasCard areas={{ total: 0, items: [] }} />);
    expect(screen.getByTestId("monitored-areas-empty")).toBeInTheDocument();
  });

  it("shows entitlement limit usage", () => {
    render(
      <MonitoredAreasCard
        areas={{ total: 1, items: [{ id: "a1", name: "Forest", country: "Romania" }] }}
        entitlements={{ monitored_area_limit: 1, monitored_area_count: 1 }}
      />
    );
    expect(screen.getByTestId("monitored-areas-limit")).toBeInTheDocument();
  });
});

describe("CustomerMonitoringStatusCard", () => {
  it("shows disturbance counts and safe authorization language", () => {
    render(
      <CustomerMonitoringStatusCard
        status={{
          entitlements: { monitoring_enabled: true },
          monitored_areas: { enabled_count: 3 },
          disturbance_summary: {
            inside_monitored_area_count: 2,
            high_critical_investigation_count: 1,
            authorization_status_default: "unknown",
          },
        }}
      />
    );
    expect(screen.getByTestId("monitoring-enabled-count")).toHaveTextContent("3");
    expect(screen.getByTestId("monitoring-inside-count")).toHaveTextContent("2");
    expect(screen.getByTestId("monitoring-auth-status")).toHaveTextContent(
      /verification required/i
    );
    expect(screen.getByText(/Potential Unauthorized Forest Activity/i)).toBeInTheDocument();
    expect(screen.queryByText(/illegal logging detected/i)).not.toBeInTheDocument();
  });

  it("shows entitlement capabilities in product language", () => {
    render(
      <CustomerMonitoringStatusCard
        status={{
          entitlements: {
            monitored_area_limit: 1,
            monitored_area_count: 1,
            monitoring_enabled: true,
            forest_disturbance_enabled: true,
            evidence_correlation_enabled: false,
            live_sources_enabled: false,
            alert_delivery_enabled: false,
          },
          monitored_areas: { enabled_count: 1 },
          disturbance_summary: {
            inside_monitored_area_count: 0,
            high_critical_investigation_count: 0,
            authorization_status_default: "unknown",
          },
        }}
      />
    );
    expect(screen.getByTestId("entitlement-disturbance")).toBeInTheDocument();
    expect(screen.getByTestId("entitlement-correlation-status")).toHaveTextContent("Not enabled");
    expect(screen.queryByTestId("monitoring-org-name")).not.toBeInTheDocument();
  });
});
