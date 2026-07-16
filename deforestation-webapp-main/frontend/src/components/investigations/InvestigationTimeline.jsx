import { StatusBadge, PriorityBadge, fmtDate } from "./investigationUtils";

const EVENT_LABELS = {
  threat_detected: "Threat detected",
  investigation_created: "Investigation created",
  assigned: "Assigned",
  evidence_uploaded: "Evidence uploaded",
  comment_added: "Comment added",
  status_changed: "Status changed",
  priority_changed: "Priority changed",
  closed: "Closed",
};

export default function InvestigationTimeline({ timeline, loading }) {
  if (loading) {
    return (
      <div className="text-sm text-[#7b827b] py-4" data-testid="timeline-loading">
        Loading timeline…
      </div>
    );
  }

  if (!timeline?.length) {
    return (
      <div className="text-sm text-[#7b827b] py-4" data-testid="timeline-empty">
        No timeline events yet.
      </div>
    );
  }

  return (
    <ol className="relative border-l border-[#eaece6] ml-3 space-y-4" data-testid="investigation-timeline">
      {timeline.map((entry) => (
        <li key={entry.id} className="ml-4" data-testid={`timeline-entry-${entry.id}`}>
          <span className="absolute -left-1.5 mt-1.5 w-3 h-3 rounded-full bg-[#2d5a27] border-2 border-white" />
          <div className="text-[10px] tracking-[0.15em] uppercase text-[#7b827b] font-semibold">
            {EVENT_LABELS[entry.event_type] ?? entry.event_type}
          </div>
          <p className="text-sm text-[#1a1e1a] mt-0.5">{entry.message}</p>
          <div className="text-xs text-[#7b827b] mt-1">
            {fmtDate(entry.created_at)}
            {entry.actor && ` · ${entry.actor}`}
          </div>
        </li>
      ))}
    </ol>
  );
}

export { StatusBadge, PriorityBadge, fmtDate };
