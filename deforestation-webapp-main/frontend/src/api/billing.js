import { api } from "@/lib/api";

/**
 * Commercial plan and subscription API client.
 *
 * Organization scope travels on the shared `X-Organization-Id` header managed by
 * OrganizationContext. Checkout submits a plan key — never a price identifier.
 */

export async function fetchBillingStatus() {
  const { data } = await api.get("/billing/status");
  return data;
}

export async function fetchBillingPlans() {
  const { data } = await api.get("/billing/plans");
  return data;
}

export async function startCheckout(planKey) {
  const { data } = await api.post("/billing/checkout", { plan_key: planKey });
  return data;
}

export async function openBillingPortal() {
  const { data } = await api.post("/billing/portal");
  return data;
}
