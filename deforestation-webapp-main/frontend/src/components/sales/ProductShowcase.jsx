const FRAMES = [
  {
    id: "command-center",
    title: "Command Center",
    caption: "Organization-scoped intelligence queue and monitoring status.",
    src: "/sales/forestwatch-command-center.png",
    alt: "ForestWatch Command Center showing active intelligence events and monitored regions",
    width: 1136,
    height: 947,
    eager: true,
  },
  {
    id: "map",
    title: "Intelligence Map",
    caption: "Geospatial view of events relative to monitored areas.",
    src: "/sales/forestwatch-intelligence-map.png",
    alt: "ForestWatch intelligence map showing monitored forest areas and geospatial overlays",
    width: 1006,
    height: 747,
  },
  {
    id: "investigation",
    title: "Investigation",
    caption: "Observation, inference, and evidence kept distinct.",
    src: "/sales/forestwatch-investigation.png",
    alt: "ForestWatch investigation view showing evidence and intelligence details",
    width: 1444,
    height: 901,
  },
  {
    id: "alerts",
    title: "Alert management",
    caption: "Policies, channels, and delivery history.",
    src: "/sales/forestwatch-alerts.png",
    alt: "ForestWatch alerts view showing demonstration policies and notification channels",
    width: 1381,
    height: 628,
  },
  {
    id: "sales-page",
    title: "Product landing",
    caption: "The public commercial page for the ForestWatch source-code product.",
    src: "/sales/forestwatch-sales-page.png",
    alt: "ForestWatch commercial product landing page",
    width: 1450,
    height: 774,
  },
];

export default function ProductShowcase() {
  return (
    <div>
      <div className="sales-frames">
        {FRAMES.map((frame) => (
          <figure key={frame.id} className="sales-frame" data-testid={`sales-showcase-${frame.id}`}>
            <figcaption>
              <div className="sales-frame-title">{frame.title}</div>
              <p className="sales-note" style={{ marginTop: "0.4rem" }}>
                {frame.caption}
              </p>
            </figcaption>
            <div className="sales-frame-media">
              <img
                src={frame.src}
                alt={frame.alt}
                width={frame.width}
                height={frame.height}
                loading={frame.eager ? "eager" : "lazy"}
                decoding="async"
              />
            </div>
          </figure>
        ))}
      </div>
      <p className="sales-note">
        Captures from the running ForestWatch application. Map tiles remain
        third-party (OpenStreetMap / Leaflet).
      </p>
    </div>
  );
}
