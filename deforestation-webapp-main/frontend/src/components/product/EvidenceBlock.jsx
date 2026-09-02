import StatusBadge from "./StatusBadge";
import {
  EVIDENCE_LABELS,
  featureAvailabilityLabel,
  formatAuthorizationLabel,
  formatDriverLabel,
  formatProviders,
} from "@/design/semanticStates";

/**
 * First-class evidence presentation — bounded read model only.
 */
export default function EvidenceBlock({ summary, disturbance, compact = false, testId = "evidence-block" }) {
  if (!summary && !disturbance) return null;

  const {
    providers = [],
    evidence_state: evidenceState = "single_source",
    strongest_correlation_strength: strength,
    source_availability: availability = {},
  } = summary ?? {};

  const degradedProviders = Object.entries(availability)
    .filter(([, status]) => status === "degraded" || status === "failed")
    .map(([providerId]) => providerId);

  const evidenceVariant =
    evidenceState === "degraded_source" || evidenceState === "unavailable"
      ? evidenceState === "unavailable"
        ? "unavailable"
        : "degraded"
      : evidenceState === "multi_source" || evidenceState === "contextual_support"
        ? "enabled"
        : "medium";

  if (compact) {
    return (
      <div className="text-xs text-[var(--text-muted)] space-y-1" data-testid={testId}>
        <div>
          <span className="fw-kicker">Evidence</span>{" "}
          {EVIDENCE_LABELS[evidenceState] ?? evidenceState}
          {typeof strength === "number" ? ` · ${strength.toFixed(2)}` : ""}
        </div>
        <div>{formatProviders(providers)}</div>
        {degradedProviders.length > 0 && (
          <div data-testid="evidence-degraded-sources">
            Source status: {degradedProviders.join(", ")} degraded
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid={testId}>
      <div>
        <div className="fw-kicker mb-1">Evidence</div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge
            variant={evidenceVariant}
            label={EVIDENCE_LABELS[evidenceState] ?? evidenceState}
            testId="evidence-state-badge"
          />
          {typeof strength === "number" && (
            <span className="text-sm font-mono tabular-nums text-[var(--text-primary)]">
              Strength {strength.toFixed(2)}
            </span>
          )}
        </div>
        <p className="text-sm text-[var(--text-secondary)] mt-1">
          {formatProviders(providers)}
        </p>
      </div>

      {disturbance?.probable_driver && (
        <div>
          <div className="fw-kicker mb-1">Probable driver</div>
          <p className="text-sm font-medium text-[var(--text-primary)]">
            {formatDriverLabel(disturbance.probable_driver)}
            {typeof disturbance.driver_confidence === "number" && (
              <span className="text-[var(--text-muted)] font-normal">
                {" "}
                · {Math.round(disturbance.driver_confidence * 100)}% confidence
              </span>
            )}
          </p>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">Inferred — not legal determination</p>
        </div>
      )}

      {disturbance?.authorization_status != null && (
        <div>
          <div className="fw-kicker mb-1">Authorization</div>
          <StatusBadge
            variant={
              String(disturbance.authorization_status).toLowerCase() === "verified"
                ? "verified"
                : "unknown"
            }
            label={formatAuthorizationLabel(disturbance.authorization_status)}
            testId="authorization-badge"
          />
        </div>
      )}

      {degradedProviders.length > 0 && (
        <p className="text-xs text-[var(--text-muted)]" data-testid="evidence-degraded-sources">
          Source availability: {degradedProviders.join(", ")} degraded
        </p>
      )}
    </div>
  );
}

export { EVIDENCE_LABELS, formatProviders };
