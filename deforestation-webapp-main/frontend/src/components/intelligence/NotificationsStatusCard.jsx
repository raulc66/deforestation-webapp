import { Bell, BellOff, CheckCircle2, XCircle } from "lucide-react";

/**
 * Format a UTC datetime string as a relative label.
 */
function relativeTime(isoStr) {
  if (!isoStr) return "—";
  try {
    const diffMs = Date.now() - new Date(isoStr).getTime();
    const diffMin = Math.floor(diffMs / 60_000);
    if (diffMin < 1) return "just now";
    if (diffMin < 60) return `${diffMin} min ago`;
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24) return `${diffH} h ago`;
    return `${Math.floor(diffH / 24)} d ago`;
  } catch {
    return isoStr;
  }
}

function formatEventType(type) {
  return String(type)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function EnabledBadge({ enabled }) {
  if (enabled) {
    return (
      <span
        className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-[#e8f5e9] text-[#2d5a27]"
        data-testid="notifications-badge-enabled"
      >
        <CheckCircle2 className="w-3 h-3" strokeWidth={2} />
        Active
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full bg-[#f4f5f2] text-[#7b827b]"
      data-testid="notifications-badge-disabled"
    >
      <BellOff className="w-3 h-3" strokeWidth={2} />
      Disabled
    </span>
  );
}

export default function NotificationsStatusCard({ status, loading }) {
  if (loading) {
    return (
      <div
        className="card-flat animate-pulse h-48 bg-[#f4f5f2]"
        data-testid="notifications-status-loading"
      />
    );
  }

  if (!status) {
    return (
      <div className="card-flat" data-testid="notifications-status-empty">
        <div className="flex items-start justify-between">
          <div className="label-eyebrow">Notifications</div>
          <Bell className="w-4 h-4 text-[#7b827b]" strokeWidth={1.5} />
        </div>
        <p className="text-sm text-[#7b827b] mt-4">No status available.</p>
      </div>
    );
  }

  const {
    enabled,
    providers,
    last_notification,
    notifications_sent,
    notifications_failed,
  } = status;

  const lastEventType = last_notification
    ? formatEventType(last_notification.event_type)
    : null;

  const rows = [
    {
      label: "Providers",
      value:
        providers && providers.length > 0 ? providers.join(", ") : "None",
      testId: "notifications-providers",
    },
    {
      label: "Sent",
      value: notifications_sent,
      testId: "notifications-sent",
    },
    {
      label: "Failed",
      value: notifications_failed,
      testId: "notifications-failed",
    },
    {
      label: "Last sent",
      value: last_notification
        ? relativeTime(last_notification.sent_at)
        : "—",
      testId: "notifications-last-sent",
    },
    {
      label: "Last event",
      value: lastEventType ?? "—",
      testId: "notifications-last-event-type",
    },
  ];

  return (
    <div className="card-flat" data-testid="notifications-status-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="label-eyebrow">Notifications</div>
          <div className="text-xs text-[#7b827b] mt-0.5">
            Outbound intelligence alerts
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <Bell className="w-4 h-4 text-[#7b827b]" strokeWidth={1.5} />
          <EnabledBadge enabled={enabled} />
        </div>
      </div>

      <dl className="mt-4 space-y-2">
        {rows.map(({ label, value, testId }) => (
          <div key={label} className="flex justify-between items-baseline gap-2">
            <dt className="text-xs text-[#7b827b] shrink-0">{label}</dt>
            <dd
              className="text-sm font-medium text-[#1a1e1a] tabular-nums truncate text-right"
              data-testid={testId}
            >
              {value}
            </dd>
          </div>
        ))}
      </dl>

      {last_notification && !last_notification.success && (
        <div
          className="mt-3 px-3 py-2 rounded text-xs text-[#9b2226] bg-[#e76f51]/8 border border-[#e76f51]/20 truncate flex items-center gap-1.5"
          data-testid="notifications-last-error"
          title={last_notification.error}
        >
          <XCircle className="w-3 h-3 shrink-0" strokeWidth={2} />
          {last_notification.error || "Last notification failed"}
        </div>
      )}
    </div>
  );
}
