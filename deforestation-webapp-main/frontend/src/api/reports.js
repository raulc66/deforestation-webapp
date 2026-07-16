/**
 * ForestWatch Reports API client.
 *
 * All functions use the shared axios instance with cookie-based authentication.
 */
import { api, API } from "@/lib/api";

/** @typedef {"daily"|"weekly"|"monthly"|"on_demand"} ReportType */
/** @typedef {"pdf"|"csv"|"json"} ReportFormat */
/** @typedef {"pending"|"generating"|"complete"|"failed"} ReportStatus */

/**
 * @typedef {Object} ReportRecord
 * @property {string} id
 * @property {ReportType} type
 * @property {ReportFormat} format
 * @property {ReportStatus} status
 * @property {string} generated_at
 * @property {string} period_start
 * @property {string} period_end
 * @property {number|null} file_size
 * @property {number|null} generation_time_ms
 * @property {Object|null} summary
 * @property {string|null} error
 */

/**
 * Fetch all report metadata records, newest first.
 * @returns {Promise<{reports: ReportRecord[], total: number}>}
 */
export async function fetchReports() {
  const { data } = await api.get("/reports");
  return data;
}

/**
 * Fetch a single report by ID.
 * @param {string} id
 * @returns {Promise<ReportRecord>}
 */
export async function fetchReport(id) {
  const { data } = await api.get(`/reports/${id}`);
  return data;
}

/**
 * Request generation of a new report (returns 202 Accepted immediately).
 * @param {ReportType} type
 * @param {ReportFormat} format
 * @param {string|null} periodStart ISO datetime string or null
 * @param {string|null} periodEnd   ISO datetime string or null
 * @returns {Promise<ReportRecord>} The PENDING record
 */
export async function generateReport(type, format = "pdf", periodStart = null, periodEnd = null) {
  const body = { type, format };
  if (periodStart) body.period_start = periodStart;
  if (periodEnd)   body.period_end   = periodEnd;
  const { data } = await api.post("/reports/generate", body);
  return data;
}

/**
 * Delete a report by ID.
 * @param {string} id
 */
export async function deleteReport(id) {
  await api.delete(`/reports/${id}`);
}

/**
 * Return the direct download URL for a completed report.
 * The browser will include session cookies automatically.
 * @param {string} id
 * @returns {string}
 */
export function getDownloadUrl(id) {
  return `${API}/reports/${id}/download`;
}
