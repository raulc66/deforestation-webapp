const FRAMES = [
  {
    id: "command-center",
    title: "Command Center",
    caption: "Organization-scoped intelligence queue and monitoring status.",
  },
  {
    id: "map",
    title: "Intelligence Map",
    caption: "Geospatial view of events relative to monitored areas.",
  },
  {
    id: "investigation",
    title: "Investigation",
    caption: "Observation, inference, and evidence kept distinct.",
  },
  {
    id: "alerts",
    title: "Alert management",
    caption: "Policies, channels, and delivery history.",
  },
  {
    id: "aois",
    title: "Monitored areas / AOIs",
    caption: "Organization-owned geographic watch extents.",
  },
];

export default function ProductShowcase() {
  return (
    <div>
      <div className="sales-frames">
        {FRAMES.map((frame) => (
          <figure key={frame.id} className="sales-frame" data-testid={`sales-showcase-${frame.id}`}>
            <figcaption>
              <div className="sales-frame-label">Screenshot placeholder</div>
              <div className="sales-frame-title">{frame.title}</div>
              <p className="sales-note" style={{ marginTop: "0.4rem" }}>
                {frame.caption}
              </p>
            </figcaption>
            <div className="sales-wire" aria-hidden="true">
              <div className="sales-wire-bar" style={{ width: "42%" }} />
              <div className="sales-wire-panel" />
              <div className="sales-wire-bar" style={{ width: "70%" }} />
              <div className="sales-wire-bar" style={{ width: "55%" }} />
            </div>
          </figure>
        ))}
      </div>
      <p className="sales-note">
        This repository does not currently vendor product screenshots. Replace these labeled
        frames with captures of the live Command Center, map, investigation, alerts, and AOI
        surfaces. Do not substitute invented UI.
      </p>
    </div>
  );
}
