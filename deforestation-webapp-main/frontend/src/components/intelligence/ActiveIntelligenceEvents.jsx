import EvidenceIndicator from "./EvidenceIndicator";
import PriorityBadge from "@/components/product/PriorityBadge";
import StatusBadge from "@/components/product/StatusBadge";

const TREND_STYLES = {
  worsening: { bg: "bg-[#9b2226]/10", text: "text-[#9b2226]", label: "worsening" },
  improving: { bg: "bg-[var(--accent-strong)]/10", text: "text-[var(--accent-strong)]", label: "improving" },
  stable: { bg: "bg-[var(--surface-inset)]", text: "text-[var(--text-muted)]", label: "stable" },
  new: { bg: "bg-[#e9c46a]/20", text: "text-[#7a5c00]", label: "new" },
};

const ESCALATION_STYLES = {
  critical: { bg: "bg-[#9b2226]/10", text: "text-[#9b2226]", label: "critical" },
  persistent: { bg: "bg-[var(--signal)]/10", text: "text-[var(--signal)]", label: "persistent" },
  normal: { bg: "bg-[var(--surface-inset)]", text: "text-[var(--text-muted)]", label: "normal" },
};

const SEVERITY_COLOR = {
  low: "#e9c46a",
  medium: "#f4a261",
  high: "#e76f51",
  critical: "#9b2226",
};

function TrendBadge({ trend }) {
  const s = TREND_STYLES[trend] ?? TREND_STYLES.stable;
  return (
    <span className={`inline-block text-[9px] tracking-[0.22em] uppercase font-bold px-2 py-1 rounded ${s.bg} ${s.text}`} data-testid={`trend-badge-${trend}`}>
      {s.label}
    </span>
  );
}

function EscalationBadge({ level }) {
  const s = ESCALATION_STYLES[level] ?? ESCALATION_STYLES.normal;
  return (
    <span className={`inline-block text-[9px] tracking-[0.22em] uppercase font-bold px-2 py-1 rounded ${s.bg} ${s.text}`} data-testid={`escalation-badge-${level}`}>
      {s.label}
    </span>
  );
}

function sortEvents(events) {
  return [...events].sort((a, b) => {
    const pd = (b.priority_score ?? 0) - (a.priority_score ?? 0);
    if (pd !== 0) return pd;
    return new Date(b.last_detected_at) - new Date(a.last_detected_at);
  });
}

function categoryLabel(evt, evidence) {
  if (evt.incident_category === "forest_disturbance") return "Disturbance";
  return evt.incident_category ?? evt.event_type ?? "Intelligence";
}

export default function ActiveIntelligenceEvents({
  events,
  loading,
  onCreateInvestigation,
  evidenceByEventId = {},
}) {
  const sorted = sortEvents(events ?? []);

  return (
    <div data-testid="active-intelligence-events">
      <div className="fw-surface overflow-hidden">
        <div className="px-5 py-3 border-b border-[var(--surface-inset)] bg-[var(--surface-subtle)]">
          <div className="fw-kicker">Active intelligence</div>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">
            Ranked by priority · organization-relevant signals highlighted
          </p>
        </div>
        <table className="w-full text-sm" data-testid="intelligence-events-table">
          <thead className="bg-[var(--surface-subtle)] text-[var(--text-muted)]">
            <tr>
              <th className="text-left font-semibold px-5 py-3">Region</th>
              <th className="text-left font-semibold px-5 py-3 hidden md:table-cell">Type</th>
              <th className="text-left font-semibold px-5 py-3 hidden lg:table-cell">AOI</th>
              <th className="text-left font-semibold px-5 py-3 hidden sm:table-cell">Severity</th>
              <th className="text-left font-semibold px-5 py-3 hidden md:table-cell">Trend</th>
              <th className="text-left font-semibold px-5 py-3 hidden lg:table-cell">Escalation</th>
              <th className="text-left font-semibold px-5 py-3 hidden xl:table-cell">Evidence</th>
              <th className="text-right font-semibold px-5 py-3">Priority</th>
              <th className="text-right font-semibold px-5 py-3 hidden md:table-cell">Detections</th>
              <th className="text-right font-semibold px-5 py-3 hidden lg:table-cell">Last detected</th>
              {onCreateInvestigation && (
                <th className="text-right font-semibold px-5 py-3">Action</th>
              )}
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr data-testid="intelligence-events-loading">
                <td colSpan={onCreateInvestigation ? 11 : 10} className="px-5 py-6 text-center text-[var(--text-muted)]">
                  Loading intelligence events…
                </td>
              </tr>
            )}

            {!loading && sorted.length === 0 && (
              <tr data-testid="intelligence-events-empty">
                <td colSpan={onCreateInvestigation ? 11 : 10} className="px-5 py-6 text-center text-[var(--text-muted)]">
                  No active intelligence events detected.
                </td>
              </tr>
            )}

            {!loading &&
              sorted.map((evt, idx) => {
                const evidence = evidenceByEventId[evt.id];
                const disturbance = evidence?.disturbance_assessment ?? {};
                const monitored = evidence?.monitored_area;
                const insideAoi =
                  monitored?.inside_monitored_area ||
                  monitored?.relevance === "inside_monitored_area";

                return (
                  <tr
                    key={evt.id ?? idx}
                    className="border-t border-[var(--surface-inset)] hover:bg-[var(--surface-subtle)]/60"
                    data-testid={`intelligence-event-row-${evt.id ?? idx}`}
                  >
                    <td className="px-5 py-3 font-medium text-[var(--text-primary)]">
                      {evt.region}
                    </td>
                    <td className="px-5 py-3 hidden md:table-cell text-xs">
                      {categoryLabel(evt, evidence)}
                      {disturbance.investigation_priority && (
                        <div className="mt-1">
                          <PriorityBadge priority={disturbance.investigation_priority} />
                        </div>
                      )}
                    </td>
                    <td className="px-5 py-3 hidden lg:table-cell">
                      {insideAoi ? (
                        <StatusBadge variant="enabled" label={monitored?.name ?? "Inside AOI"} testId={`aoi-${evt.id}`} />
                      ) : (
                        <StatusBadge variant="unavailable" label="Regional" testId={`aoi-${evt.id}`} />
                      )}
                    </td>
                    <td className="px-5 py-3 hidden sm:table-cell">
                      <span className="inline-flex items-center gap-2 text-xs uppercase tracking-wider font-semibold">
                        <span className="severity-dot" style={{ background: SEVERITY_COLOR[evt.severity] ?? "#7b827b" }} />
                        {evt.severity}
                      </span>
                    </td>
                    <td className="px-5 py-3 hidden md:table-cell">
                      <TrendBadge trend={evt.trend} />
                    </td>
                    <td className="px-5 py-3 hidden lg:table-cell">
                      <EscalationBadge level={evt.escalation_level} />
                    </td>
                    <td className="px-5 py-3 hidden xl:table-cell">
                      <EvidenceIndicator summary={evidence?.evidence_summary} />
                    </td>
                    <td className="px-5 py-3 text-right font-mono text-xs font-semibold text-[var(--signal-strong)] tabular-nums">
                      {(evt.priority_score ?? 0).toFixed(4)}
                    </td>
                    <td className="px-5 py-3 text-right hidden md:table-cell font-mono text-xs tabular-nums">
                      {evt.detection_count ?? 1}
                    </td>
                    <td className="px-5 py-3 text-right hidden lg:table-cell text-[var(--text-muted)] font-mono text-xs tabular-nums">
                      {evt.last_detected_at
                        ? new Date(evt.last_detected_at).toLocaleDateString()
                        : "—"}
                    </td>
                    {onCreateInvestigation && (
                      <td className="px-5 py-3 text-right">
                        <button
                          type="button"
                          onClick={() => onCreateInvestigation(evt)}
                          className="text-xs font-semibold text-[var(--accent-strong)] hover:underline"
                          data-testid={`create-investigation-${evt.id ?? idx}`}
                        >
                          Investigate
                        </button>
                      </td>
                    )}
                  </tr>
                );
              })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export { TrendBadge, EscalationBadge, sortEvents };
