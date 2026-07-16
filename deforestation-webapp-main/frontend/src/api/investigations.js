/**
 * ForestWatch Investigations API client.
 */
import { api } from "@/lib/api";

export async function fetchInvestigations(params = {}) {
  const { data } = await api.get("/investigations", { params });
  return data;
}

export async function fetchInvestigation(id) {
  const { data } = await api.get(`/investigations/${id}`);
  return data;
}

export async function fetchInvestigationStatistics() {
  const { data } = await api.get("/investigations/statistics");
  return data;
}

export async function createInvestigation(body) {
  const { data } = await api.post("/investigations", body);
  return data;
}

export async function updateInvestigation(id, body) {
  const { data } = await api.patch(`/investigations/${id}`, body);
  return data;
}

export async function assignInvestigation(id, body) {
  const { data } = await api.patch(`/investigations/${id}/assign`, body);
  return data;
}

export async function closeInvestigation(id, body) {
  const { data } = await api.patch(`/investigations/${id}/close`, body);
  return data;
}

export async function archiveInvestigation(id) {
  await api.delete(`/investigations/${id}`);
}
