import { api } from "@/lib/api";

/** @typedef {import('axios').AxiosResponse} AxiosResponse */

/**
 * @returns {Promise<{
 *   total_events: number;
 *   total_area_affected: number;
 *   open_events: number;
 *   resolved_events: number;
 *   investigating_events: number;
 *   average_confidence: number;
 * }>}
 */
export async function fetchOverview() {
  const { data } = await api.get("/analytics/overview");
  return data;
}

/**
 * @returns {Promise<Array<{ country: string; event_count: number; affected_area_ha: number }>>}
 */
export async function fetchCountries() {
  const { data } = await api.get("/analytics/countries");
  return data;
}

/**
 * @returns {Promise<Array<{ event_type: string; event_count: number; affected_area_ha: number }>>}
 */
export async function fetchEventTypes() {
  const { data } = await api.get("/analytics/event-types");
  return data;
}

/**
 * @returns {Promise<Record<string, { count: number; area_ha: number }>>}
 */
export async function fetchSeverity() {
  const { data } = await api.get("/analytics/severity");
  return data;
}

/**
 * @param {{ interval?: string; start_date?: string; end_date?: string }} [params]
 * @returns {Promise<{
 *   interval: string;
 *   start_date: string;
 *   end_date: string;
 *   series: Array<{ bucket: string; event_count: number; affected_area_ha: number }>;
 * }>}
 */
export async function fetchTrends(params = { interval: "day" }) {
  const { data } = await api.get("/analytics/trends", { params });
  return data;
}

/**
 * Load all dashboard analytics in parallel.
 * @returns {Promise<{
 *   overview: Awaited<ReturnType<typeof fetchOverview>>;
 *   countries: Awaited<ReturnType<typeof fetchCountries>>;
 *   eventTypes: Awaited<ReturnType<typeof fetchEventTypes>>;
 *   severity: Awaited<ReturnType<typeof fetchSeverity>>;
 *   trends: Awaited<ReturnType<typeof fetchTrends>>;
 * }>}
 */
export async function fetchDashboardAnalytics() {
  const [overview, countries, eventTypes, severity, trends] = await Promise.all([
    fetchOverview(),
    fetchCountries(),
    fetchEventTypes(),
    fetchSeverity(),
    fetchTrends({ interval: "day" }),
  ]);
  return { overview, countries, eventTypes, severity, trends };
}

/**
 * @returns {Promise<{
 *   active: Array<{
 *     id: string;
 *     region: string;
 *     severity: string;
 *     escalation_level: string;
 *     trend: string;
 *     priority_score: number;
 *     detection_count: number;
 *     current_score: number;
 *     previous_score: number | null;
 *     last_detected_at: string;
 *     first_detected_at: string;
 *     status: string;
 *     metadata: Record<string, unknown>;
 *   }>;
 *   resolved: Array<unknown>;
 * }>}
 */
export async function fetchIntelligenceEvents() {
  const { data } = await api.get("/analytics/intelligence/events");
  return data;
}

/**
 * @returns {Promise<{
 *   active: number;
 *   resolved: number;
 *   persistent: number;
 *   critical: number;
 *   worsening: number;
 *   stable: number;
 *   improving: number;
 *   highest_priority_score: number | null;
 *   highest_priority_region: string | null;
 * }>}
 */
export async function fetchIntelligenceSummary() {
  const { data } = await api.get("/analytics/intelligence/events/summary");
  return data;
}

/**
 * Generic unscoped forest-event map retrieval.
 * Intelligence dashboards must use fetchMapOverlay() for GEOGRAPHIC_SCOPE-aware markers.
 * @returns {Promise<{ events: Array<object> }>}
 */
export async function fetchMapEvents() {
  const { data } = await api.get("/events/map");
  return data;
}

/**
 * Scoped intelligence map overlay — authoritative contract for IntelligenceMap.
 * Applies backend GEOGRAPHIC_SCOPE, authoritative coordinates, and centroid policy.
 * @returns {Promise<{
 *   generated_at: string;
 *   geographic_scope: string;
 *   allow_romania_centroid_fallback: boolean;
 *   region_centroids: Record<string, { latitude: number; longitude: number }>;
 *   forest_events: Array<object>;
 *   anomalies: Array<object>;
 *   intelligence_events: Array<object>;
 * }>}
 */
export async function fetchMapOverlay() {
  const { data } = await api.get("/analytics/intelligence/map-overlay");
  return data;
}

/**
 * @returns {Promise<{
 *   anomalies: Array<{
 *     region: string;
 *     current_count: number;
 *     baseline_avg: number;
 *     deviation_percent: number;
 *     anomaly_score: number;
 *     severity: string;
 *     status: string;
 *   }>;
 *   evaluated_at: string;
 *   total_regions: number;
 *   anomaly_count: number;
 * }>}
 */
export async function fetchAnomalies() {
  const { data } = await api.get("/analytics/intelligence/anomalies");
  return data;
}

/**
 * @returns {Promise<{
 *   scheduler_enabled: boolean;
 *   poll_interval_minutes: number;
 *   latest_run: {
 *     id: string;
 *     started_at: string;
 *     completed_at: string;
 *     duration_seconds: number;
 *     source: string;
 *     status: "success" | "failed";
 *     events_fetched: number;
 *     events_inserted: number;
 *     duplicates_skipped: number;
 *     error: string | null;
 *   } | null;
 *   successful_runs: number;
 *   failed_runs: number;
 * }>}
 */
export async function fetchIngestionStatus() {
  const { data } = await api.get("/analytics/intelligence/ingestion-status");
  return data;
}

/**
 * @returns {Promise<{
 *   enabled: boolean;
 *   providers: string[];
 *   last_notification: {
 *     id: string;
 *     provider: string;
 *     event_type: string;
 *     region: string;
 *     sent_at: string;
 *     success: boolean;
 *     error: string | null;
 *   } | null;
 *   notifications_sent: number;
 *   notifications_failed: number;
 * }>}
 */
export async function fetchNotificationsStatus() {
  const { data } = await api.get("/analytics/intelligence/notifications");
  return data;
}

/**
 * @returns {Promise<{
 *   generated_at: string;
 *   distribution: Array<{ land_cover: string; events: number }>;
 * }>}
 */
export async function fetchLandCoverDistribution() {
  const { data } = await api.get("/analytics/intelligence/land-cover");
  return data;
}

/**
 * @param {number} [days=30]
 * @returns {Promise<{ generated_at: string; days: Array<{ date: string; events: number; anomalies: number }> }>}
 */
export async function fetchHistoricalDaily(days = 30) {
  const { data } = await api.get("/analytics/intelligence/history/daily", {
    params: { days },
  });
  return data;
}

/**
 * @returns {Promise<Array<{
 *   region: string;
 *   events_last_30d: number;
 *   events_previous_30d: number;
 *   change_percent: number;
 *   trend: "increasing" | "stable" | "decreasing";
 * }>>}
 */
export async function fetchHistoricalRegions() {
  const { data } = await api.get("/analytics/intelligence/history/regions");
  return data;
}

/**
 * @returns {Promise<Array<{
 *   region: string;
 *   detections: number;
 *   average_priority: number;
 *   highest_severity: string;
 * }>>}
 */
export async function fetchHistoricalHotspots() {
  const { data } = await api.get("/analytics/intelligence/history/hotspots");
  return data;
}

/**
 * @returns {Promise<{ months: Array<{
 *   month: string;
 *   events: number;
 *   anomalies: number;
 *   forest_events: number;
 *   urban_events: number;
 * }> }>}
 */
export async function fetchHistoricalMonthly() {
  const { data } = await api.get("/analytics/intelligence/history/monthly");
  return data;
}

/**
 * Fetch current regional fire risk scores.
 * @returns {{ generated_at: string, regions: Array<{
 *   region: string,
 *   risk_score: number,
 *   risk_level: "Low"|"Moderate"|"High"|"Extreme",
 *   change: "up"|"down"|"stable"|"new",
 *   breakdown: {
 *     current_activity: number,
 *     historical_activity: number,
 *     forest: number,
 *     priority: number,
 *     escalation: number
 *   }
 * }> }}
 */
export async function fetchRegionalRisk() {
  const { data } = await api.get("/analytics/intelligence/risk");
  return data;
}

/**
 * Fetch cached regional weather observations.
 * @returns {{
 *   generated_at: string,
 *   provider: string,
 *   cache_ttl_minutes: number,
 *   regions: Array<{
 *     region: string,
 *     temperature: number,
 *     humidity: number,
 *     wind_speed: number,
 *     wind_direction: number,
 *     precipitation: number,
 *     weather_code: number,
 *     source: string,
 *     confidence: number,
 *     updated_at: string
 *   }>
 * }}
 */
export async function fetchWeather() {
  const { data } = await api.get("/analytics/intelligence/weather");
  return data;
}

/**
 * Fetch environmental threat assessments for active intelligence events.
 * @returns {{ generated_at: string, threats: Array<object> }}
 */
export async function fetchThreats() {
  const { data } = await api.get("/analytics/intelligence/threats");
  return data;
}

/**
 * Fetch aggregated threat summary for Command Center / dashboards.
 */
export async function fetchThreatSummary() {
  const { data } = await api.get("/analytics/intelligence/threat-summary");
  return data;
}

/**
 * Fetch Command Center snapshot including bounded intelligence evidence.
 */
export async function fetchCommandCenter() {
  const { data } = await api.get("/analytics/intelligence/command-center");
  return data;
}

/**
 * Fetch bounded operational status for multi-region validation.
 */
export async function fetchOperationalStatus() {
  const { data } = await api.get("/analytics/intelligence/operational-status");
  return data;
}

export function formatEventType(type) {
  return String(type)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
