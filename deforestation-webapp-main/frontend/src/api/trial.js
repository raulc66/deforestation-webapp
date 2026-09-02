import { api } from "@/lib/api";

export async function startTrial(payload = {}) {
  const { data } = await api.post("/trial/start", payload);
  return data;
}

export async function fetchTrialStatus() {
  const { data } = await api.get("/trial/status");
  return data;
}
