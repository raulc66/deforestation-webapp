import { api } from "@/lib/api";

export async function fetchMonitoringAreas() {
  const { data } = await api.get("/monitoring-areas");
  return data;
}

export async function fetchMonitoringStatus() {
  const { data } = await api.get("/analytics/intelligence/monitoring-status");
  return data;
}

export async function createMonitoringArea(payload) {
  const { data } = await api.post("/monitoring-areas", payload);
  return data;
}
