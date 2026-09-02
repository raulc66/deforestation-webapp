const VARIANTS = {
  critical: "fw-badge fw-badge-critical",
  high: "fw-badge fw-badge-high",
  medium: "fw-badge fw-badge-medium",
  low: "fw-badge fw-badge-low",
  operational: "fw-badge fw-badge-operational",
  degraded: "fw-badge fw-badge-degraded",
  failed: "fw-badge fw-badge-failed",
  unavailable: "fw-badge fw-badge-unavailable",
  disabled: "fw-badge fw-badge-disabled",
  enabled: "fw-badge fw-badge-enabled",
  "not-enabled": "fw-badge fw-badge-not-enabled",
  unknown: "fw-badge fw-badge-unknown",
  verified: "fw-badge fw-badge-verified",
};

export default function StatusBadge({ variant = "medium", label, testId, title }) {
  const cls = VARIANTS[variant] ?? VARIANTS.medium;
  return (
    <span className={cls} data-testid={testId} title={title}>
      {label}
    </span>
  );
}
