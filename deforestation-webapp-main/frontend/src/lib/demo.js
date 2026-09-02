/** Helpers for the interactive demonstration — product language only. */

export function isDemoUser(user) {
  return Boolean(user && typeof user === "object" && user.provider === "demo");
}

export function isDemoOrganization(org) {
  if (!org) return false;
  return org.slug === "forestwatch-demo" || org.kind === "demo";
}

export function remainingLabel(status, meter = "investigation") {
  const remaining = status?.budget?.remaining?.[meter];
  const limit = status?.budget?.limits?.[meter];
  if (remaining == null || limit == null) return null;
  return { remaining, limit };
}

export function isBudgetExhausted(status) {
  return Boolean(status?.budget?.exhausted);
}

export function isMeterExhausted(status, meter) {
  const remaining = status?.budget?.remaining?.[meter];
  return remaining != null && remaining <= 0;
}

export function budgetErrorMessage(err) {
  const code = err?.response?.data?.code;
  const detail = err?.response?.data?.detail;
  if (code === "demo_budget_exhausted") {
    return typeof detail === "string"
      ? detail
      : "You've explored the ForestWatch intelligence engine. Create an organization to continue monitoring your own forests.";
  }
  if (typeof detail === "string") return detail;
  return err?.message || "Something went wrong. Please try again.";
}
