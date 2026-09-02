/** Semantic state labels and presentation metadata for ForestWatch UI. */

export const EVIDENCE_LABELS = {
  single_source: "Single source",
  multi_source: "Multi-source",
  contextual_support: "Contextual support",
  degraded_source: "Degraded source",
  unavailable: "Unavailable",
};

export const PRIORITY_LABELS = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
};

export const SYSTEM_LABELS = {
  operational: "Operational",
  healthy: "Operational",
  degraded: "Degraded",
  failed: "Failed",
  unavailable: "Unavailable",
  disabled: "Disabled",
};

export const DELIVERY_STATE_LABELS = {
  pending: "Queued",
  sent: "Delivered",
  failed: "Delivery failed",
  suppressed: "Suppressed",
  acknowledged: "Acknowledged",
  resolved: "Resolved",
};

const DELIVERY_STATE_VARIANTS = {
  pending: "medium",
  sent: "operational",
  failed: "failed",
  suppressed: "disabled",
  acknowledged: "operational",
  resolved: "operational",
};

export const ALERT_STAGE_LABELS = {
  initial: "Initial alert",
  escalation: "Escalation",
  resolution: "Resolution",
};

export const CHANNEL_TYPE_LABELS = {
  email: "Email channel",
  webhook: "Webhook channel",
};

export function deliveryStateLabel(lifecycle) {
  return DELIVERY_STATE_LABELS[String(lifecycle || "")] ?? "Unknown";
}

export function deliveryStateVariant(lifecycle) {
  return DELIVERY_STATE_VARIANTS[String(lifecycle || "")] ?? "unknown";
}

export function alertStageLabel(stage) {
  return ALERT_STAGE_LABELS[String(stage || "")] ?? "Alert";
}

export function channelTypeLabel(channelType) {
  return CHANNEL_TYPE_LABELS[String(channelType || "")] ?? "Notification channel";
}

export function activationLabel(enabled) {
  return enabled ? "Active" : "Paused";
}

/** Cooldown is a customer-facing interval, never a raw minute count. */
export function formatCooldown(minutes) {
  const value = Number(minutes ?? 0);
  if (!Number.isFinite(value) || value <= 0) return "No cooldown";
  if (value < 60) return `${value} min`;
  const hours = value / 60;
  if (value % 60 === 0 && hours < 24) return `${hours} hr`;
  if (value % 1440 === 0) return `${value / 1440} day${value === 1440 ? "" : "s"}`;
  return `${Math.floor(hours)} hr ${value % 60} min`;
}

export function formatTimestamp(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDriverLabel(driver) {
  if (!driver) return "Unknown";
  return String(driver)
    .replace(/_candidate$/i, "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatAuthorizationLabel(status) {
  const s = String(status || "unknown").toLowerCase();
  if (s === "unknown") return "Unknown — requires verification";
  if (s === "verified") return "Verified";
  if (s.includes("verification")) return status;
  return String(status).replace(/_/g, " ");
}

export function entitlementAreaLabel(count, limit) {
  if (limit == null) return `${count ?? 0} monitored`;
  if (count >= limit) return "Limit reached";
  if (limit > 0 && count / limit >= 0.8) return "Approaching limit";
  return null;
}

export function featureAvailabilityLabel(enabled, { includedLabel = "Active", excludedLabel = "Not enabled" } = {}) {
  return enabled ? includedLabel : excludedLabel;
}

const SUBSCRIPTION_STATE_VARIANTS = {
  active: "operational",
  trialing: "operational",
  past_due: "degraded",
  incomplete: "degraded",
  unpaid: "failed",
  canceled: "not-enabled",
  incomplete_expired: "not-enabled",
};

/** Presentation for a subscription state; the label comes from the backend. */
export function subscriptionStateVariant(status) {
  return SUBSCRIPTION_STATE_VARIANTS[String(status || "")] ?? "unknown";
}

/** Monitoring capacity in product language rather than a bare ratio. */
export function monitoringCapacityLabel(count, limit) {
  const used = Number(count ?? 0);
  if (limit == null) return `${used} monitored forests`;
  const allowance = Number(limit);
  const noun = allowance === 1 ? "monitored forest" : "monitored forests";
  if (used > allowance) return `${used} of ${allowance} ${noun} — above plan capacity`;
  return `${used} of ${allowance} ${noun} in use`;
}

export function formatProviders(providers = []) {
  if (!providers.length) return "Unknown";
  return providers.join(" · ");
}

export function investigationPriorityRank(priority) {
  const order = { critical: 4, high: 3, medium: 2, low: 1 };
  return order[String(priority || "").toLowerCase()] ?? 0;
}

export function sortEvidenceByPriority(items = []) {
  return [...items].sort((a, b) => {
    const da = a.disturbance_assessment ?? {};
    const db = b.disturbance_assessment ?? {};
    const inside = Number(Boolean(b.monitored_area?.inside_monitored_area)) -
      Number(Boolean(a.monitored_area?.inside_monitored_area));
    if (inside !== 0) return inside;
    const pr =
      investigationPriorityRank(db.investigation_priority) -
      investigationPriorityRank(da.investigation_priority);
    if (pr !== 0) return pr;
    const str =
      (b.evidence_summary?.strongest_correlation_strength ?? 0) -
      (a.evidence_summary?.strongest_correlation_strength ?? 0);
    return str;
  });
}
