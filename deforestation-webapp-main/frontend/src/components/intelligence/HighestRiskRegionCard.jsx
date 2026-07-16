import React from "react";

const LEVEL_STYLES = {
  Extreme: {
    bg: "bg-red-50 border-red-200",
    badge: "bg-red-100 text-red-800",
    dot: "bg-red-500",
    score: "text-red-700",
  },
  High: {
    bg: "bg-orange-50 border-orange-200",
    badge: "bg-orange-100 text-orange-800",
    dot: "bg-orange-500",
    score: "text-orange-700",
  },
  Moderate: {
    bg: "bg-yellow-50 border-yellow-200",
    badge: "bg-yellow-100 text-yellow-800",
    dot: "bg-yellow-500",
    score: "text-yellow-700",
  },
  Low: {
    bg: "bg-green-50 border-green-200",
    badge: "bg-green-100 text-green-800",
    dot: "bg-green-500",
    score: "text-green-700",
  },
};

const CHANGE_ICONS = {
  up: { icon: "↑", label: "Increased", color: "text-red-600" },
  down: { icon: "↓", label: "Decreased", color: "text-green-600" },
  stable: { icon: "→", label: "Stable", color: "text-gray-500" },
  new: { icon: "★", label: "New region", color: "text-blue-500" },
};

/**
 * Card showing the single highest-risk Romanian region.
 *
 * Props:
 *   region — region entry from the /risk response ({ region, risk_score,
 *             risk_level, change, breakdown }) or null when data is unavailable.
 */
export default function HighestRiskRegionCard({ region }) {
  if (!region) {
    return (
      <div
        className="card-flat p-4 border rounded-xl"
        data-testid="highest-risk-region-card"
      >
        <p className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-2">
          Highest Risk Region
        </p>
        <p className="text-sm text-gray-400" data-testid="no-risk-data">
          No risk data available
        </p>
      </div>
    );
  }

  const styles = LEVEL_STYLES[region.risk_level] || LEVEL_STYLES.Low;
  const changeInfo = CHANGE_ICONS[region.change] || CHANGE_ICONS.stable;

  return (
    <div
      className={`p-4 border rounded-xl ${styles.bg}`}
      data-testid="highest-risk-region-card"
    >
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
        Highest Risk Region
      </p>

      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span
              className={`inline-block w-2.5 h-2.5 rounded-full flex-shrink-0 ${styles.dot}`}
              aria-hidden="true"
            />
            <span
              className="font-bold text-gray-900 text-base truncate"
              data-testid="risk-region-name"
            >
              {region.region}
            </span>
          </div>

          <span
            className={`inline-block text-xs font-semibold px-2 py-0.5 rounded-full ${styles.badge}`}
            data-testid="risk-level-badge"
          >
            {region.risk_level}
          </span>
        </div>

        <div className="text-right flex-shrink-0">
          <div
            className={`text-2xl font-bold tabular-nums ${styles.score}`}
            data-testid="risk-score-value"
          >
            {(region.risk_score * 100).toFixed(1)}
            <span className="text-sm font-normal ml-0.5">%</span>
          </div>

          <div
            className={`flex items-center justify-end gap-1 text-xs font-medium mt-0.5 ${changeInfo.color}`}
            data-testid="risk-change-indicator"
          >
            <span aria-hidden="true">{changeInfo.icon}</span>
            <span>{changeInfo.label}</span>
          </div>
        </div>
      </div>

      {region.breakdown && (
        <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-gray-600">
          {[
            ["Activity", region.breakdown.current_activity],
            ["History", region.breakdown.historical_activity],
            ["Forest", region.breakdown.forest],
            ["Priority", region.breakdown.priority],
            ["Escalation", region.breakdown.escalation],
          ].map(([label, value]) => (
            <div key={label} className="flex justify-between">
              <span className="text-gray-500">{label}</span>
              <span className="font-medium tabular-nums">
                {((value || 0) * 100).toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
