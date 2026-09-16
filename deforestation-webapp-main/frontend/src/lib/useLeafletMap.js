import { useEffect, useRef, useState } from "react";
import * as LeafletNS from "leaflet";

const L = LeafletNS.default?.map ? LeafletNS.default : LeafletNS;

export const OSM_TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
export const OSM_ATTRIBUTION =
  '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

/**
 * Initialize a Leaflet map on a DOM node exactly once.
 *
 * Options are read on first mount only (center/zoom are fixed for ForestWatch
 * maps). Cleanup always calls map.remove() so React Strict Mode remounts do
 * not reuse a container that still has a Leaflet instance attached.
 */
export function useLeafletMap(containerRef, options = {}) {
  const optionsRef = useRef(options);
  optionsRef.current = options;
  const mapRef = useRef(null);
  const [map, setMap] = useState(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return undefined;

    if (el._leaflet_id) {
      el._leaflet_id = undefined;
    }

    const {
      center,
      zoom,
      scrollWheelZoom = true,
      zoomControl = true,
      zoomControlPosition = null,
    } = optionsRef.current;

    const instance = L.map(el, {
      center,
      zoom,
      scrollWheelZoom,
      zoomControl: zoomControl && !zoomControlPosition,
    });

    L.tileLayer(OSM_TILE_URL, { attribution: OSM_ATTRIBUTION }).addTo(instance);

    if (zoomControlPosition) {
      L.control.zoom({ position: zoomControlPosition }).addTo(instance);
    }

    mapRef.current = instance;
    setMap(instance);

    const raf = requestAnimationFrame(() => {
      instance.invalidateSize();
    });

    let resizeObserver = null;
    if (typeof ResizeObserver !== "undefined") {
      resizeObserver = new ResizeObserver(() => {
        instance.invalidateSize();
      });
      resizeObserver.observe(el);
    }

    return () => {
      cancelAnimationFrame(raf);
      if (resizeObserver) resizeObserver.disconnect();
      instance.remove();
      mapRef.current = null;
      setMap(null);
    };
  }, [containerRef]);

  return map;
}
