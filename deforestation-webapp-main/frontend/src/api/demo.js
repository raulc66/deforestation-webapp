import { api } from "@/lib/api";

export async function startDemoSession() {
  const { data } = await api.post("/demo/start");
  return data;
}

export async function fetchDemoStatus() {
  const { data } = await api.get("/demo/status");
  return data;
}

export async function resetDemoSession() {
  const { data } = await api.post("/demo/reset");
  return data;
}

export async function setDemoGuideStep(stepId) {
  const { data } = await api.post(`/demo/guide/${encodeURIComponent(stepId)}`);
  return data;
}

export async function openDemoScenario(scenarioId) {
  const { data } = await api.post(`/demo/scenarios/${encodeURIComponent(scenarioId)}`);
  return data;
}

export async function consumeDemoInvestigation(eventId) {
  const { data } = await api.post("/demo/actions/investigate", {
    event_id: eventId ?? "",
  });
  return data;
}

export async function consumeDemoReport() {
  const { data } = await api.post("/demo/actions/report");
  return data;
}

export async function simulateDemoAlert(eventId) {
  const { data } = await api.post("/demo/alerts/simulate", {
    event_id: eventId ?? "",
  });
  return data;
}

export async function recordDemoEvent(eventName, detail = {}) {
  const { data } = await api.post(`/demo/events/${encodeURIComponent(eventName)}`, detail);
  return data;
}
