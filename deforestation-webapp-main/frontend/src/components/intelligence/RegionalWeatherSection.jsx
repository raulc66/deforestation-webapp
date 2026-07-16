import { useState, useEffect, useCallback } from "react";
import { Cloud, Wind, Droplets, Thermometer } from "lucide-react";
import { fetchWeather } from "@/api/analytics";
import { formatApiErrorDetail } from "@/lib/api";
import WeatherSummaryCard from "./WeatherSummaryCard";

// ---------------------------------------------------------------------------
// WMO weather code descriptions
// ---------------------------------------------------------------------------

const WEATHER_DESCRIPTIONS = {
  0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
  45: "Foggy", 48: "Fog",
  51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
  61: "Light rain", 63: "Rain", 65: "Heavy rain",
  71: "Light snow", 73: "Snow", 75: "Heavy snow",
  80: "Showers", 81: "Showers", 82: "Heavy showers",
  95: "Thunderstorm", 96: "Thunderstorm", 99: "Thunderstorm",
};

function weatherDesc(code) {
  if (code == null) return "—";
  return (
    WEATHER_DESCRIPTIONS[code] ??
    WEATHER_DESCRIPTIONS[Math.floor(code / 10) * 10] ??
    `Code ${code}`
  );
}

// ---------------------------------------------------------------------------
// Temperature color (cold → hot)
// ---------------------------------------------------------------------------

function tempColor(temp) {
  if (temp < 0)  return "#3b82f6";   // blue
  if (temp < 10) return "#60a5fa";   // light blue
  if (temp < 20) return "#a3e635";   // lime
  if (temp < 30) return "#fb923c";   // orange
  if (temp < 40) return "#ef4444";   // red
  return "#991b1b";                  // dark red
}

// ---------------------------------------------------------------------------
// Wind direction arrow (Unicode arrow rotated via CSS)
// ---------------------------------------------------------------------------

function WindArrow({ degrees, speed }) {
  if (!speed && speed !== 0) return <span className="text-[#9ca3af]">—</span>;
  const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
  const compass = dirs[Math.round((degrees ?? 0) / 45) % 8];
  return (
    <span
      className="inline-flex items-center gap-1 text-[#3b82f6] font-medium tabular-nums"
      title={`${speed?.toFixed(1)} km/h ${compass} (${degrees?.toFixed(0)}°)`}
      data-testid="wind-arrow"
    >
      <span
        style={{
          display: "inline-block",
          transform: `rotate(${degrees ?? 0}deg)`,
          fontSize: "14px",
          lineHeight: 1,
        }}
        aria-hidden="true"
      >
        ↑
      </span>
      {speed?.toFixed(1)}{" "}
      <span className="text-[10px] text-[#7b827b]">km/h {compass}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------
// Humidity bar
// ---------------------------------------------------------------------------

function HumidityBar({ value }) {
  const pct = Math.round(Math.min(Math.max(value ?? 0, 0), 100));
  const color =
    pct < 30 ? "#f97316" : pct < 60 ? "#eab308" : "#22c55e";
  return (
    <div className="flex items-center gap-2 mt-0.5">
      <div className="flex-1 h-1.5 rounded-full bg-[#eaece6] overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="text-xs tabular-nums text-[#1a1e1a] w-9 text-right">
        {pct}%
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Single region weather card
// ---------------------------------------------------------------------------

function WeatherCard({ region }) {
  const color = tempColor(region.temperature);
  return (
    <div
      className="card-flat"
      data-testid={`weather-card-${region.region.replace(/\s+/g, "-").toLowerCase()}`}
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <div>
          <div className="text-sm font-semibold text-[#1a1e1a]">{region.region}</div>
          <div className="text-[11px] text-[#7b827b] mt-0.5">
            {weatherDesc(region.weather_code)}
          </div>
        </div>
        <div
          className="text-lg font-bold tabular-nums shrink-0"
          style={{ color }}
          data-testid="temperature-display"
        >
          {region.temperature?.toFixed(1)}°C
        </div>
      </div>

      <div className="space-y-2 text-xs text-[#7b827b]">
        <div className="flex items-center justify-between">
          <span className="flex items-center gap-1">
            <Wind className="w-3 h-3" strokeWidth={1.5} /> Wind
          </span>
          <WindArrow degrees={region.wind_direction} speed={region.wind_speed} />
        </div>

        <div>
          <div className="flex items-center gap-1 mb-0.5">
            <Droplets className="w-3 h-3" strokeWidth={1.5} /> Humidity
          </div>
          <HumidityBar value={region.humidity} />
        </div>

        {region.precipitation > 0 && (
          <div className="flex items-center justify-between">
            <span>Precipitation</span>
            <span className="font-medium text-[#1a1e1a] tabular-nums">
              {region.precipitation?.toFixed(1)} mm
            </span>
          </div>
        )}
      </div>

      {region.updated_at && (
        <div className="text-[10px] text-[#9ca3af] mt-2 text-right">
          {new Date(region.updated_at).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// RegionalWeatherSection — main export
// ---------------------------------------------------------------------------

export default function RegionalWeatherSection() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    let alive = true;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchWeather();
      if (alive) setData(result);
    } catch (err) {
      if (alive) setError(formatApiErrorDetail(err, "Failed to load weather data."));
    } finally {
      if (alive) setLoading(false);
    }
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const regions = data?.regions ?? [];

  return (
    <section className="mb-12" data-testid="regional-weather-section">
      <div className="flex items-center gap-3 mb-6">
        <Cloud className="w-5 h-5 text-[#3b82f6]" strokeWidth={1.5} />
        <div>
          <h2 className="text-lg font-semibold text-[#1a1e1a]">
            Regional Weather
          </h2>
          <p className="text-sm text-[#7b827b]">
            Live environmental conditions by region — updated every{" "}
            {data?.cache_ttl_minutes ?? 30} minutes
          </p>
        </div>
      </div>

      {error && (
        <div
          className="rounded-lg bg-[#fef2f2] border border-[#fecaca] px-4 py-3 text-sm text-[#991b1b] mb-6"
          data-testid="weather-error"
        >
          {error}
        </div>
      )}

      {/* Summary card */}
      <div className="mb-6" data-testid="weather-summary-wrapper">
        <WeatherSummaryCard data={data} loading={loading} />
      </div>

      {/* Per-region cards */}
      {loading ? (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="card-flat animate-pulse h-36 bg-[#f4f5f2]"
              data-testid="weather-card-loading"
            />
          ))}
        </div>
      ) : regions.length === 0 ? (
        <div className="card-flat" data-testid="weather-empty">
          <div className="flex items-start gap-3">
            <Cloud className="w-5 h-5 text-[#9ca3af] shrink-0 mt-0.5" strokeWidth={1.5} />
            <div>
              <div className="text-sm font-medium text-[#1a1e1a]">
                No weather data cached
              </div>
              <div className="text-xs text-[#7b827b] mt-1">
                The scheduler refreshes weather data every{" "}
                {data?.cache_ttl_minutes ?? 30} minutes. Data will appear after
                the first ingestion cycle completes.
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div
          className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4"
          data-testid="weather-cards-grid"
        >
          {regions.map((r) => (
            <WeatherCard key={r.region} region={r} />
          ))}
        </div>
      )}
    </section>
  );
}
