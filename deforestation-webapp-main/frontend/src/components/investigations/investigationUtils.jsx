/** Status badge styles for investigations. */
export const STATUS_STYLES = {
  open: { bg: "bg-blue-50", text: "text-blue-700", label: "Open" },
  in_progress: { bg: "bg-amber-50", text: "text-amber-700", label: "In Progress" },
  waiting: { bg: "bg-purple-50", text: "text-purple-700", label: "Waiting" },
  resolved: { bg: "bg-green-50", text: "text-green-700", label: "Resolved" },
  closed: { bg: "bg-[#7b827b]/10", text: "text-[#7b827b]", label: "Closed" },
};

export const PRIORITY_STYLES = {
  low: { bg: "bg-[#2d5a27]/10", text: "text-[#2d5a27]", dot: "#2d5a27" },
  medium: { bg: "bg-[#e9c46a]/20", text: "text-[#7a5c00]", dot: "#e9c46a" },
  high: { bg: "bg-[#e76f51]/10", text: "text-[#c84b31]", dot: "#e76f51" },
  critical: { bg: "bg-[#9b2226]/10", text: "text-[#9b2226]", dot: "#9b2226" },
};

export function StatusBadge({ status }) {
  const s = STATUS_STYLES[status] ?? STATUS_STYLES.open;
  return (
    <span
      className={`inline-block text-[9px] tracking-[0.22em] uppercase font-bold px-2 py-1 rounded ${s.bg} ${s.text}`}
      data-testid={`status-badge-${status}`}
    >
      {s.label}
    </span>
  );
}

export function PriorityBadge({ priority }) {
  const s = PRIORITY_STYLES[priority] ?? PRIORITY_STYLES.medium;
  return (
    <span
      className={`inline-flex items-center gap-1.5 text-[9px] tracking-[0.22em] uppercase font-bold px-2 py-1 rounded ${s.bg} ${s.text}`}
      data-testid={`priority-badge-${priority}`}
    >
      <span className="w-1.5 h-1.5 rounded-full" style={{ background: s.dot }} />
      {priority}
    </span>
  );
}

export function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
