import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Layers } from "lucide-react";
import { formatEventType } from "@/api/analytics";

const CHART_COLOR = "#2d5a27";

function ChartTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="bg-white border border-[#eaece6] rounded-md px-3 py-2 text-xs shadow-sm">
      <div className="font-semibold text-[#1a1e1a]">{row.label}</div>
      <div className="text-[#4a524a] mt-1">{row.event_count} events</div>
      <div className="text-[#7b827b]">{row.affected_area_ha.toLocaleString()} ha</div>
    </div>
  );
}

export default function EventTypeChart({ eventTypes, loading }) {
  const data = (eventTypes ?? [])
    .filter((r) => r.event_count > 0)
    .map((r) => ({
      ...r,
      label: formatEventType(r.event_type),
      shortLabel:
        formatEventType(r.event_type).length > 12
          ? formatEventType(r.event_type).slice(0, 10) + "…"
          : formatEventType(r.event_type),
    }));

  return (
    <div className="card-flat h-full" data-testid="analytics-event-types">
      <div className="flex items-center gap-2 mb-4">
        <Layers className="w-4 h-4 text-[#7b827b]" strokeWidth={1.5} />
        <div>
          <div className="label-eyebrow">Taxonomy</div>
          <h3 className="text-lg font-semibold tracking-tight mt-0.5">Event type distribution</h3>
        </div>
      </div>

      {loading && <div className="h-64 animate-pulse bg-[#f4f5f2] rounded" />}

      {!loading && data.length === 0 && (
        <p className="text-sm text-[#7b827b] h-64 flex items-center justify-center">
          No events by type yet.
        </p>
      )}

      {!loading && data.length > 0 && (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 4, right: 8, left: -16, bottom: 48 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eaece6" vertical={false} />
              <XAxis
                dataKey="shortLabel"
                tick={{ fontSize: 10, fill: "#7b827b" }}
                angle={-35}
                textAnchor="end"
                interval={0}
                height={56}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fontSize: 11, fill: "#7b827b" }}
                width={32}
              />
              <Tooltip content={<ChartTooltip />} cursor={{ fill: "#f4f5f2" }} />
              <Bar dataKey="event_count" fill={CHART_COLOR} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
