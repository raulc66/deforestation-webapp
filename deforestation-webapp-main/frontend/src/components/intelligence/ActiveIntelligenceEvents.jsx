/** Colour maps live here so badge helpers stay pure. */
const TREND_STYLES = {
  worsening: {
    bg: "bg-[#9b2226]/10",
    text: "text-[#9b2226]",
    label: "worsening",
  },
  improving: {
    bg: "bg-[#2d5a27]/10",
    text: "text-[#2d5a27]",
    label: "improving",
  },
  stable: {
    bg: "bg-[#7b827b]/10",
    text: "text-[#7b827b]",
    label: "stable",
  },
  new: {
    bg: "bg-[#e9c46a]/20",
    text: "text-[#7a5c00]",
    label: "new",
  },
};

const ESCALATION_STYLES = {
  critical: {
    bg: "bg-[#9b2226]/10",
    text: "text-[#9b2226]",
    label: "critical",
  },
  persistent: {
    bg: "bg-[#c84b31]/10",
    text: "text-[#c84b31]",
    label: "persistent",
  },
  normal: {
    bg: "bg-[#7b827b]/10",
    text: "text-[#7b827b]",
    label: "normal",
  },
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
    <span
      className={`inline-block text-[9px] tracking-[0.22em] uppercase font-bold px-2 py-1 rounded ${s.bg} ${s.text}`}
      data-testid={`trend-badge-${trend}`}
    >
      {s.label}
    </span>
  );
}

function EscalationBadge({ level }) {
  const s = ESCALATION_STYLES[level] ?? ESCALATION_STYLES.normal;
  return (
    <span
      className={`inline-block text-[9px] tracking-[0.22em] uppercase font-bold px-2 py-1 rounded ${s.bg} ${s.text}`}
      data-testid={`escalation-badge-${level}`}
    >
      {s.label}
    </span>
  );
}

/** Client-side sort: priority_score DESC → last_detected_at DESC. */
function sortEvents(events) {
  return [...events].sort((a, b) => {
    const pd = (b.priority_score ?? 0) - (a.priority_score ?? 0);
    if (pd !== 0) return pd;
    return new Date(b.last_detected_at) - new Date(a.last_detected_at);
  });
}

export default function ActiveIntelligenceEvents({ events, loading, onCreateInvestigation }) {
  const sorted = sortEvents(events ?? []);

  return (
    <div data-testid="active-intelligence-events">
      <div className="bg-white border border-[#eaece6] rounded-lg overflow-hidden">
        <table className="w-full text-sm" data-testid="intelligence-events-table">
          <thead className="bg-[#f4f5f2] text-[#7b827b]">
            <tr>
              <th className="text-left font-semibold px-5 py-3">Region</th>
              <th className="text-left font-semibold px-5 py-3 hidden sm:table-cell">
                Severity
              </th>
              <th className="text-left font-semibold px-5 py-3 hidden md:table-cell">
                Trend
              </th>
              <th className="text-left font-semibold px-5 py-3 hidden lg:table-cell">
                Escalation
              </th>
              <th className="text-right font-semibold px-5 py-3">Priority</th>
              <th className="text-right font-semibold px-5 py-3 hidden md:table-cell">
                Detections
              </th>
              <th className="text-right font-semibold px-5 py-3 hidden lg:table-cell">
                Last detected
              </th>
              {onCreateInvestigation && (
                <th className="text-right font-semibold px-5 py-3">Action</th>
              )}
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr data-testid="intelligence-events-loading">
                <td colSpan={onCreateInvestigation ? 8 : 7} className="px-5 py-6 text-center text-[#7b827b]">
                  Loading intelligence events…
                </td>
              </tr>
            )}

            {!loading && sorted.length === 0 && (
              <tr data-testid="intelligence-events-empty">
                <td colSpan={onCreateInvestigation ? 8 : 7} className="px-5 py-6 text-center text-[#7b827b]">
                  No active intelligence events detected.
                </td>
              </tr>
            )}

            {!loading &&
              sorted.map((evt, idx) => (
                <tr
                  key={evt.id ?? idx}
                  className="border-t border-[#eaece6] hover:bg-[#f4f5f2]/60"
                  data-testid={`intelligence-event-row-${evt.id ?? idx}`}
                >
                  <td className="px-5 py-3 font-medium text-[#1a1e1a]">
                    {evt.region}
                  </td>
                  <td className="px-5 py-3 hidden sm:table-cell">
                    <span className="inline-flex items-center gap-2 text-xs uppercase tracking-wider font-semibold">
                      <span
                        className="severity-dot"
                        style={{
                          background: SEVERITY_COLOR[evt.severity] ?? "#7b827b",
                        }}
                      />
                      {evt.severity}
                    </span>
                  </td>
                  <td className="px-5 py-3 hidden md:table-cell">
                    <TrendBadge trend={evt.trend} />
                  </td>
                  <td className="px-5 py-3 hidden lg:table-cell">
                    <EscalationBadge level={evt.escalation_level} />
                  </td>
                  <td className="px-5 py-3 text-right font-mono text-xs font-semibold text-[#9b2226] tabular-nums">
                    {(evt.priority_score ?? 0).toFixed(4)}
                  </td>
                  <td className="px-5 py-3 text-right hidden md:table-cell font-mono text-xs tabular-nums">
                    {evt.detection_count ?? 1}
                  </td>
                  <td className="px-5 py-3 text-right hidden lg:table-cell text-[#7b827b] font-mono text-xs tabular-nums">
                    {evt.last_detected_at
                      ? new Date(evt.last_detected_at).toLocaleDateString()
                      : "—"}
                  </td>
                  {onCreateInvestigation && (
                    <td className="px-5 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => onCreateInvestigation(evt)}
                        className="text-xs font-semibold text-[#2d5a27] hover:underline"
                        data-testid={`create-investigation-${evt.id ?? idx}`}
                      >
                        Investigate
                      </button>
                    </td>
                  )}
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
