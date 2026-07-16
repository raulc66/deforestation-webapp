import { render, screen, waitFor, act } from "@testing-library/react";
import RegionalWeatherSection from "../RegionalWeatherSection";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

jest.mock("@/lib/api", () => ({
  api: { get: jest.fn() },
  formatApiErrorDetail: (d) => (d ? String(d) : "Something went wrong."),
}));

jest.mock("@/api/analytics", () => ({
  fetchWeather: jest.fn(),
}));

// Stub WeatherSummaryCard to simplify RegionalWeatherSection tests
jest.mock("../WeatherSummaryCard", () => ({ data, loading }) => (
  <div data-testid="weather-summary-card-stub" />
));

const { fetchWeather } = require("@/api/analytics");

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_WEATHER = {
  generated_at: "2026-06-10T12:00:00Z",
  provider: "Open-Meteo",
  cache_ttl_minutes: 30,
  regions: [
    {
      region: "Suceava",
      temperature: 30.0,
      humidity: 35.0,
      wind_speed: 28.0,
      wind_direction: 225.0,
      precipitation: 0.0,
      weather_code: 1,
      source: "open_meteo",
      confidence: 1.0,
      updated_at: "2026-06-10T11:45:00Z",
    },
    {
      region: "Bacău",
      temperature: 24.0,
      humidity: 60.0,
      wind_speed: 12.0,
      wind_direction: 90.0,
      precipitation: 1.5,
      weather_code: 63,
      source: "open_meteo",
      confidence: 1.0,
      updated_at: "2026-06-10T11:45:00Z",
    },
  ],
};

// ---------------------------------------------------------------------------
// Loading state
// ---------------------------------------------------------------------------

describe("RegionalWeatherSection — loading", () => {
  it("shows loading skeletons while fetching", () => {
    fetchWeather.mockReturnValue(new Promise(() => {})); // never resolves
    render(<RegionalWeatherSection />);
    const skeletons = screen.getAllByTestId("weather-card-loading");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders section wrapper immediately", () => {
    fetchWeather.mockReturnValue(new Promise(() => {}));
    render(<RegionalWeatherSection />);
    expect(screen.getByTestId("regional-weather-section")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Error state
// ---------------------------------------------------------------------------

describe("RegionalWeatherSection — error", () => {
  it("shows error message when API fails", async () => {
    fetchWeather.mockRejectedValue(new Error("Network error"));
    render(<RegionalWeatherSection />);
    await waitFor(() => {
      expect(screen.getByTestId("weather-error")).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Empty cache state
// ---------------------------------------------------------------------------

describe("RegionalWeatherSection — empty cache", () => {
  it("shows empty state when regions array is empty", async () => {
    fetchWeather.mockResolvedValue({ ...MOCK_WEATHER, regions: [] });
    render(<RegionalWeatherSection />);
    await waitFor(() => {
      expect(screen.getByTestId("weather-empty")).toBeInTheDocument();
    });
  });

  it("shows TTL hint in empty state", async () => {
    fetchWeather.mockResolvedValue({ ...MOCK_WEATHER, regions: [] });
    render(<RegionalWeatherSection />);
    await waitFor(() => {
      expect(screen.getByTestId("weather-empty").textContent).toMatch(/30 minutes/i);
    });
  });
});

// ---------------------------------------------------------------------------
// Populated state
// ---------------------------------------------------------------------------

describe("RegionalWeatherSection — populated", () => {
  beforeEach(() => {
    fetchWeather.mockResolvedValue(MOCK_WEATHER);
  });

  it("renders weather cards grid after load", async () => {
    render(<RegionalWeatherSection />);
    await waitFor(() => {
      expect(screen.getByTestId("weather-cards-grid")).toBeInTheDocument();
    });
  });

  it("renders one card per region", async () => {
    render(<RegionalWeatherSection />);
    await waitFor(() => {
      expect(screen.getByTestId("weather-card-suceava")).toBeInTheDocument();
      expect(screen.getByTestId("weather-card-bacău")).toBeInTheDocument();
    });
  });

  it("displays temperature for Suceava", async () => {
    render(<RegionalWeatherSection />);
    await waitFor(() => {
      const tempDisplays = screen.getAllByTestId("temperature-display");
      const temps = tempDisplays.map((el) => el.textContent);
      expect(temps.some((t) => t.includes("30"))).toBe(true);
    });
  });

  it("renders WeatherSummaryCard stub", async () => {
    render(<RegionalWeatherSection />);
    await waitFor(() => {
      expect(screen.getByTestId("weather-summary-card-stub")).toBeInTheDocument();
    });
  });

  it("calls fetchWeather exactly once on mount", async () => {
    render(<RegionalWeatherSection />);
    await waitFor(() => {
      expect(screen.getByTestId("weather-cards-grid")).toBeInTheDocument();
    });
    expect(fetchWeather).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// Wind arrow
// ---------------------------------------------------------------------------

describe("RegionalWeatherSection — wind indicator", () => {
  it("renders wind arrow when wind_speed > 0", async () => {
    fetchWeather.mockResolvedValue(MOCK_WEATHER);
    render(<RegionalWeatherSection />);
    await waitFor(() => {
      const arrows = screen.getAllByTestId("wind-arrow");
      expect(arrows.length).toBeGreaterThan(0);
    });
  });
});
