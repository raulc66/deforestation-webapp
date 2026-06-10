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

export function formatEventType(type) {
  return String(type)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
