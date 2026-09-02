import { api } from "@/lib/api";

/**
 * Customer alerting API client.
 *
 * Organization scope travels on the shared `X-Organization-Id` header managed by
 * OrganizationContext, so no call here takes an organization argument.
 */

export async function fetchAlertOptions() {
  const { data } = await api.get("/customer-alerts/options");
  return data;
}

export async function fetchAlertOverview() {
  const { data } = await api.get("/customer-alerts/overview");
  return data;
}

export async function fetchAlertPolicies() {
  const { data } = await api.get("/customer-alerts/policies");
  return data;
}

export async function createAlertPolicy(payload) {
  const { data } = await api.post("/customer-alerts/policies", payload);
  return data;
}

export async function updateAlertPolicy(policyId, payload) {
  const { data } = await api.put(`/customer-alerts/policies/${policyId}`, payload);
  return data;
}

export async function setAlertPolicyActive(policyId, enabled) {
  const { data } = await api.post(
    `/customer-alerts/policies/${policyId}/activation`,
    null,
    { params: { enabled } }
  );
  return data;
}

export async function deleteAlertPolicy(policyId) {
  await api.delete(`/customer-alerts/policies/${policyId}`);
}

export async function fetchNotificationChannels() {
  const { data } = await api.get("/customer-alerts/channels");
  return data;
}

export async function createNotificationChannel(payload) {
  const { data } = await api.post("/customer-alerts/channels", payload);
  return data;
}

export async function updateNotificationChannel(channelId, payload) {
  const { data } = await api.put(`/customer-alerts/channels/${channelId}`, payload);
  return data;
}

export async function setNotificationChannelActive(channelId, enabled) {
  const { data } = await api.post(
    `/customer-alerts/channels/${channelId}/activation`,
    null,
    { params: { enabled } }
  );
  return data;
}

export async function deleteNotificationChannel(channelId) {
  await api.delete(`/customer-alerts/channels/${channelId}`);
}

export async function fetchAlertDeliveries({ limit = 50, lifecycle } = {}) {
  const { data } = await api.get("/customer-alerts/deliveries", {
    params: lifecycle ? { limit, lifecycle } : { limit },
  });
  return data;
}
