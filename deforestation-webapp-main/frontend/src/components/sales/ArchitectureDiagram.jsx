const PIPE = [
  {
    title: "External sources / providers",
    detail: "FIRMS and other adapters. Live keys belong to the licensee; mock data is used when unkeyed.",
  },
  {
    title: "Ingestion",
    detail: "Provider registry normalizes inbound observations into the platform contract.",
  },
  {
    title: "Normalization + deduplication",
    detail: "Deterministic identity so the same observation is not treated as a new event.",
  },
  {
    title: "ForestEvent / geospatial storage",
    detail: "MongoDB documents with GeoJSON location and 2dsphere indexes for proximity and bounds.",
  },
  {
    title: "Analytics",
    detail: "Baselines, aggregations, and detector outputs over stored observations.",
  },
  {
    title: "Intelligence engine",
    detail: "Observations become tracked intelligence events rather than a raw feed.",
  },
  {
    title: "Reconciliation, escalation, trends",
    detail: "Lifecycle of an event: identity, severity, trend, and whether it still requires attention.",
  },
  {
    title: "Investigations, evidence, alerts",
    detail: "Human workflow plus policy-driven notification records.",
  },
  {
    title: "Command Center / map / organization product",
    detail: "Operator surfaces scoped to the selected organization.",
  },
];

export default function ArchitectureDiagram() {
  return (
    <div data-testid="sales-architecture-diagram" className="sales-split sales-split-wide">
      <div>
        <p className="sales-kicker">Vertical pipeline</p>
        <div className="sales-pipe" role="list">
          {PIPE.map((step, index) => (
            <div key={step.title} className="sales-pipe-step" role="listitem">
              <div className="sales-pipe-rail" aria-hidden="true">
                <span className="sales-pipe-dot" />
                {index < PIPE.length - 1 ? <span className="sales-pipe-line" /> : null}
              </div>
              <div className="sales-pipe-body">
                <strong>{step.title}</strong>
                <span>{step.detail}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
      <div>
        <p className="sales-kicker">Cross-cutting control plane</p>
        <div className="sales-crosscut">
          <div className="sales-crosscut-label">Applies across the pipeline</div>
          <div className="sales-crosscut-row">
            <span className="sales-chip">Organizations</span>
            <span className="sales-chip">Membership roles</span>
            <span className="sales-chip">AOIs / monitored areas</span>
            <span className="sales-chip">Entitlements</span>
          </div>
          <p className="sales-note" style={{ marginTop: "1rem" }}>
            Organization context (X-Organization-Id) scopes product reads and writes. Capacity
            is enforced by entitlements, not by a separate product stack.
          </p>
        </div>
      </div>
    </div>
  );
}
