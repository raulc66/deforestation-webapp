import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { TrendingUp } from "lucide-react";

const LINE_COLOR = "#2d5a27";

function formatBucket(bucket) {
  if (!bucket) return "";
  const d = new Date(bucket);
  if (Number.isNaN(d.getTime())) return String(bucket);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-[#eaece6] rounded-md px-3 py-2 text-xs shadow-sm">
      <div className="font-semibold text-[#1a1e1a]">{formatBucket(label)}</div>
      <div className="text-[#4a524a] mt-1">{payload[0].value} events</div>
      {payload[1] && (
        <div className="text-[#7b827b]">{Number(payload[1].value).toLocaleString()} ha</div>
      )}
    </div>
  );
}

export default function TrendsChart({ trends, loading }) {
  const series = trends?.series ?? [];
  const chartData = series.map((point) => ({
    ...point,
    label: formatBucket(point.bucket),
  }));

  const rangeLabel =
    trends?.start_date && trends?.end_date
      ? `${formatBucket(trends.start_date)} – ${formatBucket(trends.end_date)}`
      : "Last 30 days";

  return (
    <div className="card-flat h-full" data-testid="analytics-trends">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-[#7b827b]" strokeWidth={1.5} />
          <div>
            <div className="label-eyebrow">Time series</div>
            <h3 className="text-lg font-semibold tracking-tight mt-0.5">30-day trends</h3>
          </div>
        </div>
        {!loading && (
          <span className="text-xs text-[#7b827b] hidden sm:inline">{rangeLabel}</span>
        )}
      </div>

      {loading && <div className="h-64 animate-pulse bg-[#f4f5f2] rounded" />}

      {!loading && chartData.length === 0 && (
        <p className="text-sm text-[#7b827b] h-64 flex items-center justify-center">
          No detections in this period.
        </p>
      )}

      {!loading && chartData.length > 0 && (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 8, right: 12, left: -12, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eaece6" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 10, fill: "#7b827b" }}
                interval="preserveStartEnd"
              />
              <YAxis
                yAxisId="events"
                allowDecimals={false}
                tick={{ fontSize: 11, fill: "#7b827b" }}
                width={32}
              />
              <YAxis
                yAxisId="area"
                orientation="right"
                tick={{ fontSize: 10, fill: "#c4c9c0" }}
                width={40}
                hide
              />
              <Tooltip content={<ChartTooltip />} />
              <Line
                yAxisId="events"
                type="monotone"
                dataKey="event_count"
                stroke={LINE_COLOR}
                strokeWidth={2}
                dot={{ r: 3, fill: LINE_COLOR }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
