import React, { useState, useEffect, useCallback, useMemo } from "react";
import { fetchRegionalRisk } from "@/api/analytics";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const LEVEL_CONFIG = {
  Extreme: {
    color: "#ef4444",
    bg: "bg-red-50",
    border: "border-red-200",
    badge: "bg-red-100 text-red-800",
    bar: "bg-red-500",
    glyph: "🔴",
  },
  High: {
    color: "#f97316",
    bg: "bg-orange-50",
    border: "border-orange-200",
    badge: "bg-orange-100 text-orange-800",
    bar: "bg-orange-500",
    glyph: "🟠",
  },
  Moderate: {
    color: "#eab308",
    bg: "bg-yellow-50",
    border: "border-yellow-200",
    badge: "bg-yellow-100 text-yellow-800",
    bar: "bg-yellow-400",
    glyph: "🟡",
  },
  Low: {
    color: "#22c55e",
    bg: "bg-green-50",
    border: "border-green-200",
    badge: "bg-green-100 text-green-800",
    bar: "bg-green-500",
    glyph: "🟢",
  },
};

const LEVELS_ORDER = ["Extreme", "High", "Moderate", "Low"];

const CHANGE_DISPLAY = {
  up: { icon: "↑", label: "up", cls: "text-red-500" },
  down: { icon: "↓", label: "down", cls: "text-green-500" },
  stable: { icon: "→", label: "stable", cls: "text-gray-400" },
  new: { icon: "★", label: "new", cls: "text-blue-400" },
};

const BREAKDOWN_LABELS = {
  current_activity: "Activity",
  historical_activity: "History",
  forest: "Forest",
  priority: "Priority",
  escalation: "Escalation",
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function RiskDistributionCards({ regions }) {
  const counts = useMemo(() => {
    const c = { Extreme: 0, High: 0, Moderate: 0, Low: 0 };
    (regions || []).forEach((r) => {
      if (c[r.risk_level] !== undefined) c[r.risk_level]++;
    });
    return c;
  }, [regions]);

  return (
    <div
      className="grid grid-cols-2 sm:grid-cols-4 gap-3"
      data-testid="risk-distribution-cards"
    >
      {LEVELS_ORDER.map((level) => {
        const cfg = LEVEL_CONFIG[level];
        return (
          <div
            key={level}
            className={`p-3 border rounded-xl text-center ${cfg.bg} ${cfg.border}`}
            data-testid={`risk-dist-${level.toLowerCase()}`}
          >
            <div className="text-2xl font-bold text-gray-900">
              {counts[level]}
            </div>
            <span
              className={`inline-block mt-1 text-xs font-semibold px-2 py-0.5 rounded-full ${cfg.badge}`}
            >
              {level}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function BreakdownBars({ breakdown }) {
  if (!breakdown) return null;
  return (
    <div className="space-y-0.5 mt-1" data-testid="breakdown-bars">
      {Object.entries(breakdown).map(([key, value]) => (
        <div key={key} className="flex items-center gap-1.5">
          <span className="w-14 text-right text-xs text-gray-400 flex-shrink-0">
            {BREAKDOWN_LABELS[key] || key}
          </span>
          <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-400 rounded-full"
              style={{ width: `${Math.min((value / 0.35) * 100, 100)}%` }}
              data-testid={`bar-${key}`}
            />
          </div>
          <span className="w-8 text-xs text-gray-500 tabular-nums">
            {((value || 0) * 100).toFixed(0)}%
          </span>
        </div>
      ))}
    </div>
  );
}

function Top5Cards({ regions }) {
  const top5 = useMemo(() => (regions || []).slice(0, 5), [regions]);

  if (top5.length === 0) {
    return (
      <p className="text-sm text-gray-400 py-4" data-testid="top5-empty">
        No risk data available.
      </p>
    );
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3" data-testid="top5-risk-cards">
      {top5.map((r, idx) => {
        const cfg = LEVEL_CONFIG[r.risk_level] || LEVEL_CONFIG.Low;
        const changeInfo = CHANGE_DISPLAY[r.change] || CHANGE_DISPLAY.stable;
        return (
          <div
            key={r.region}
            className={`p-3 border rounded-xl ${cfg.bg} ${cfg.border}`}
            data-testid={`top5-card-${idx}`}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-semibold text-gray-500">
                #{idx + 1}
              </span>
              <span
                className={`text-xs font-medium ${changeInfo.cls}`}
                data-testid={`change-${r.region}`}
              >
                {changeInfo.icon}
              </span>
            </div>
            <div className="font-bold text-sm text-gray-900 truncate mb-1">
              {r.region}
            </div>
            <div
              className="text-xl font-bold tabular-nums"
              style={{ color: cfg.color }}
            >
              {(r.risk_score * 100).toFixed(1)}
              <span className="text-xs font-normal ml-0.5 text-gray-500">%</span>
            </div>
            <span
              className={`inline-block text-xs font-semibold px-1.5 py-0.5 rounded-full mt-1 ${cfg.badge}`}
            >
              {r.risk_level}
            </span>
            <BreakdownBars breakdown={r.breakdown} />
          </div>
        );
      })}
    </div>
  );
}

function RiskTableRow({ region, rank }) {
  const cfg = LEVEL_CONFIG[region.risk_level] || LEVEL_CONFIG.Low;
  const changeInfo = CHANGE_DISPLAY[region.change] || CHANGE_DISPLAY.stable;
  const pct = ((region.risk_score || 0) * 100).toFixed(1);

  return (
    <tr className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
      <td className="py-2 px-3 text-xs text-gray-400 tabular-nums">{rank}</td>
      <td className="py-2 px-3 text-sm font-medium text-gray-800">
        {region.region}
      </td>
      <td className="py-2 px-3">
        <div className="flex items-center gap-2">
          <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden min-w-[60px]">
            <div
              className={`h-full rounded-full ${cfg.bar}`}
              style={{ width: `${pct}%` }}
            />
          </div>
          <span className="text-sm font-semibold tabular-nums text-gray-700 w-12 text-right">
            {pct}%
          </span>
        </div>
      </td>
      <td className="py-2 px-3">
        <span
          className={`inline-block text-xs font-semibold px-2 py-0.5 rounded-full ${cfg.badge}`}
        >
          {region.risk_level}
        </span>
      </td>
      <td
        className={`py-2 px-3 text-sm font-medium ${changeInfo.cls}`}
        title={changeInfo.label}
      >
        {changeInfo.icon}
      </td>
    </tr>
  );
}

function RiskTable({ regions }) {
  if (!regions || regions.length === 0) {
    return (
      <p
        className="text-sm text-gray-400 py-4 text-center"
        data-testid="risk-table-empty"
      >
        No risk data available.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto" data-testid="risk-table">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs font-semibold text-gray-500 uppercase tracking-wide border-b border-gray-200">
            <th className="py-2 px-3 text-left w-8">#</th>
            <th className="py-2 px-3 text-left">Region</th>
            <th className="py-2 px-3 text-left">Risk Score</th>
            <th className="py-2 px-3 text-left">Level</th>
            <th className="py-2 px-3 text-left">Δ</th>
          </tr>
        </thead>
        <tbody>
          {regions.map((r, idx) => (
            <RiskTableRow key={r.region} region={r} rank={idx + 1} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main section
// ---------------------------------------------------------------------------

export default function RegionalRiskSection() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchRegionalRisk();
      setData(result);
    } catch (err) {
      setError(err?.message || "Failed to load risk data.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const regions = data?.regions ?? [];

  return (
    <section
      className="mb-12"
      data-testid="regional-risk-section"
    >
      <div className="flex items-center justify-between mb-5">
        <div>
          <h2 className="text-xl font-bold text-gray-900">
            Fire Risk Assessment
          </h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Deterministic regional risk scores — updated each ingestion cycle
          </p>
        </div>
        {data?.generated_at && (
          <span className="text-xs text-gray-400">
            {new Date(data.generated_at).toLocaleString()}
          </span>
        )}
      </div>

      {error && (
        <div
          className="p-3 mb-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700 flex items-center justify-between"
          data-testid="risk-error"
        >
          <span>{error}</span>
          <button
            onClick={load}
            className="ml-3 text-xs font-medium text-red-600 underline hover:no-underline"
          >
            Retry
          </button>
        </div>
      )}

      {loading ? (
        <div data-testid="risk-loading">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-20 bg-gray-100 rounded-xl animate-pulse" />
            ))}
          </div>
          <div className="h-48 bg-gray-100 rounded-xl animate-pulse mb-5" />
          <div className="h-64 bg-gray-100 rounded-xl animate-pulse" />
        </div>
      ) : (
        <>
          <div className="mb-5">
            <h3 className="text-sm font-semibold text-gray-600 mb-3">
              Risk Distribution
            </h3>
            <RiskDistributionCards regions={regions} />
          </div>

          <div className="card-flat mb-5">
            <h3 className="text-sm font-semibold text-gray-600 mb-3">
              Top 5 Highest-Risk Regions
            </h3>
            <Top5Cards regions={regions} />
          </div>

          <div className="card-flat">
            <h3 className="text-sm font-semibold text-gray-600 mb-3">
              All Regions — Risk Table
            </h3>
            <RiskTable regions={regions} />
          </div>
        </>
      )}
    </section>
  );
}
