import StatusBadge from "./StatusBadge";
import { entitlementAreaLabel, featureAvailabilityLabel } from "@/design/semanticStates";

function EntitlementRow({ label, value, statusVariant, statusLabel, testId }) {
  return (
    <div className="flex items-start justify-between gap-3 py-2 border-b border-[var(--surface-inset)] last:border-0" data-testid={testId}>
      <div>
        <div className="text-sm font-medium text-[var(--text-primary)]">{label}</div>
        {value != null && (
          <div className="text-xs text-[var(--text-muted)] mt-0.5">{value}</div>
        )}
      </div>
      {statusLabel && (
        <StatusBadge variant={statusVariant} label={statusLabel} testId={`${testId}-status`} />
      )}
    </div>
  );
}

/**
 * Product-language entitlement summary — no billing, no internal flag names.
 */
export default function EntitlementList({ entitlements, compact = false }) {
  if (!entitlements) return null;

  const {
    monitored_area_limit: limit,
    monitored_area_count: count = 0,
    monitoring_enabled: monitoringEnabled = true,
    forest_disturbance_enabled: disturbanceEnabled = false,
    evidence_correlation_enabled: correlationEnabled = false,
    live_sources_enabled: liveEnabled = false,
    alert_delivery_enabled: alertsEnabled = false,
  } = entitlements;

  const limitHint = entitlementAreaLabel(count, limit);
  const areaVariant =
    limit != null && count >= limit
      ? "failed"
      : limitHint === "Approaching limit"
        ? "degraded"
        : "enabled";

  if (compact) {
    return (
      <div className="text-xs text-[var(--text-muted)] space-y-1" data-testid="entitlement-list-compact">
        {limit != null && (
          <div data-testid="entitlement-areas-compact">
            Monitored areas {count} / {limit}
            {limitHint ? ` · ${limitHint}` : ""}
          </div>
        )}
      </div>
    );
  }

  return (
    <div data-testid="entitlement-list">
      {limit != null && (
        <EntitlementRow
          label="Monitored areas"
          value={`${count} / ${limit} used${limitHint ? ` · ${limitHint}` : ""}`}
          statusVariant={areaVariant}
          statusLabel={limitHint ?? featureAvailabilityLabel(true, { includedLabel: "Available" })}
          testId="entitlement-monitored-areas"
        />
      )}
      <EntitlementRow
        label="Forest disturbance intelligence"
        statusVariant={disturbanceEnabled && monitoringEnabled ? "enabled" : "not-enabled"}
        statusLabel={featureAvailabilityLabel(disturbanceEnabled && monitoringEnabled, {
          includedLabel: "Active",
          excludedLabel: "Not enabled",
        })}
        testId="entitlement-disturbance"
      />
      <EntitlementRow
        label="Cross-source evidence"
        statusVariant={correlationEnabled ? "enabled" : "not-enabled"}
        statusLabel={featureAvailabilityLabel(correlationEnabled, {
          includedLabel: "Available",
          excludedLabel: "Not enabled",
        })}
        testId="entitlement-correlation"
      />
      <EntitlementRow
        label="Live environmental sources"
        statusVariant={liveEnabled ? "enabled" : "not-enabled"}
        statusLabel={featureAvailabilityLabel(liveEnabled, {
          includedLabel: "Enabled",
          excludedLabel: "Not enabled",
        })}
        testId="entitlement-live-sources"
      />
      <EntitlementRow
        label="Alert delivery"
        statusVariant={alertsEnabled ? "enabled" : "not-enabled"}
        statusLabel={featureAvailabilityLabel(alertsEnabled, {
          includedLabel: "Enabled",
          excludedLabel: "Not enabled",
        })}
        testId="entitlement-alerts"
      />
    </div>
  );
}
