import { render, screen } from "@testing-library/react";
import WeatherSummaryCard from "../WeatherSummaryCard";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_DATA = {
  generated_at: "2026-06-10T12:00:00Z",
  provider: "Open-Meteo",
  cache_ttl_minutes: 30,
  regions: [
    {
      region: "Suceava",
      temperature: 35.5,
      humidity: 25.0,
      wind_speed: 45.0,
      wind_direction: 270.0,
      precipitation: 0.0,
      weather_code: 1,
      source: "open_meteo",
      confidence: 1.0,
      updated_at: "2026-06-10T11:30:00Z",
    },
    {
      region: "Bacău",
      temperature: 28.0,
      humidity: 50.0,
      wind_speed: 20.0,
      wind_direction: 180.0,
      precipitation: 2.5,
      weather_code: 61,
      source: "open_meteo",
      confidence: 1.0,
      updated_at: "2026-06-10T11:45:00Z",
    },
    {
      region: "Cluj",
      temperature: 15.0,
      humidity: 80.0,
      wind_speed: 8.0,
      wind_direction: 90.0,
      precipitation: 5.0,
      weather_code: 63,
      source: "open_meteo",
      confidence: 1.0,
      updated_at: "2026-06-10T11:20:00Z",
    },
  ],
};

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

describe("WeatherSummaryCard — loading", () => {
  it("renders loading skeleton when loading=true", () => {
    render(<WeatherSummaryCard data={null} loading={true} />);
    expect(screen.getByTestId("weather-summary-loading")).toBeInTheDocument();
  });

  it("does not render card metrics while loading", () => {
    render(<WeatherSummaryCard data={null} loading={true} />);
    expect(screen.queryByTestId("weather-summary-card")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

describe("WeatherSummaryCard — empty", () => {
  it("renders empty message when regions array is empty", () => {
    render(<WeatherSummaryCard data={{ ...MOCK_DATA, regions: [] }} loading={false} />);
    expect(screen.getByTestId("weather-summary-empty")).toBeInTheDocument();
  });

  it("shows the cache TTL minutes in empty state", () => {
    render(<WeatherSummaryCard data={{ ...MOCK_DATA, regions: [] }} loading={false} />);
    expect(screen.getByText(/30 minutes/i)).toBeInTheDocument();
  });

  it("renders empty state when data is null", () => {
    render(<WeatherSummaryCard data={null} loading={false} />);
    expect(screen.getByTestId("weather-summary-empty")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Populated state
// ---------------------------------------------------------------------------

describe("WeatherSummaryCard — populated", () => {
  beforeEach(() => {
    render(<WeatherSummaryCard data={MOCK_DATA} loading={false} />);
  });

  it("renders the card", () => {
    expect(screen.getByTestId("weather-summary-card")).toBeInTheDocument();
  });

  it("displays highest temperature region (Suceava at 35.5°C)", () => {
    const hottest = screen.getByTestId("weather-hottest");
    expect(hottest).toBeInTheDocument();
    const value = screen.getByTestId("weather-hottest-value");
    expect(value.textContent).toMatch(/35\.5/);
    expect(hottest.textContent).toContain("Suceava");
  });

  it("displays strongest wind region (Suceava at 45 km/h)", () => {
    const windiest = screen.getByTestId("weather-windiest");
    expect(windiest).toBeInTheDocument();
    const value = screen.getByTestId("weather-windiest-value");
    expect(value.textContent).toMatch(/45/);
    expect(windiest.textContent).toContain("Suceava");
  });

  it("displays lowest humidity region (Suceava at 25%)", () => {
    const driest = screen.getByTestId("weather-driest");
    expect(driest).toBeInTheDocument();
    const value = screen.getByTestId("weather-driest-value");
    expect(value.textContent).toMatch(/25/);
    expect(driest.textContent).toContain("Suceava");
  });

  it("displays the provider name", () => {
    expect(screen.getByTestId("weather-provider").textContent).toContain("Open-Meteo");
  });

  it("shows regions count and TTL in subline", () => {
    const card = screen.getByTestId("weather-summary-card");
    expect(card.textContent).toMatch(/3 regions/);
    expect(card.textContent).toMatch(/30/);
  });
});

// ---------------------------------------------------------------------------
// Wind direction compass
// ---------------------------------------------------------------------------

describe("WeatherSummaryCard — wind compass", () => {
  it("shows compass direction for W wind (270°)", () => {
    render(<WeatherSummaryCard data={MOCK_DATA} loading={false} />);
    const value = screen.getByTestId("weather-windiest-value");
    expect(value.textContent).toContain("W");
  });
});
