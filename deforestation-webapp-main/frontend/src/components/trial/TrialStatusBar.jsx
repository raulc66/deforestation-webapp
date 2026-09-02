import { Link } from "react-router-dom";
import { useTrial } from "@/context/TrialContext";

export default function TrialStatusBar() {
  const { status, isTrial, isExpired } = useTrial();
  if (!status || (!isTrial && !isExpired)) return null;

  const usage = status.usage ?? {};
  const areas = `${usage.monitored_areas ?? 0} / ${usage.monitored_area_limit ?? 0} monitored forests`;
  const remaining = status.days_remaining;
  const label = isExpired
    ? "Trial ended"
    : remaining === 0
      ? "Trial ends today"
      : `Trial · ${remaining} day${remaining === 1 ? "" : "s"} remaining`;

  return (
    <div
      className="mx-3 mt-3 px-3 py-2 rounded-md border border-[var(--surface-inset)] bg-[var(--surface-subtle)]"
      data-testid="trial-status-bar"
    >
      <div className="flex items-baseline justify-between gap-2">
        <div className="fw-kicker" data-testid="trial-status-label">
          {label}
        </div>
        {isExpired && (
          <Link
            to="/billing"
            className="text-[11px] font-semibold text-[var(--accent)] hover:underline"
            data-testid="trial-continue-cta"
          >
            Continue monitoring
          </Link>
        )}
      </div>
      <p className="text-[11px] text-[var(--text-muted)] mt-1 tabular-nums" data-testid="trial-usage-summary">
        {areas}
      </p>
    </div>
  );
}
