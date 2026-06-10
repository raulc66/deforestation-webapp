import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Activity } from "lucide-react";

const SEVERITY_ORDER = ["low", "medium", "high", "critical"];

const severityColor = {
  low: "#e9c46a",
  medium: "#f4a261",
  high: "#e76f51",
  critical: "#9b2226",
};

function ChartTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="bg-white border border-[#eaece6] rounded-md px-3 py-2 text-xs shadow-sm">
      <div className="font-semibold capitalize text-[#1a1e1a]">{row.severity}</div>
      <div className="text-[#4a524a] mt-1">{row.count} events</div>
      <div className="text-[#7b827b]">{row.area_ha.toLocaleString()} ha</div>
    </div>
  );
}

export default function SeverityChart({ severity, loading }) {
  const data = SEVERITY_ORDER.map((key) => ({
    severity: key,
    count: severity?.[key]?.count ?? 0,
    area_ha: severity?.[key]?.area_ha ?? 0,
  }));

  const total = data.reduce((sum, d) => sum + d.count, 0);

  return (
    <div className="card-flat h-full" data-testid="severity-distribution">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-[#7b827b]" strokeWidth={1.5} />
          <div>
            <div className="label-eyebrow">Risk profile</div>
            <h3 className="text-lg font-semibold tracking-tight mt-0.5">
              Severity distribution
            </h3>
          </div>
        </div>
        {!loading && (
          <span className="text-sm text-[#7b827b] tabular-nums">{total} total</span>
        )}
      </div>

      {loading && <div className="h-64 animate-pulse bg-[#f4f5f2] rounded" />}

      {!loading && total === 0 && (
        <p className="text-sm text-[#7b827b] h-64 flex items-center justify-center">
          No severity data available.
        </p>
      )}

      {!loading && total > 0 && (
        <>
          <div className="flex h-2 rounded-full overflow-hidden bg-[#eaece6] mb-4">
            {data.map((d) => {
              const pct = total ? (d.count / total) * 100 : 0;
              return (
                <div
                  key={d.severity}
                  className="h-full"
                  style={{ width: `${pct}%`, background: severityColor[d.severity] }}
                  title={`${d.severity}: ${d.count}`}
                />
              );
            })}
          </div>
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eaece6" vertical={false} />
                <XAxis
                  dataKey="severity"
                  tick={{ fontSize: 11, fill: "#7b827b" }}
                  tickFormatter={(v) => v.charAt(0).toUpperCase() + v.slice(1)}
                />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#7b827b" }} width={32} />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: "#f4f5f2" }} />
                <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                  {data.map((entry) => (
                    <Cell key={entry.severity} fill={severityColor[entry.severity]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
}
