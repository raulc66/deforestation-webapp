import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import AppLayout from "@/components/layout/AppLayout";
import SurfaceCard from "@/components/product/SurfaceCard";
import { useOrganization } from "@/context/OrganizationContext";
import { useTrial } from "@/context/TrialContext";
import { createMonitoringArea } from "@/api/monitoringAreas";
import { updateOrganization } from "@/api/organizations";

function bboxPolygon(west, south, east, north) {
  const w = Number(west);
  const s = Number(south);
  const e = Number(east);
  const n = Number(north);
  return {
    type: "Polygon",
    coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
  };
}

export default function TrialSetupPage() {
  const navigate = useNavigate();
  const { currentOrganization, reload } = useOrganization();
  const { status, isExpired, startTrial, reload: reloadTrial } = useTrial();
  const [orgName, setOrgName] = useState("");
  const [areaName, setAreaName] = useState("");
  const [country, setCountry] = useState("Romania");
  const [west, setWest] = useState("25.5");
  const [south, setSouth] = useState("46.8");
  const [east, setEast] = useState("26.5");
  const [north, setNorth] = useState("47.5");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [started, setStarted] = useState(false);

  useEffect(() => {
    if (started) return;
    setStarted(true);
    (async () => {
      try {
        if (!status || status.commercial_lifecycle === "unsubscribed") {
          const next = await startTrial(
            orgName.trim() ? { organization_name: orgName.trim() } : {}
          );
          if (next?.organization_name) setOrgName(next.organization_name);
        } else if (status.organization_name && !orgName) {
          setOrgName(status.organization_name);
        }
      } catch (err) {
        setError(err?.response?.data?.detail || err.message || "Could not start the trial.");
      }
    })();
  }, [orgName, startTrial, started, status]);

  useEffect(() => {
    if (status?.organization_name && !orgName) {
      setOrgName(status.organization_name);
    }
  }, [orgName, status]);

  const onSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setSaving(true);
    try {
      const organizationId = status?.organization_id || currentOrganization?.id;
      if (orgName.trim() && organizationId) {
        await updateOrganization(organizationId, { name: orgName.trim() });
        await reload();
      }
      if (areaName.trim()) {
        await createMonitoringArea({
          name: areaName.trim(),
          country: country.trim() || "Romania",
          geometry: bboxPolygon(west, south, east, north),
          enabled: true,
        });
      }
      await reloadTrial();
      navigate("/dashboard", { replace: true });
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || "Could not save the monitored area.");
    } finally {
      setSaving(false);
    }
  };

  if (isExpired) {
    return (
      <AppLayout>
        <div className="max-w-2xl mx-auto px-5 py-8" data-testid="trial-setup-page">
          <div className="fw-kicker mb-2">Trial ended</div>
          <h1 className="text-2xl font-bold tracking-tight">Continue monitoring</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-2 leading-relaxed">
            Your organization and historical intelligence remain available. New monitored
            areas and alert delivery resume with a paid plan.
          </p>
          <Link to="/billing" className="inline-flex mt-4 fw-button-primary text-sm py-2 px-3">
            View plans
          </Link>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="max-w-2xl mx-auto px-5 py-8" data-testid="trial-setup-page">
        <div className="fw-kicker mb-2">Trial organization</div>
        <h1 className="text-2xl font-bold tracking-tight">Set up monitoring</h1>
        <p className="text-sm text-[var(--text-secondary)] mt-2 mb-6 leading-relaxed max-w-xl">
          This is a real ForestWatch organization. Add one forest, then open the Command Center.
        </p>

        <form onSubmit={onSubmit} className="space-y-5" data-testid="trial-setup-form">
          <SurfaceCard className="p-4">
            <label className="block text-sm font-medium mb-1" htmlFor="trial-org-name">
              Organization
            </label>
            <input
              id="trial-org-name"
              data-testid="trial-org-name"
              className="w-full h-10 px-3 border border-[var(--surface-inset)] rounded-md bg-white text-sm"
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              placeholder="Carpathian Watch"
            />
          </SurfaceCard>

          <SurfaceCard className="p-4">
            <label className="block text-sm font-medium mb-1" htmlFor="trial-area-name">
              Forest / area to monitor
            </label>
            <input
              id="trial-area-name"
              data-testid="trial-area-name"
              className="w-full h-10 px-3 border border-[var(--surface-inset)] rounded-md bg-white text-sm mb-3"
              value={areaName}
              onChange={(e) => setAreaName(e.target.value)}
              placeholder="Harghita working forest"
              required
            />
            <label className="block text-sm font-medium mb-1" htmlFor="trial-country">
              Country
            </label>
            <input
              id="trial-country"
              data-testid="trial-country"
              className="w-full h-10 px-3 border border-[var(--surface-inset)] rounded-md bg-white text-sm mb-3"
              value={country}
              onChange={(e) => setCountry(e.target.value)}
            />
            <p className="text-xs text-[var(--text-muted)] mb-2">
              Bounding box in WGS84 (west, south, east, north). A GIS editor is not required for trial setup.
            </p>
            <div className="grid grid-cols-2 gap-2">
              {[["west", west, setWest], ["south", south, setSouth], ["east", east, setEast], ["north", north, setNorth]].map(
                ([id, value, setter]) => (
                  <input
                    key={id}
                    data-testid={`trial-bbox-${id}`}
                    aria-label={id}
                    className="h-10 px-3 border border-[var(--surface-inset)] rounded-md bg-white text-sm font-mono"
                    value={value}
                    onChange={(e) => setter(e.target.value)}
                    required
                  />
                )
              )}
            </div>
          </SurfaceCard>

          <SurfaceCard variant="inset" className="p-4 space-y-3 text-sm" testId="trial-setup-briefing">
            <div>
              <div className="fw-kicker mb-1">What ForestWatch currently detects</div>
              <p className="text-[var(--text-secondary)] leading-relaxed">
                Forest disturbance inside your monitored areas, with cross-source evidence when
                live sources are available. Satellite disturbance is not a legal finding.
              </p>
            </div>
            <div>
              <div className="fw-kicker mb-1">What should require your attention</div>
              <p className="text-[var(--text-secondary)] leading-relaxed">
                High and critical investigation-priority disturbance inside a watched forest,
                especially repeated activity or unknown authorization.
              </p>
            </div>
            <div>
              <div className="fw-kicker mb-1">How alerts work</div>
              <p className="text-[var(--text-secondary)] leading-relaxed">
                You create a policy against investigation priority and evidence. During the trial,
                delivery is limited to your account email — ForestWatch will not send to arbitrary addresses.
              </p>
            </div>
          </SurfaceCard>

          {error && (
            <p className="text-sm text-[var(--signal-strong)]" data-testid="trial-setup-error">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={saving}
            className="fw-button-primary text-sm py-2.5 px-4"
            data-testid="trial-setup-submit"
          >
            {saving ? "Saving…" : "Open Command Center"}
          </button>
        </form>
      </div>
    </AppLayout>
  );
}
