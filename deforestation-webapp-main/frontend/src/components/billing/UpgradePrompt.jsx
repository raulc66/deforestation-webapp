import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";

/**
 * Makes a plan limitation actionable wherever the customer meets it.
 *
 * Copy is always customer-facing: what is unavailable and what to do about it.
 * Entitlement identifiers and plan internals never reach this component.
 */
export default function UpgradePrompt({
  message,
  actionLabel = "View plans",
  to = "/billing",
  testId = "upgrade-prompt",
  compact = false,
}) {
  if (!message) return null;

  if (compact) {
    return (
      <div className="text-xs text-[var(--text-muted)] mt-2" data-testid={testId}>
        <span>{message} </span>
        <Link
          to={to}
          className="text-[var(--accent-strong)] font-semibold hover:underline"
          data-testid={`${testId}-link`}
        >
          {actionLabel}
        </Link>
      </div>
    );
  }

  return (
    <div
      className="mt-3 p-3 rounded-md border border-[var(--surface-inset)] bg-[var(--surface-subtle)]"
      data-testid={testId}
    >
      <p className="text-sm text-[var(--text-primary)]">{message}</p>
      <Link
        to={to}
        className="inline-flex items-center gap-1 mt-2 text-sm font-semibold text-[var(--accent-strong)] hover:underline"
        data-testid={`${testId}-link`}
      >
        {actionLabel}
        <ArrowUpRight className="w-3.5 h-3.5" strokeWidth={2} />
      </Link>
    </div>
  );
}
