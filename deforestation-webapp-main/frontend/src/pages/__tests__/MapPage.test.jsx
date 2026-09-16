import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import MapPage from "../MapPage";

jest.mock("leaflet/dist/leaflet.css", () => ({}));

const mockAddLayer = jest.fn();
const mockRemoveLayer = jest.fn();
const mockMapRemove = jest.fn();
const mockInvalidateSize = jest.fn();
const mockTileAddTo = jest.fn();
const mockZoomAddTo = jest.fn();
const mockBindPopup = jest.fn().mockReturnThis();
const mockGroupAddLayer = jest.fn();
const mockGroupAddTo = jest.fn();

jest.mock("leaflet", () => {
  const api = {
    map: jest.fn(() => ({
      addLayer: mockAddLayer,
      removeLayer: mockRemoveLayer,
      remove: mockMapRemove,
      invalidateSize: mockInvalidateSize,
    })),
    tileLayer: jest.fn(() => ({ addTo: mockTileAddTo })),
    circleMarker: jest.fn(() => ({
      bindPopup: mockBindPopup,
    })),
    layerGroup: jest.fn(() => ({
      addLayer: mockGroupAddLayer,
      addTo: mockGroupAddTo,
    })),
    control: {
      zoom: jest.fn(() => ({ addTo: mockZoomAddTo })),
    },
  };
  api.default = api;
  return api;
});

jest.mock("@/components/layout/AppLayout", () => ({ children }) => (
  <div data-testid="app-layout">{children}</div>
));

const mockUseDemo = jest.fn(() => ({ isDemo: false }));
jest.mock("@/context/DemoContext", () => ({
  useDemo: () => mockUseDemo(),
}));

jest.mock("@/lib/api", () => ({
  api: { get: jest.fn() },
}));

import L from "leaflet";
import { api } from "@/lib/api";

const ALERTS = [
  {
    id: "a1",
    title: "Canopy loss",
    severity: "high",
    region: "Harghita",
    country: "Romania",
    area_ha: 12.5,
    confidence: 0.82,
    source: "NASA FIRMS",
    status: "open",
    location: { lat: 46.6, lng: 25.7 },
  },
  {
    id: "a2",
    title: "Fire hotspot",
    severity: "critical",
    region: "Suceava",
    country: "Romania",
    area_ha: 4,
    confidence: 0.91,
    source: "CSV",
    status: "new",
    location: { lat: 47.6, lng: 26.2 },
  },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <MapPage />
    </MemoryRouter>
  );
}

beforeEach(() => {
  mockUseDemo.mockReturnValue({ isDemo: false });
  api.get.mockReset();
  api.get.mockResolvedValue({ data: ALERTS });
  mockAddLayer.mockClear();
  mockRemoveLayer.mockClear();
  mockMapRemove.mockClear();
  mockInvalidateSize.mockClear();
  mockTileAddTo.mockClear();
  mockZoomAddTo.mockClear();
  mockBindPopup.mockClear();
  mockGroupAddLayer.mockClear();
  mockGroupAddTo.mockClear();
  L.map.mockImplementation(() => ({
    addLayer: mockAddLayer,
    removeLayer: mockRemoveLayer,
    remove: mockMapRemove,
    invalidateSize: mockInvalidateSize,
  }));
  L.tileLayer.mockImplementation(() => ({ addTo: mockTileAddTo }));
  L.circleMarker.mockImplementation(() => ({
    bindPopup: mockBindPopup,
  }));
  L.layerGroup.mockImplementation(() => ({
    addLayer: mockGroupAddLayer,
    addTo: mockGroupAddTo,
  }));
  L.control.zoom.mockImplementation(() => ({ addTo: mockZoomAddTo }));
});

describe("MapPage", () => {
  it("initializes a Leaflet map with OSM tiles and zoom control", async () => {
    renderPage();
    await waitFor(() => expect(L.map).toHaveBeenCalledTimes(1));
    expect(screen.getByTestId("leaflet-map")).toBeInTheDocument();
    expect(L.tileLayer).toHaveBeenCalledWith(
      "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      expect.objectContaining({
        attribution: expect.stringContaining("OpenStreetMap"),
      })
    );
    expect(mockTileAddTo).toHaveBeenCalled();
    expect(L.control.zoom).toHaveBeenCalledWith({ position: "bottomright" });
    expect(mockZoomAddTo).toHaveBeenCalled();
  });

  it("renders alert circle markers and binds popups", async () => {
    renderPage();
    await waitFor(() => expect(L.circleMarker).toHaveBeenCalledTimes(2));
    expect(L.circleMarker).toHaveBeenCalledWith(
      [46.6, 25.7],
      expect.objectContaining({
        radius: 10,
        fillOpacity: 0.55,
        weight: 2,
      })
    );
    expect(mockBindPopup).toHaveBeenCalledTimes(2);
    expect(mockBindPopup.mock.calls[0][0]).toBeInstanceOf(HTMLElement);
    expect(mockBindPopup.mock.calls[0][0].textContent).toContain("Canopy loss");
    expect(mockGroupAddTo).toHaveBeenCalled();
  });

  it("removes the map on unmount", async () => {
    const { unmount } = renderPage();
    await waitFor(() => expect(L.map).toHaveBeenCalled());
    unmount();
    expect(mockMapRemove).toHaveBeenCalled();
  });

  it("redirects demo sessions away from the map page", () => {
    mockUseDemo.mockReturnValue({ isDemo: true });
    renderPage();
    expect(screen.queryByTestId("map-page")).not.toBeInTheDocument();
  });
});
