import { COMMERCIAL } from "@/config/commercial";
import ArchitectureDiagram from "@/components/sales/ArchitectureDiagram";
import ProductShowcase from "@/components/sales/ProductShowcase";
import "./sales.css";

const MANIFEST = [
  ["01", "Full-stack source", "FastAPI backend and React frontend, licensed as source."],
  ["02", "Organizations", "Multi-tenant organizations, memberships, and roles."],
  ["03", "AOIs", "Organization-owned monitored areas stored as geospatial extents."],
  ["04", "Geospatial store", "GeoJSON locations in MongoDB with 2dsphere indexes."],
  ["05", "Queries", "Proximity and bounding-box access over stored events."],
  ["06", "Ingestion", "Provider adapters with normalization and deterministic deduplication."],
  ["07", "Analytics", "Pipelines over observations, not a one-off notebook."],
  ["08", "Intelligence", "Event reconciliation, severity, trend, and escalation lifecycle."],
  ["09", "Evidence", "Investigation workflow that keeps observation and inference apart."],
  ["10", "Alerts", "Policies, channels, and delivery records; email and webhook architecture."],
  ["11", "Access", "Entitlements, authenticated trial, and a read-only interactive demo."],
  ["12", "Ship path", "Docker Compose local setup, architecture docs, and automated tests."],
];

const FOUNDATION_PROBLEMS = [
  "Authentication and session cookies",
  "Organizations and authorization",
  "Geospatial persistence",
  "Provider normalization",
  "Intelligence lifecycle",
  "Event reconciliation",
  "Anomaly and severity logic",
  "Investigation UX",
  "Evidence handling",
  "Alerting",
  "Entitlements",
  "Demo isolation",
  "Local deployment",
  "Regression testing",
];

const FAQ = [
  {
    q: "Is the full source code included?",
    a: "Yes. A license grant covers the ForestWatch application source in this package. Third-party libraries, fonts, datasets, and provider APIs remain under their own terms.",
  },
  {
    q: "Can I modify ForestWatch?",
    a: "Yes, within the license tier you purchase. Modification is expected. Redistribution and resale of the source package are governed by the license agreement, not by this page.",
  },
  {
    q: "Is ForestWatch limited to forestry?",
    a: "The included reference implementation is forest monitoring, with Romanian demo and seed data. The reusable architecture—organizations, AOIs, ingestion, intelligence, investigations, alerts—is built so other geospatial monitoring products can be adapted from it. Those other verticals are not shipping products in this package.",
  },
  {
    q: "Can I use it commercially?",
    a: "The Commercial and Agency tiers are intended for commercial use of the original ForestWatch code, subject to the final license agreement supplied with the product. The Developer tier is for evaluation and non-production work.",
  },
  {
    q: "Can an agency use it for client projects?",
    a: "The Agency tier is intended for consultancies adapting the platform for named client work, subject to the final commercial license terms. It is not an unrestricted right to republish ForestWatch as a competing source package.",
  },
  {
    q: "Does ForestWatch include hosting?",
    a: "No. You operate MongoDB, the API, and the frontend (locally, on your cloud, or otherwise). Docker Compose is included for local installation.",
  },
  {
    q: "Does it require Stripe?",
    a: "No. Billing is optional, disabled by default, and has not been validated against a live Stripe account in this package. Demo, trial, and intelligence do not depend on Stripe.",
  },
  {
    q: "Are live satellite or data-provider subscriptions included?",
    a: "No. Provider accounts and API keys belong to the licensee. FIRMS uses a bundled mock when unkeyed. Other providers are opt-in. Live availability is not guaranteed.",
  },
  {
    q: "What technologies are used?",
    a: "React (Create React App / CRACO, React Router, Axios, Leaflet, Tailwind) on the frontend. FastAPI, Pydantic, Motor/PyMongo, and MongoDB on the backend. JWT authentication, organization context, MongoDB 2dsphere indexes, an in-process asyncio scheduler, and Docker Compose. Stripe exists as an optional module.",
  },
  {
    q: "Is support included?",
    a: "Support terms are not defined on this page. They will be specified in the license agreement supplied with a purchase, if support is offered.",
  },
  {
    q: "Are updates included?",
    a: "Update entitlements are not defined on this page. Do not assume a support SLA or a guaranteed update stream until the license agreement says so.",
  },
  {
    q: "Can the entire project or IP be acquired?",
    a: "Yes, as a negotiated exclusive acquisition of original ForestWatch intellectual property. Third-party libraries, datasets, trademarks, and provider rights are not transferred by a source license. Use the Acquisition contact path.",
  },
];

function purchaseHref(url) {
  return url || COMMERCIAL.licensesPath;
}

export default function SalesPage() {
  return (
    <div className="sales" data-testid="sales-page">
      <a className="sales-skip" href="#sales-main">
        Skip to content
      </a>
      <header className="sales-nav">
        <div className="sales-nav-inner">
          <a className="sales-brand" href="/">
            ForestWatch
          </a>
          <nav className="sales-nav-links" aria-label="Sales">
            <a href={COMMERCIAL.platformPath}>Platform</a>
            <a href={COMMERCIAL.architecturePath}>Architecture</a>
            <a href={COMMERCIAL.licensesPath}>Licenses</a>
            <a href={COMMERCIAL.faqPath}>FAQ</a>
            <a
              className="sales-nav-demo"
              href={COMMERCIAL.demoPath}
              data-testid="sales-nav-demo"
            >
              Explore demo
            </a>
          </nav>
        </div>
      </header>

      <main id="sales-main">
        <section className="sales-section sales-hero">
          <p className="sales-kicker">Geospatial intelligence platform · source license</p>
          <h1>Build geospatial intelligence products without starting from zero.</h1>
          <p className="sales-lede">
            ForestWatch is a commercially licensed full-stack source-code platform for
            building geospatial monitoring and intelligence products. It combines
            multi-tenant organizations, AOIs, geospatial data ingestion, analytics,
            intelligence events, investigations, evidence, alerts, and a complete
            forest-monitoring reference application.
          </p>
          <div className="sales-cta-row">
            <a
              className="sales-btn sales-btn-primary"
              href={COMMERCIAL.demoPath}
              data-testid="sales-cta-demo"
            >
              Explore demo
            </a>
            <a
              className="sales-btn sales-btn-secondary"
              href={COMMERCIAL.licensesPath}
              data-testid="sales-cta-licenses"
            >
              View Licenses
            </a>
          </div>
          <p className="sales-stack">React · FastAPI · MongoDB · Docker</p>
        </section>

        <section className="sales-section" id="platform">
          <div className="sales-split sales-split-2">
            <div>
              <p className="sales-kicker">What you get</p>
              <h2>An operational architecture, not a component kit.</h2>
              <p className="sales-prose" style={{ marginTop: "1rem" }}>
                The package is the running ForestWatch application: ingestion through
                Command Center, with organizations and monitored areas as the tenancy
                boundary. Forestry is the included reference vertical. The systems
                below are in the source tree today.
              </p>
            </div>
            <ol className="sales-manifest">
              {MANIFEST.map(([n, title, body]) => (
                <li key={n}>
                  <code>{n}</code>
                  <div>
                    <strong>{title}</strong>
                    <div style={{ color: "var(--sales-muted)", marginTop: "0.2rem" }}>{body}</div>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className="sales-section" style={{ borderTop: "1px solid var(--sales-line)" }}>
          <p className="sales-kicker">Engineering value</p>
          <h2>Start from an operational architecture instead of assembling the foundation from separate libraries and prototypes.</h2>
          <p className="sales-prose" style={{ marginTop: "1rem" }}>
            A comparable geospatial intelligence product usually requires solving the
            same cluster of problems before any domain work is useful. ForestWatch
            already connects those pieces in one tested stack. This is not a claim
            about hours saved; it is a claim about where you begin.
          </p>
          <ul className="sales-problem-list">
            {FOUNDATION_PROBLEMS.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>

        <section className="sales-section" id="architecture" style={{ borderTop: "1px solid var(--sales-line)" }}>
          <p className="sales-kicker">Architecture</p>
          <h2>From provider observation to operator action.</h2>
          <p className="sales-prose" style={{ marginTop: "1rem", marginBottom: "2rem" }}>
            Organizations, AOIs, and entitlements cut across the pipeline. They are
            not a bolt-on dashboard theme.
          </p>
          <ArchitectureDiagram />
        </section>

        <section className="sales-section" style={{ borderTop: "1px solid var(--sales-line)" }}>
          <p className="sales-kicker">Product</p>
          <h2>The reference application is the forest-monitoring product.</h2>
          <p className="sales-prose" style={{ marginTop: "1rem", marginBottom: "1.75rem" }}>
            Command Center, map, investigation, alerts, and monitored areas are
            implemented screens. Captures of those screens belong here once supplied;
            they are not fabricated below.
          </p>
          <ProductShowcase />
        </section>

        <section className="sales-section" id="adapt" style={{ borderTop: "1px solid var(--sales-line)" }}>
          <p className="sales-kicker">Built for adaptation</p>
          <h2>Forestry is the reference. The architecture is the asset.</h2>
          <div className="sales-adapt-grid" style={{ marginTop: "1.75rem" }}>
            <div className="sales-col">
              <h3>Included reference functionality</h3>
              <ul>
                <li>Forest-monitoring taxonomy, AOIs, and operator UI</li>
                <li>Romanian demo catalog and intelligence seed as a worked geography</li>
                <li>FIRMS mock-or-live ingestion and opt-in environmental providers</li>
                <li>Investigations and alerts on that forest intelligence</li>
              </ul>
            </div>
            <div className="sales-col">
              <h3>Possible adaptation — not included out of the box</h3>
              <ul>
                <li>Infrastructure monitoring</li>
                <li>Environmental compliance products</li>
                <li>Land-use monitoring</li>
                <li>Wildfire intelligence as a dedicated product line</li>
                <li>Agricultural monitoring</li>
                <li>Industrial site monitoring</li>
              </ul>
            </div>
          </div>
        </section>

        <section className="sales-section" style={{ borderTop: "1px solid var(--sales-line)" }}>
          <p className="sales-kicker">Technical specification</p>
          <h2>Confirmed stack.</h2>
          <dl className="sales-spec" style={{ marginTop: "1.75rem" }}>
            <div>
              <dt>Frontend</dt>
              <dd>React, React Router, Axios, Leaflet, Tailwind CSS, Create React App with CRACO.</dd>
            </div>
            <div>
              <dt>Backend</dt>
              <dd>FastAPI, Pydantic, Motor and PyMongo against MongoDB.</dd>
            </div>
            <div>
              <dt>Platform</dt>
              <dd>
                JWT authentication, organization context, MongoDB 2dsphere indexes,
                in-process asyncio scheduler, Docker Compose. Stripe billing architecture
                is present, optional, and disabled by default.
              </dd>
            </div>
            <div>
              <dt>Testing</dt>
              <dd>
                Automated backend and frontend suites, a frozen Phase 0 intelligence
                oracle, and a repeated-run determinism check. Exact counts are not
                marketing copy; they live with the test runner.
              </dd>
            </div>
          </dl>
        </section>

        <section className="sales-section" id="licenses" style={{ borderTop: "1px solid var(--sales-line)" }}>
          <p className="sales-kicker">Licenses</p>
          <h2>Four ways to acquire the source.</h2>
          <p className="sales-prose" style={{ marginTop: "1rem", marginBottom: "1.75rem" }}>
            Prices below are the public list for this offering. Checkout is not
            implemented on this page; purchase links are configured centrally
            and currently lead to this section until store URLs are set.
          </p>
          <div className="sales-licenses">
            <article className="sales-license" data-testid="license-developer">
              <h3>{COMMERCIAL.developer.name}</h3>
              <div className="sales-price">{COMMERCIAL.developer.price}</div>
              <p>
                For an individual developer evaluating, adapting, or building from the
                platform.
              </p>
              <a
                className="sales-btn sales-btn-secondary"
                href={purchaseHref(COMMERCIAL.developer.purchaseUrl)}
                data-testid="license-developer-cta"
              >
                Choose Developer
              </a>
            </article>
            <article
              className="sales-license sales-license-rec"
              data-testid="license-commercial"
            >
              <div className="sales-rec">Recommended</div>
              <h3>{COMMERCIAL.commercial.name}</h3>
              <div className="sales-price">{COMMERCIAL.commercial.price}</div>
              <p>
                For a company or startup using ForestWatch as the foundation for one
                commercial product or deployment.
              </p>
              <a
                className="sales-btn sales-btn-primary"
                href={purchaseHref(COMMERCIAL.commercial.purchaseUrl)}
                data-testid="license-commercial-cta"
              >
                Choose Commercial
              </a>
            </article>
            <article className="sales-license" data-testid="license-agency">
              <h3>{COMMERCIAL.agency.name}</h3>
              <div className="sales-price">{COMMERCIAL.agency.price}</div>
              <p>
                For agencies and consultancies adapting the platform for client work,
                subject to the final commercial license terms.
              </p>
              <a
                className="sales-btn sales-btn-secondary"
                href={purchaseHref(COMMERCIAL.agency.purchaseUrl)}
                data-testid="license-agency-cta"
              >
                Choose Agency
              </a>
            </article>
          </div>
          <div className="sales-acquire" data-testid="license-acquisition">
            <div>
              <h3>{COMMERCIAL.acquisition.name}</h3>
              <div className="sales-price">{COMMERCIAL.acquisition.price}</div>
              <p className="sales-prose" style={{ marginTop: "0.35rem" }}>
                For organizations interested in broader rights, asset acquisition, or
                an exclusive transaction. Original ForestWatch IP only; third-party
                rights are excluded.
              </p>
            </div>
            <a
              className="sales-btn sales-btn-secondary"
              href={purchaseHref(COMMERCIAL.acquisition.contactUrl)}
              data-testid="license-acquisition-cta"
            >
              Contact for Acquisition
            </a>
          </div>
          <p className="sales-disclaimer">
            Commercial license terms are subject to the final license agreement
            supplied with the product.
          </p>
        </section>

        <section className="sales-section" id="limitations" style={{ borderTop: "1px solid var(--sales-line)" }}>
          <p className="sales-kicker">What is not included</p>
          <h2>Buy the source. Operate the rest.</h2>
          <ul className="sales-limits" style={{ marginTop: "1.5rem" }}>
            <li>Hosting and infrastructure are not included.</li>
            <li>External API and provider accounts may be required for live data.</li>
            <li>Provider availability is not guaranteed.</li>
            <li>
              Stripe billing integration is optional and should be independently
              validated before production use.
            </li>
            <li>
              Satellite imagery processing is not included as a proprietary processing
              pipeline.
            </li>
            <li>
              Environmental detection results must not be represented as legal
              determinations.
            </li>
            <li>
              Buyers are responsible for verifying third-party dataset and API
              licensing requirements.
            </li>
          </ul>
        </section>

        <section className="sales-section" id="faq" style={{ borderTop: "1px solid var(--sales-line)" }}>
          <p className="sales-kicker">FAQ</p>
          <h2>Straightforward answers.</h2>
          <div style={{ marginTop: "1.5rem" }}>
            {FAQ.map((item) => (
              <details key={item.q} className="sales-faq-item">
                <summary>{item.q}</summary>
                <p>{item.a}</p>
              </details>
            ))}
          </div>
        </section>

        <section className="sales-section sales-close">
          <h2>Start from the platform, not the plumbing.</h2>
          <div className="sales-cta-row">
            <a
              className="sales-btn sales-btn-primary"
              href={COMMERCIAL.demoPath}
              data-testid="sales-close-demo"
            >
              Explore the Demo
            </a>
            <a
              className="sales-btn sales-btn-secondary"
              href={COMMERCIAL.licensesPath}
              data-testid="sales-close-licenses"
            >
              Choose a License
            </a>
          </div>
          <p style={{ marginTop: "1.25rem" }}>
            <a
              href={purchaseHref(COMMERCIAL.acquisition.contactUrl)}
              style={{ color: "var(--sales-muted)" }}
              data-testid="sales-close-acquisition"
            >
              Discuss Acquisition
            </a>
          </p>
        </section>
      </main>

      <footer className="sales-footer">
        <div className="sales-footer-inner">
          <div>
            <strong style={{ color: "var(--sales-ink)" }}>ForestWatch</strong>
            <div>Geospatial Intelligence Platform</div>
            <div style={{ marginTop: "0.65rem" }}>
              © {new Date().getFullYear()} ForestWatch. Proprietary source. See LICENSE.
            </div>
          </div>
          <nav className="sales-footer-links" aria-label="Footer">
            <a href={COMMERCIAL.documentationUrl}>Documentation</a>
            <a href={COMMERCIAL.demoPath}>Demo</a>
            <a href={COMMERCIAL.licensesPath}>Licenses</a>
            <a href={COMMERCIAL.architecturePath}>Architecture</a>
          </nav>
        </div>
      </footer>
    </div>
  );
}
