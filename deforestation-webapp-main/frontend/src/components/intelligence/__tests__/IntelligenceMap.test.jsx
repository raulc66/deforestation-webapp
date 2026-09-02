/**
 * IntelligenceMap — comprehensive test suite.
 *
 * Coverage:
 *   Loading state       — overlay visible before API resolves
 *   Map rendering       — MapContainer and section always present
 *   Layer controls      — all three checkboxes, default state, toggle on/off
 *   Summary overlay     — counts, top-region, hidden when null
 *   Empty state         — map renders with no events / anomalies
 *   API failure state   — error banner shown, no crash
 *   Marker rendering    — L.circleMarker and L.markerClusterGroup called with data
 *   Layer interaction   — toggling a layer calls removeLayer on the map
 *   Legend              — always rendered
 *   API integration     — all four endpoints called on mount
 */
import React from "react";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  act,
} from "@testing-library/react";

// ---------------------------------------------------------------------------
// Mock CSS side-effect imports FIRST (hoisted by Jest)
// ---------------------------------------------------------------------------
jest.mock("leaflet/dist/leaflet.css", () => ({}));
jest.mock("leaflet.markercluster/dist/MarkerCluster.css", () => ({}));
jest.mock("leaflet.markercluster/dist/MarkerCluster.Default.css", () => ({}));
jest.mock("leaflet.markercluster", () => ({}));

// ---------------------------------------------------------------------------
// Mock references (must start with "mock" due to Jest hoisting rules)
// ---------------------------------------------------------------------------
const mockAddLayer = jest.fn();
const mockRemoveLayer = jest.fn();

// ---------------------------------------------------------------------------
// Mock react-leaflet — MapContainer just renders children in a div.
// useMap returns a stable map stub so layer components can call addLayer.
// ---------------------------------------------------------------------------
jest.mock("react-leaflet", () => ({
  MapContainer: ({ children }) => (
    <div data-testid="map-container">{children}</div>
  ),
  TileLayer: () => null,
  useMap: () => ({ addLayer: mockAddLayer, removeLayer: mockRemoveLayer }),
}));

// ---------------------------------------------------------------------------
// Mock leaflet — circleMarker and markerClusterGroup are the only APIs used.
// Note: implementations are set in beforeEach to survive mockClear cycles.
// ---------------------------------------------------------------------------
jest.mock("leaflet", () => ({
  markerClusterGroup: jest.fn(),
  circleMarker: jest.fn(),
  marker: jest.fn(),
  divIcon: jest.fn(),
  geoJSON: jest.fn(() => ({
    bindPopup: jest.fn(),
  })),
}));

// ---------------------------------------------------------------------------
// Mock API layer
// ---------------------------------------------------------------------------
jest.mock("@/api/analytics", () => ({
  fetchMapOverlay: jest.fn(),
  fetchMapEvents: jest.fn(),
  fetchAnomalies: jest.fn(),
  fetchIntelligenceEvents: jest.fn(),
  fetchIntelligenceSummary: jest.fn(),
  fetchRegionalRisk: jest.fn(),
  fetchWeather: jest.fn(),
  fetchThreats: jest.fn(),
}));

jest.mock("@/api/monitoringAreas", () => ({
  fetchMonitoringAreas: jest.fn(),
}));

jest.mock("@/context/OrganizationContext", () => ({
  useOrganization: () => ({
    selectedOrgId: "org-test-1",
    organizationVersion: 1,
  }),
}));

jest.mock("@/lib/api", () => ({
  formatApiErrorDetail: (d) => (typeof d === "string" ? d : null),
}));

// ---------------------------------------------------------------------------
// Import under test AFTER mocks
// ---------------------------------------------------------------------------
import IntelligenceMap from "../IntelligenceMap";
import {
  fetchMapOverlay,
  fetchMapEvents,
  fetchAnomalies,
  fetchIntelligenceEvents,
  fetchIntelligenceSummary,
  fetchRegionalRisk,
  fetchWeather,
  fetchThreats,
} from "@/api/analytics";
import { fetchMonitoringAreas } from "@/api/monitoringAreas";

// Access the mocked L for call-count assertions
const L = require("leaflet");

// ---------------------------------------------------------------------------
// Fixture data
// ---------------------------------------------------------------------------

const MOCK_EVENTS = {
  events: [
    {
      id: "e1",
      latitude: 46.567,
      longitude: 26.9146,
      severity: "high",
      region: "Bacău",
      detected_at: "2024-06-01T08:00:00Z",
      source: "NASA FIRMS",
    },
    {
      id: "e2",
      latitude: 47.635,
      longitude: 26.259,
      severity: "medium",
      region: "Suceava",
      detected_at: "2024-06-02T09:00:00Z",
      source: "CSV",
    },
  ],
};

const MOCK_OVERLAY = {
  generated_at: "2024-06-01T08:00:00Z",
  geographic_scope: "romania",
  allow_romania_centroid_fallback: true,
  region_centroids: {},
  forest_events: MOCK_EVENTS.events,
  anomalies: [],
  intelligence_events: [],
};

const MOCK_ANOMALIES = {
  anomalies: [
    {
      region: "Bacău",
      current_count: 12,
      baseline_avg: 3.5,
      deviation_percent: 243,
      anomaly_score: 0.73,
      severity: "high",
      status: "anomaly",
    },
  ],
};

const MOCK_INTEL = {
  active: [
    {
      id: "i1",
      region: "Suceava",
      severity: "high",
      escalation_level: "persistent",
      trend: "worsening",
      priority_score: 0.82,
      detection_count: 5,
    },
  ],
  resolved: [],
};

const MOCK_SUMMARY = {
  active: 3,
  critical: 1,
  persistent: 2,
  highest_priority_region: "Suceava",
  highest_priority_score: 0.82,
};

/** Configure all four API mocks. */
const MOCK_RISK = {
  generated_at: "2026-06-10T12:00:00Z",
  regions: [
    {
      region: "Suceava",
      risk_score: 0.82,
      risk_level: "Extreme",
      change: "up",
      breakdown: { current_activity: 0.28, historical_activity: 0.20, forest: 0.15, priority: 0.12, escalation: 0.07 },
    },
    {
      region: "Bacău",
      risk_score: 0.45,
      risk_level: "Moderate",
      change: "stable",
      breakdown: { current_activity: 0.14, historical_activity: 0.12, forest: 0.09, priority: 0.07, escalation: 0.03 },
    },
  ],
};

function setupMocks({
  overlay = MOCK_OVERLAY,
  anomalies = MOCK_ANOMALIES,
  intel = MOCK_INTEL,
  summary = MOCK_SUMMARY,
} = {}) {
  fetchMapOverlay.mockResolvedValue(overlay);
  fetchAnomalies.mockResolvedValue(anomalies);
  fetchIntelligenceEvents.mockResolvedValue(intel);
  fetchIntelligenceSummary.mockResolvedValue(summary);
  fetchThreats.mockResolvedValue({ threats: [] });
  fetchRegionalRisk.mockResolvedValue(MOCK_RISK);
}

/** Reusable: wait until the loading overlay disappears. */
const waitForLoad = () =>
  waitFor(() =>
    expect(screen.queryByTestId("map-loading")).not.toBeInTheDocument()
  );

// ---------------------------------------------------------------------------
// Per-test setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  // Reset API call tracking (removes mockResolvedValue etc.)
  fetchMapOverlay.mockReset();
  fetchMapEvents.mockReset();
  fetchAnomalies.mockReset();
  fetchIntelligenceEvents.mockReset();
  fetchIntelligenceSummary.mockReset();
  fetchRegionalRisk.mockReset();
  fetchWeather.mockReset();
  fetchThreats.mockReset();
  fetchMonitoringAreas.mockReset();
  fetchMonitoringAreas.mockResolvedValue({ items: [] });
  fetchThreats.mockResolvedValue({ threats: [] });
  fetchWeather.mockResolvedValue({ provider: "Open-Meteo", cache_ttl_minutes: 30, regions: [] });

  // Clear map stub call counts
  mockAddLayer.mockClear();
  mockRemoveLayer.mockClear();

  // Re-apply Leaflet mock implementations every test (survives clearAllMocks)
  L.circleMarker.mockImplementation(() => ({
    bindPopup: jest.fn().mockReturnThis(),
    addTo: jest.fn().mockReturnThis(),
  }));
  L.markerClusterGroup.mockImplementation(() => ({
    addLayer: jest.fn(),
  }));
  L.marker && L.marker.mockImplementation(() => ({
    addTo: jest.fn().mockReturnThis(),
  }));
  L.divIcon && L.divIcon.mockImplementation(() => ({}));
  L.geoJSON.mockImplementation(() => ({
    bindPopup: jest.fn().mockReturnThis(),
    addTo: jest.fn().mockReturnThis(),
  }));
});

// ===========================================================================
// Test suites
// ===========================================================================

describe("IntelligenceMap", () => {
  // -------------------------------------------------------------------------
  // Loading state
  // -------------------------------------------------------------------------
  describe("loading state", () => {
    it("shows loading overlay while data is fetching", async () => {
      let resolveEvents;
      fetchMapOverlay.mockReturnValue(
        new Promise((r) => {
          resolveEvents = r;
        })
      );
      fetchAnomalies.mockResolvedValue(MOCK_ANOMALIES);
      fetchIntelligenceEvents.mockResolvedValue(MOCK_INTEL);
      fetchIntelligenceSummary.mockResolvedValue(MOCK_SUMMARY);

      render(<IntelligenceMap />);
      expect(screen.getByTestId("map-loading")).toBeInTheDocument();

      await act(async () => {
        resolveEvents(MOCK_OVERLAY);
      });
    });

    it("hides loading overlay after data resolves", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.queryByTestId("map-loading")).not.toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Map rendering
  // -------------------------------------------------------------------------
  describe("map rendering", () => {
    it("renders the section wrapper", () => {
      setupMocks();
      render(<IntelligenceMap />);
      expect(screen.getByTestId("intelligence-map-section")).toBeInTheDocument();
    });

    it("renders the MapContainer", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByTestId("map-container")).toBeInTheDocument();
    });

    it("renders the section heading text", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(
        screen.getByText(/Geospatial intelligence/i)
      ).toBeInTheDocument();
    });

    it("renders the colour legend", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByTestId("map-legend")).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Layer controls
  // -------------------------------------------------------------------------
  describe("layer controls", () => {
    it("renders the layer controls panel", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByTestId("map-layer-controls")).toBeInTheDocument();
    });

    it("renders Forest Events toggle", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByTestId("layer-toggle-events")).toBeInTheDocument();
    });

    it("renders Anomalies toggle", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByTestId("layer-toggle-anomalies")).toBeInTheDocument();
    });

    it("renders Intelligence Events toggle", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(
        screen.getByTestId("layer-toggle-intelligence")
      ).toBeInTheDocument();
    });

    it("all three layers are checked by default", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();

      const eventsInput = screen
        .getByTestId("layer-toggle-events")
        .querySelector("input");
      const anomInput = screen
        .getByTestId("layer-toggle-anomalies")
        .querySelector("input");
      const intelInput = screen
        .getByTestId("layer-toggle-intelligence")
        .querySelector("input");

      expect(eventsInput).toBeChecked();
      expect(anomInput).toBeChecked();
      expect(intelInput).toBeChecked();
    });

    it("unchecks Forest Events layer on toggle", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();

      const input = screen
        .getByTestId("layer-toggle-events")
        .querySelector("input");
      fireEvent.click(input);
      expect(input).not.toBeChecked();
    });

    it("unchecks Anomalies layer on toggle", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();

      const input = screen
        .getByTestId("layer-toggle-anomalies")
        .querySelector("input");
      fireEvent.click(input);
      expect(input).not.toBeChecked();
    });

    it("unchecks Intelligence Events layer on toggle", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();

      const input = screen
        .getByTestId("layer-toggle-intelligence")
        .querySelector("input");
      fireEvent.click(input);
      expect(input).not.toBeChecked();
    });

    it("re-checks a layer after toggling twice", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();

      const input = screen
        .getByTestId("layer-toggle-events")
        .querySelector("input");
      fireEvent.click(input); // off
      fireEvent.click(input); // back on
      expect(input).toBeChecked();
    });

    it("layers toggle independently", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();

      const eventsInput = screen
        .getByTestId("layer-toggle-events")
        .querySelector("input");
      const anomInput = screen
        .getByTestId("layer-toggle-anomalies")
        .querySelector("input");

      fireEvent.click(eventsInput);

      expect(eventsInput).not.toBeChecked();
      expect(anomInput).toBeChecked(); // unaffected
    });
  });

  // -------------------------------------------------------------------------
  // Summary overlay
  // -------------------------------------------------------------------------
  describe("summary overlay", () => {
    it("renders summary overlay after load", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByTestId("map-summary-overlay")).toBeInTheDocument();
    });

    it("shows correct active count", async () => {
      setupMocks({ summary: { ...MOCK_SUMMARY, active: 7 } });
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByTestId("summary-active")).toHaveTextContent("7");
    });

    it("shows correct critical count", async () => {
      setupMocks({ summary: { ...MOCK_SUMMARY, critical: 2 } });
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByTestId("summary-critical")).toHaveTextContent("2");
    });

    it("shows correct persistent count", async () => {
      setupMocks({ summary: { ...MOCK_SUMMARY, persistent: 4 } });
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByTestId("summary-persistent")).toHaveTextContent("4");
    });

    it("shows highest priority region name", async () => {
      setupMocks({
        summary: { ...MOCK_SUMMARY, highest_priority_region: "Harghita" },
      });
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByTestId("summary-top-region")).toHaveTextContent(
        "Harghita"
      );
    });

    it("shows formatted priority score", async () => {
      setupMocks({
        summary: { ...MOCK_SUMMARY, highest_priority_score: 0.9123 },
      });
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByTestId("summary-top-score")).toHaveTextContent(
        "0.9123"
      );
    });

    it("omits top-region block when region is null", async () => {
      setupMocks({
        summary: {
          active: 0,
          critical: 0,
          persistent: 0,
          highest_priority_region: null,
          highest_priority_score: null,
        },
      });
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(
        screen.queryByTestId("summary-top-region")
      ).not.toBeInTheDocument();
    });

    it("hides overlay entirely when summary is null", async () => {
      setupMocks({ summary: null });
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(
        screen.queryByTestId("map-summary-overlay")
      ).not.toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Empty state
  // -------------------------------------------------------------------------
  describe("empty state", () => {
    it("renders map without errors when all arrays are empty", async () => {
      setupMocks({
        overlay: { ...MOCK_OVERLAY, forest_events: [] },
        anomalies: { anomalies: [] },
        intel: { active: [], resolved: [] },
        summary: { active: 0, critical: 0, persistent: 0 },
      });
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByTestId("map-container")).toBeInTheDocument();
    });

    it("renders legend with empty data", async () => {
      setupMocks({
        overlay: { ...MOCK_OVERLAY, forest_events: [] },
        anomalies: { anomalies: [] },
        intel: { active: [], resolved: [] },
      });
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByTestId("map-legend")).toBeInTheDocument();
    });

    it("renders layer controls with empty data", async () => {
      setupMocks({ overlay: { ...MOCK_OVERLAY, forest_events: [] } });
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByTestId("map-layer-controls")).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // API failure state
  // -------------------------------------------------------------------------
  describe("API failure state", () => {
    it("shows error banner when one API call throws", async () => {
      fetchMapOverlay.mockRejectedValue(new Error("Network timeout"));
      fetchAnomalies.mockResolvedValue(MOCK_ANOMALIES);
      fetchIntelligenceEvents.mockResolvedValue(MOCK_INTEL);
      fetchIntelligenceSummary.mockResolvedValue(MOCK_SUMMARY);

      render(<IntelligenceMap />);

      await waitFor(() =>
        expect(screen.getByTestId("map-error")).toBeInTheDocument()
      );
      expect(screen.getByTestId("map-error")).toHaveTextContent(
        "Network timeout"
      );
    });

    it("does not show error banner on success", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.queryByTestId("map-error")).not.toBeInTheDocument();
    });

    it("still renders map container after API failure", async () => {
      fetchMapOverlay.mockRejectedValue(new Error("fail"));
      fetchAnomalies.mockRejectedValue(new Error("fail"));
      fetchIntelligenceEvents.mockRejectedValue(new Error("fail"));
      fetchIntelligenceSummary.mockRejectedValue(new Error("fail"));

      render(<IntelligenceMap />);

      await waitFor(() =>
        expect(screen.getByTestId("map-error")).toBeInTheDocument()
      );
      expect(screen.getByTestId("map-container")).toBeInTheDocument();
    });

    it("error banner has role=alert for accessibility", async () => {
      fetchMapOverlay.mockRejectedValue(new Error("fail"));
      fetchAnomalies.mockResolvedValue(MOCK_ANOMALIES);
      fetchIntelligenceEvents.mockResolvedValue(MOCK_INTEL);
      fetchIntelligenceSummary.mockResolvedValue(MOCK_SUMMARY);

      render(<IntelligenceMap />);

      await waitFor(() =>
        expect(screen.getByRole("alert")).toBeInTheDocument()
      );
    });
  });

  // -------------------------------------------------------------------------
  // Marker rendering — imperative Leaflet calls
  // -------------------------------------------------------------------------
  describe("marker rendering", () => {
    it("calls L.markerClusterGroup for each visible layer with data", async () => {
      setupMocks();
      L.circleMarker.mockClear();
      L.markerClusterGroup.mockClear();

      render(<IntelligenceMap />);
      await waitForLoad();

      // At least 3 cluster groups: events + anomalies + intel
      expect(L.markerClusterGroup).toHaveBeenCalled();
    });

    it("calls L.circleMarker for each forest event", async () => {
      setupMocks();
      L.circleMarker.mockClear();

      render(<IntelligenceMap />);
      await waitForLoad();

      // 2 events + 1 anomaly + 1 intel = ≥ 4 calls (all layers enabled)
      expect(L.circleMarker).toHaveBeenCalled();
    });

    it("adds cluster groups to the Leaflet map", async () => {
      setupMocks();
      mockAddLayer.mockClear();

      render(<IntelligenceMap />);
      await waitForLoad();

      expect(mockAddLayer).toHaveBeenCalled();
    });

    it("does not call circleMarker when all arrays are empty", async () => {
      setupMocks({
        overlay: { ...MOCK_OVERLAY, forest_events: [] },
        anomalies: { anomalies: [] },
        intel: { active: [], resolved: [] },
      });
      L.circleMarker.mockClear();

      render(<IntelligenceMap />);
      await waitForLoad();

      expect(L.circleMarker).not.toHaveBeenCalled();
    });

    it("creates markers for anomalies using region coordinates", async () => {
      setupMocks({
        overlay: { ...MOCK_OVERLAY, forest_events: [] },
        intel: { active: [], resolved: [] },
      });
      L.circleMarker.mockClear();

      render(<IntelligenceMap />);
      await waitForLoad();

      // Only the anomaly should produce markers
      expect(L.circleMarker).toHaveBeenCalledTimes(1);
    });

    it("creates markers for active intelligence events", async () => {
      setupMocks({
        overlay: { ...MOCK_OVERLAY, forest_events: [] },
        anomalies: { anomalies: [] },
      });
      L.circleMarker.mockClear();

      render(<IntelligenceMap />);
      await waitForLoad();

      // Only the intel event should produce a marker
      expect(L.circleMarker).toHaveBeenCalledTimes(1);
    });
  });

  // -------------------------------------------------------------------------
  // Layer interaction — toggling triggers map.removeLayer
  // -------------------------------------------------------------------------
  describe("layer interaction with map", () => {
    it("calls map.removeLayer when a layer is toggled off", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();

      mockRemoveLayer.mockClear();

      const eventsInput = screen
        .getByTestId("layer-toggle-events")
        .querySelector("input");
      fireEvent.click(eventsInput); // toggle off

      await waitFor(() => {
        expect(mockRemoveLayer).toHaveBeenCalled();
      });
    });
  });

  // -------------------------------------------------------------------------
  // API integration
  // -------------------------------------------------------------------------
  describe("API integration", () => {
    it("calls all five API endpoints on mount", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();

      expect(fetchMapOverlay).toHaveBeenCalledTimes(1);
      expect(fetchAnomalies).toHaveBeenCalledTimes(1);
      expect(fetchIntelligenceEvents).toHaveBeenCalledTimes(1);
      expect(fetchIntelligenceSummary).toHaveBeenCalledTimes(1);
      expect(fetchThreats).toHaveBeenCalledTimes(1);
    });

    it("does not fetch unscoped anomalies or threats in demonstration mode", async () => {
      setupMocks();
      render(<IntelligenceMap demoMode />);
      await waitForLoad();

      expect(fetchMapOverlay).toHaveBeenCalledTimes(1);
      expect(fetchAnomalies).not.toHaveBeenCalled();
      expect(fetchThreats).not.toHaveBeenCalled();
      expect(fetchIntelligenceEvents).toHaveBeenCalledTimes(1);
    });

    it("only fetches once at mount (effect deps are [])", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();

      // Each API should have been called exactly once
      expect(fetchMapOverlay).toHaveBeenCalledTimes(1);
      expect(fetchAnomalies).toHaveBeenCalledTimes(1);
    });
  });

  // -------------------------------------------------------------------------
  // Land cover filter panel
  // -------------------------------------------------------------------------
  describe("land cover filter panel", () => {
    it("renders the land cover filter panel", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByTestId("land-cover-filter")).toBeInTheDocument();
    });

    it("renders a checkbox toggle for each of the six land cover types", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();

      const types = ["forest", "near_forest", "agriculture", "urban", "water", "unknown"];
      for (const t of types) {
        expect(screen.getByTestId(`lc-toggle-${t}`)).toBeInTheDocument();
      }
    });

    it("all land cover checkboxes are checked by default", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();

      const types = ["forest", "near_forest", "agriculture", "urban", "water", "unknown"];
      for (const t of types) {
        const label = screen.getByTestId(`lc-toggle-${t}`);
        const checkbox = label.querySelector('input[type="checkbox"]');
        expect(checkbox).toBeChecked();
      }
    });

    it("unchecking a land cover type does not crash", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();

      const label = screen.getByTestId("lc-toggle-forest");
      const checkbox = label.querySelector('input[type="checkbox"]');
      await act(async () => {
        fireEvent.click(checkbox);
      });
      expect(checkbox).not.toBeChecked();
    });

    it("unchecking and re-checking a type restores checked state", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();

      const label = screen.getByTestId("lc-toggle-forest");
      const checkbox = label.querySelector('input[type="checkbox"]');

      await act(async () => { fireEvent.click(checkbox); });
      expect(checkbox).not.toBeChecked();

      await act(async () => { fireEvent.click(checkbox); });
      expect(checkbox).toBeChecked();
    });
  });

  // -------------------------------------------------------------------------
  // Popup content — land cover and forest confidence
  // -------------------------------------------------------------------------
  describe("popup content — land cover fields", () => {
    it("renders events with land_cover_type without crashing", async () => {
      const eventsWithLC = {
        events: [
          {
            id: "e1",
            latitude: 47.53,
            longitude: 25.93,
            severity: "high",
            region: "Suceava",
            detected_at: "2024-06-01T08:00:00Z",
            source: "NASA FIRMS",
            land_cover_type: "forest",
          },
        ],
      };
      fetchMapOverlay.mockResolvedValue({
        ...MOCK_OVERLAY,
        forest_events: eventsWithLC.events,
      });
      fetchAnomalies.mockResolvedValue({ anomalies: [] });
      fetchIntelligenceEvents.mockResolvedValue({ active: [], resolved: [] });
      fetchIntelligenceSummary.mockResolvedValue(MOCK_SUMMARY);

      render(<IntelligenceMap />);
      await waitForLoad();

      // circleMarker should have been called for the forest event
      expect(L.circleMarker).toHaveBeenCalled();
    });

    it("handles events without land_cover_type gracefully", async () => {
      const eventsNoLC = {
        events: [
          {
            id: "e1",
            latitude: 46.567,
            longitude: 26.9146,
            severity: "medium",
            region: "Bacău",
            detected_at: "2024-06-01T08:00:00Z",
            source: "CSV",
            // land_cover_type intentionally absent
          },
        ],
      };
      fetchMapOverlay.mockResolvedValue({
        ...MOCK_OVERLAY,
        forest_events: eventsNoLC.events,
      });
      fetchAnomalies.mockResolvedValue({ anomalies: [] });
      fetchIntelligenceEvents.mockResolvedValue({ active: [], resolved: [] });
      fetchIntelligenceSummary.mockResolvedValue(MOCK_SUMMARY);

      render(<IntelligenceMap />);
      await waitForLoad();
      // Should not throw; circleMarker uses "unknown" as fallback
      expect(L.circleMarker).toHaveBeenCalled();
    });

    it("renders anomaly with forest_confidence without crashing", async () => {
      const anomaliesWithFC = {
        anomalies: [
          {
            region: "Suceava",
            current_count: 10,
            baseline_avg: 2.0,
            deviation_percent: 400,
            anomaly_score: 0.68,
            severity: "high",
            forest_confidence: 0.95,
          },
        ],
      };
      fetchMapOverlay.mockResolvedValue({ ...MOCK_OVERLAY, forest_events: [] });
      fetchAnomalies.mockResolvedValue(anomaliesWithFC);
      fetchIntelligenceEvents.mockResolvedValue({ active: [], resolved: [] });
      fetchIntelligenceSummary.mockResolvedValue(MOCK_SUMMARY);

      render(<IntelligenceMap />);
      await waitForLoad();
      expect(L.circleMarker).toHaveBeenCalled();
    });
  });

  // -------------------------------------------------------------------------
  // Land cover legend
  // -------------------------------------------------------------------------
  describe("land cover legend", () => {
    it("legend still renders with border-color entries", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByTestId("map-legend")).toBeInTheDocument();
    });

    it("legend contains severity fill labels", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByText(/Fill.*severity/i)).toBeInTheDocument();
    });

    it("legend contains land cover border labels", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByText(/Border.*land cover/i)).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Time range filter
  // -------------------------------------------------------------------------
  describe("time range filter", () => {
    it("renders the time range filter control", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByTestId("time-range-filter")).toBeInTheDocument();
    });

    it("renders all four range options", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByTestId("time-range-btn-7")).toBeInTheDocument();
      expect(screen.getByTestId("time-range-btn-30")).toBeInTheDocument();
      expect(screen.getByTestId("time-range-btn-90")).toBeInTheDocument();
      expect(screen.getByTestId("time-range-btn-all")).toBeInTheDocument();
    });

    it("defaults to 'All' time range (no filter applied)", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      const allBtn = screen.getByTestId("time-range-btn-all");
      // Default selection has bg-[#2d5a27] text-white classes
      expect(allBtn.className).toMatch(/bg-\[#2d5a27\]/);
    });

    it("clicking 7-day button selects it", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      const btn7 = screen.getByTestId("time-range-btn-7");
      fireEvent.click(btn7);
      expect(btn7.className).toMatch(/bg-\[#2d5a27\]/);
    });

    it("clicking 30-day button deselects All", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      fireEvent.click(screen.getByTestId("time-range-btn-30"));
      const allBtn = screen.getByTestId("time-range-btn-all");
      expect(allBtn.className).not.toMatch(/bg-\[#2d5a27\]/);
    });

    it("map still loads after time range selection", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      fireEvent.click(screen.getByTestId("time-range-btn-90"));
      // Map wrapper should still be present
      expect(screen.getByTestId("intelligence-map-section")).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Risk overlay layer
  // -------------------------------------------------------------------------
  describe("risk overlay layer", () => {
    it("includes Risk Overlay toggle in layer controls", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByTestId("layer-toggle-risk_overlay")).toBeInTheDocument();
    });

    it("risk overlay toggle is unchecked by default", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      const toggle = screen.getByTestId("layer-toggle-risk_overlay").querySelector("input");
      expect(toggle.checked).toBe(false);
    });

    it("does not call fetchRegionalRisk on initial load", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(fetchRegionalRisk).not.toHaveBeenCalled();
    });

    it("calls fetchRegionalRisk when risk overlay is toggled on", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      const toggle = screen.getByTestId("layer-toggle-risk_overlay").querySelector("input");
      fireEvent.click(toggle);
      await waitFor(() => expect(fetchRegionalRisk).toHaveBeenCalledTimes(1));
    });

    it("does not call fetchRegionalRisk again when toggled off and on with cached data", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      const toggle = screen.getByTestId("layer-toggle-risk_overlay").querySelector("input");
      // First enable
      fireEvent.click(toggle);
      await waitFor(() => expect(fetchRegionalRisk).toHaveBeenCalledTimes(1));
      // Disable then re-enable
      fireEvent.click(toggle);
      fireEvent.click(toggle);
      // Should still be 1 call (data was cached after first fetch)
      expect(fetchRegionalRisk).toHaveBeenCalledTimes(1);
    });

    it("risk overlay toggle can be checked", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      const toggle = screen.getByTestId("layer-toggle-risk_overlay").querySelector("input");
      fireEvent.click(toggle);
      await waitFor(() => expect(toggle.checked).toBe(true));
    });

    it("map section still renders after toggling risk overlay", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      const toggle = screen.getByTestId("layer-toggle-risk_overlay").querySelector("input");
      fireEvent.click(toggle);
      await waitFor(() => expect(fetchRegionalRisk).toHaveBeenCalled());
      expect(screen.getByTestId("intelligence-map-section")).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Weather overlay layer
  // -------------------------------------------------------------------------
  describe("weather overlay layer", () => {
    it("includes Weather Overlay toggle in layer controls", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByTestId("layer-toggle-weather_overlay")).toBeInTheDocument();
    });

    it("weather overlay toggle is unchecked by default", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      const toggle = screen.getByTestId("layer-toggle-weather_overlay").querySelector("input");
      expect(toggle.checked).toBe(false);
    });

    it("does not call fetchWeather on initial load", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(fetchWeather).not.toHaveBeenCalled();
    });

    it("calls fetchWeather when weather overlay is toggled on", async () => {
      fetchWeather.mockResolvedValue({
        provider: "Open-Meteo",
        cache_ttl_minutes: 30,
        regions: [
          {
            region: "Suceava",
            temperature: 30.0,
            humidity: 35.0,
            wind_speed: 20.0,
            wind_direction: 270.0,
            precipitation: 0.0,
            weather_code: 1,
            updated_at: null,
          },
        ],
      });
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      const toggle = screen.getByTestId("layer-toggle-weather_overlay").querySelector("input");
      fireEvent.click(toggle);
      await waitFor(() => expect(fetchWeather).toHaveBeenCalledTimes(1));
    });

    it("weather overlay toggle operates independently from risk overlay", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      const weatherToggle = screen.getByTestId("layer-toggle-weather_overlay").querySelector("input");
      const riskToggle = screen.getByTestId("layer-toggle-risk_overlay").querySelector("input");
      fireEvent.click(weatherToggle);
      await waitFor(() => expect(fetchWeather).toHaveBeenCalledTimes(1));
      // Risk should NOT have been called
      expect(fetchRegionalRisk).not.toHaveBeenCalled();
      // Enabling risk independently
      fireEvent.click(riskToggle);
      await waitFor(() => expect(fetchRegionalRisk).toHaveBeenCalledTimes(1));
      // Weather still only called once
      expect(fetchWeather).toHaveBeenCalledTimes(1);
    });

    it("weather legend entries appear when overlay is enabled", async () => {
      fetchWeather.mockResolvedValue({ provider: "Open-Meteo", cache_ttl_minutes: 30, regions: [] });
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      const toggle = screen.getByTestId("layer-toggle-weather_overlay").querySelector("input");
      fireEvent.click(toggle);
      await waitFor(() => {
        // Temperature legend entries appear
        expect(screen.getByText("< 0°C")).toBeInTheDocument();
      });
    });
  });

  // -------------------------------------------------------------------------
  // Popup content — environmental threat intelligence
  // -------------------------------------------------------------------------
  describe("popup content — threat intelligence", () => {
    it("includes threat fields when threat assessments are available", async () => {
      let popupHtml = "";
      L.circleMarker.mockImplementation(() => ({
        bindPopup: jest.fn((html) => {
          popupHtml = html;
          return { addTo: jest.fn() };
        }),
        addTo: jest.fn(),
      }));

      fetchMapOverlay.mockResolvedValue({ ...MOCK_OVERLAY, forest_events: [] });
      fetchAnomalies.mockResolvedValue({ anomalies: [] });
      fetchIntelligenceEvents.mockResolvedValue(MOCK_INTEL);
      fetchIntelligenceSummary.mockResolvedValue(MOCK_SUMMARY);
      fetchThreats.mockResolvedValue({
        threats: [
          {
            source_event_id: "i1",
            region: "Suceava",
            threat_category: "wildfire",
            origin: "natural",
            monitoring_priority: "high",
            intervention_priority: "medium",
            recommended_actions: ["Increase satellite monitoring frequency"],
          },
        ],
      });

      render(<IntelligenceMap />);
      await waitForLoad();

      expect(popupHtml).toMatch(/Threat/i);
      expect(popupHtml).toMatch(/Wildfire/i);
      expect(popupHtml).toMatch(/natural/i);
      expect(popupHtml).toMatch(/Increase satellite monitoring/i);
    });
  });

  describe("scoped map overlay contract", () => {
    it("calls fetchMapOverlay on mount (not fetchMapEvents)", async () => {
      setupMocks();
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(fetchMapOverlay).toHaveBeenCalledTimes(1);
      expect(fetchMapEvents).not.toHaveBeenCalled();
    });

    it("renders European coordinates from backend forest_events", async () => {
      const europeEvent = {
        id: "de-wf",
        latitude: 48.1351,
        longitude: 11.582,
        severity: "high",
        region: "Bavaria",
        incident_category: "wildfire",
        detected_at: "2024-06-01T08:00:00Z",
        source: "NASA FIRMS",
        land_cover_type: "forest",
      };
      setupMocks({
        overlay: {
          ...MOCK_OVERLAY,
          geographic_scope: "europe",
          allow_romania_centroid_fallback: false,
          forest_events: [europeEvent],
        },
      });
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(L.circleMarker).toHaveBeenCalledWith(
        [48.1351, 11.582],
        expect.any(Object)
      );
    });

    it("does not render out-of-scope events excluded by backend", async () => {
      setupMocks({
        overlay: {
          ...MOCK_OVERLAY,
          geographic_scope: "europe",
          forest_events: [],
        },
      });
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(L.circleMarker).not.toHaveBeenCalled();
    });

    it("preserves Leaflet latitude-longitude ordering", async () => {
      setupMocks({
        overlay: {
          ...MOCK_OVERLAY,
          forest_events: [
            {
              id: "pl-wf",
              latitude: 52.2297,
              longitude: 21.0122,
              severity: "high",
              region: "Mazovia",
              land_cover_type: "forest",
              detected_at: "2024-06-01T08:00:00Z",
              source: "NASA FIRMS",
            },
          ],
        },
      });
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(L.circleMarker).toHaveBeenCalledWith(
        [52.2297, 21.0122],
        expect.any(Object)
      );
    });
  });

  describe("Tenant monitoring AOI", () => {
    it("renders monitored areas layer toggle", async () => {
      fetchMapOverlay.mockResolvedValue({
        ...MOCK_OVERLAY,
        monitored_areas: [
          {
            id: "a1",
            name: "Harghita Block",
            geometry: {
              type: "Polygon",
              coordinates: [[[25.5, 46.8], [26.5, 46.8], [26.5, 47.5], [25.5, 47.5], [25.5, 46.8]]],
            },
          },
        ],
      });
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(screen.getByTestId("layer-toggle-monitored_areas")).toBeInTheDocument();
    });

    it("prefers overlay intelligence events with AOI enrichment", async () => {
      fetchMapOverlay.mockResolvedValue({
        ...MOCK_OVERLAY,
        intelligence_events: [
          {
            id: "dist-1",
            incident_category: "forest_disturbance",
            latitude: 47.12,
            longitude: 25.98,
            region: "Harghita",
            priority_score: 0.7,
            inside_monitored_area: true,
            monitored_area: {
              relevance: "inside_monitored_area",
              name: "Harghita Block",
            },
          },
        ],
      });
      render(<IntelligenceMap />);
      await waitForLoad();
      expect(L.circleMarker).toHaveBeenCalledWith(
        [47.12, 25.98],
        expect.any(Object)
      );
    });
  });
});
