import { Thermometer, Wind, Droplets, Clock } from "lucide-react";

/** Format ISO datetime to a short locale string. */
function fmt(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "—";
  }
}

/** Convert wind direction degrees to a compass abbreviation. */
function windCompass(degrees) {
  const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  return dirs[Math.round(degrees / 45) % 8] ?? "—";
}

export default function WeatherSummaryCard({ data, loading }) {
  if (loading) {
    return (
      <div
        className="card-flat animate-pulse h-44 bg-[#f4f5f2]"
        data-testid="weather-summary-loading"
      />
    );
  }

  const regions = data?.regions ?? [];

  if (!data || regions.length === 0) {
    return (
      <div className="card-flat" data-testid="weather-summary-empty">
        <div className="label-eyebrow">Weather Summary</div>
        <p className="text-sm text-[#7b827b] mt-4">
          No weather data cached yet. Data updates every {data?.cache_ttl_minutes ?? 30} minutes.
        </p>
      </div>
    );
  }

  const hottest = regions.reduce(
    (max, r) => (r.temperature > (max?.temperature ?? -Infinity) ? r : max),
    null
  );
  const windiest = regions.reduce(
    (max, r) => (r.wind_speed > (max?.wind_speed ?? 0) ? r : max),
    null
  );
  const driest = regions.reduce(
    (min, r) => (r.humidity < (min?.humidity ?? Infinity) ? r : min),
    null
  );
  const mostRecent = regions.reduce(
    (max, r) =>
      new Date(r.updated_at ?? 0) > new Date(max?.updated_at ?? 0) ? r : max,
    null
  );

  const metrics = [
    {
      icon: <Thermometer className="w-4 h-4" strokeWidth={1.5} />,
      label: "Highest temperature",
      value: hottest ? `${hottest.temperature.toFixed(1)} °C` : "—",
      sub: hottest?.region ?? "",
      color: "#ef4444",
      testId: "weather-hottest",
    },
    {
      icon: <Wind className="w-4 h-4" strokeWidth={1.5} />,
      label: "Strongest wind",
      value: windiest
        ? `${windiest.wind_speed.toFixed(1)} km/h ${windCompass(windiest.wind_direction)}`
        : "—",
      sub: windiest?.region ?? "",
      color: "#3b82f6",
      testId: "weather-windiest",
    },
    {
      icon: <Droplets className="w-4 h-4" strokeWidth={1.5} />,
      label: "Lowest humidity",
      value: driest ? `${driest.humidity.toFixed(0)} %` : "—",
      sub: driest?.region ?? "",
      color: "#f97316",
      testId: "weather-driest",
    },
    {
      icon: <Clock className="w-4 h-4" strokeWidth={1.5} />,
      label: "Most recently updated",
      value: mostRecent ? fmt(mostRecent.updated_at) : "—",
      sub: mostRecent?.region ?? "",
      color: "#22c55e",
      testId: "weather-recent",
    },
  ];

  return (
    <div className="card-flat" data-testid="weather-summary-card">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <div className="label-eyebrow">Weather Summary</div>
          <div className="text-xs text-[#7b827b] mt-0.5">
            {regions.length} regions · refreshes every {data?.cache_ttl_minutes ?? 30} min
          </div>
        </div>
        <Thermometer className="w-4 h-4 text-[#7b827b] shrink-0" strokeWidth={1.5} />
      </div>

      <div className="grid grid-cols-2 gap-3">
        {metrics.map(({ icon, label, value, sub, color, testId }) => (
          <div
            key={testId}
            className="rounded-lg bg-[#f4f5f2] px-3 py-2.5"
            data-testid={testId}
          >
            <div
              className="flex items-center gap-1.5 mb-1"
              style={{ color }}
            >
              {icon}
              <span className="text-[10px] font-semibold uppercase tracking-wide">
                {label}
              </span>
            </div>
            <div className="text-sm font-semibold text-[#1a1e1a]" data-testid={`${testId}-value`}>
              {value}
            </div>
            {sub && (
              <div className="text-[11px] text-[#7b827b] mt-0.5 truncate">
                {sub}
              </div>
            )}
          </div>
        ))}
      </div>

      {data?.provider && (
        <div className="mt-3 text-[10px] text-[#9ca3af] text-right" data-testid="weather-provider">
          Provider: {data.provider}
        </div>
      )}
    </div>
  );
}
