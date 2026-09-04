import { useEffect, useRef } from "react";
import { MapPin, Repeat2, ShieldQuestion } from "lucide-react";
import SurfaceCard from "@/components/product/SurfaceCard";
import PriorityBadge from "@/components/product/PriorityBadge";
import EvidenceBlock from "@/components/product/EvidenceBlock";
import StatusBadge from "@/components/product/StatusBadge";
import {
  formatAuthorizationLabel,
  formatDriverLabel,
} from "@/design/semanticStates";
import { useDemo } from "@/context/DemoContext";
import { useTrial } from "@/context/TrialContext";
import TrialConversionCta from "@/components/trial/TrialConversionCta";
import { demoSimulationNotice } from "@/lib/demo";

const ASSESSMENT_LABEL = "Potential Unauthorized Forest Activity";

/**
 * Investigation workflow for forest disturbance — semantic safety preserved.
 * Observation, inference, evidence, unknown, and action stay visually distinct.
 */
export default function DisturbanceInvestigationPanel({
  item,
  onInvestigate,
  isDemo = false,
  opened = false,
  testId = "disturbance-investigation-panel",
}) {
  const demo = useDemo();
  const trial = useTrial();
  const demoMode = isDemo || demo.isDemo;
  const panelRef = useRef(null);

  useEffect(() => {
    if (!demoMode || !item) return;
    demo.recordEvent?.("evidence_viewed", { event_id: item.event_id });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demoMode, item?.event_id]);

  useEffect(() => {
    if (!opened || !panelRef.current) return;
    if (typeof panelRef.current.scrollIntoView === "function") {
      panelRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (typeof panelRef.current.focus === "function") {
      panelRef.current.focus();
    }
  }, [opened, item?.event_id]);

  if (!item) {
    return (
      <SurfaceCard variant="inset" className="p-5 h-full min-h-[280px] flex items-center justify-center" testId={testId}>
        <p className="text-sm text-[var(--text-muted)] text-center max-w-xs" data-testid="disturbance-panel-empty">
          Select a forest disturbance signal to review evidence, monitored-area relevance, and investigation priority.
        </p>
      </SurfaceCard>
    );
  }

  const disturbance = item.disturbance_assessment ?? {};
  const monitored = item.monitored_area ?? {};
  const summary = item.evidence_summary ?? {};
  const assessment =
    disturbance.assessment_label && disturbance.assessment_label !== ASSESSMENT_LABEL
      ? ASSESSMENT_LABEL
      : disturbance.assessment_label ?? ASSESSMENT_LABEL;

  const insideAoi = monitored.inside_monitored_area || monitored.relevance === "inside_monitored_area";
  const affectedHa = disturbance.affected_area_ha;
  const authorization = disturbance.authorization_status ?? "unknown";
  const unknownBits = [
    formatAuthorizationLabel(authorization),
    "Satellite disturbance and inferred drivers do not establish illegality without authoritative verification.",
  ];

  const handleInvestigate = () => {
    onInvestigate?.(item);
  };

  const handleSimulate = async () => {
    const result = await demo.simulateAlert?.(item.event_id);
    if (result?.ok) {
      demo.setGuideStep?.("monitor");
    }
  };
  const simulationNotice = demoSimulationNotice(demo.lastSimulation);

  return (
    <SurfaceCard variant="inset" className="p-5" testId={testId}>
      <div
        ref={panelRef}
        tabIndex={opened ? -1 : undefined}
        className={opened ? "outline-none" : undefined}
        data-testid={opened ? "investigation-opened" : undefined}
      >
      <div className="fw-kicker mb-2">{opened ? "Investigation open" : "Investigation focus"}</div>
      {opened && (
        <p
          className="mb-3 text-sm text-[var(--text-secondary)] leading-relaxed"
          data-testid="investigation-opened-copy"
        >
          Review observation, inference, and evidence for this prepared demonstration disturbance.
          Satellite disturbance is not a legal finding.
        </p>
      )}
      <h3 className="text-base font-bold tracking-tight text-[var(--text-primary)] leading-snug">
        {assessment}
      </h3>

      <div className="mt-3 flex flex-wrap gap-2">
        {disturbance.investigation_priority && (
          <PriorityBadge priority={disturbance.investigation_priority} testId="disturbance-priority" />
        )}
        {insideAoi ? (
          <StatusBadge variant="enabled" label="Inside monitored area" testId="disturbance-inside-aoi" />
        ) : (
          <StatusBadge variant="unavailable" label="Outside monitored areas" testId="disturbance-outside-aoi" />
        )}
        {disturbance.repeat_activity && (
          <StatusBadge variant="degraded" label="Repeated activity" testId="disturbance-repeat" />
        )}
      </div>

      <section className="mt-5" data-testid="investigation-observation">
        <div className="fw-kicker mb-2">Observation</div>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
          {typeof affectedHa === "number" && (
            <div>
              <dt className="fw-kicker">Affected area</dt>
              <dd className="font-mono tabular-nums font-semibold">{affectedHa.toFixed(1)} ha</dd>
            </div>
          )}
          {monitored.name && (
            <div>
              <dt className="fw-kicker flex items-center gap-1">
                <MapPin className="w-3 h-3" /> Monitored area
              </dt>
              <dd className="font-medium">{monitored.name}</dd>
            </div>
          )}
          {item.region && (
            <div>
              <dt className="fw-kicker">Region</dt>
              <dd>{item.region}</dd>
            </div>
          )}
        </dl>
        <p className="text-xs text-[var(--text-muted)] mt-2">
          What was detected in a watched forest — not a legal finding.
        </p>
      </section>

      <section className="mt-5 pt-4 border-t border-[var(--surface-inset)]" data-testid="investigation-inference">
        <div className="fw-kicker mb-2">Inference</div>
        {disturbance.probable_driver ? (
          <p className="text-sm font-medium text-[var(--text-primary)]">
            {formatDriverLabel(disturbance.probable_driver)}
            {typeof disturbance.driver_confidence === "number" && (
              <span className="text-[var(--text-muted)] font-normal">
                {" "}
                · {Math.round(disturbance.driver_confidence * 100)}% confidence
              </span>
            )}
          </p>
        ) : (
          <p className="text-sm text-[var(--text-muted)]">No driver inferred yet.</p>
        )}
        <p className="text-xs text-[var(--text-muted)] mt-1">
          What ForestWatch believes may be happening. Inferred — not legal determination.
        </p>
        {disturbance.repeat_activity && (
          <div className="mt-2 flex items-center gap-1.5 text-xs text-[var(--text-secondary)]">
            <Repeat2 className="w-3.5 h-3.5" />
            Repeat activity raises investigative importance for this stand.
          </div>
        )}
      </section>

      <section
        className={`mt-5 pt-4 border-t border-[var(--surface-inset)]${opened ? " rounded-md ring-1 ring-[var(--accent)]/40 px-3 pb-3" : ""}`}
        data-testid="investigation-evidence"
      >
        <EvidenceBlock summary={summary} disturbance={disturbance} />
      </section>

      <section className="mt-5 pt-4 border-t border-[var(--surface-inset)]" data-testid="investigation-unknown">
        <div className="fw-kicker mb-2">Unknown</div>
        <div className="flex items-start gap-2 text-xs text-[var(--text-muted)]">
          <ShieldQuestion className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          <p>{unknownBits.join(". ")}</p>
        </div>
      </section>

      <section className="mt-5 pt-4 border-t border-[var(--surface-inset)]" data-testid="investigation-action">
        <div className="fw-kicker mb-2">Action</div>
        {onInvestigate && (
          <button
            type="button"
            onClick={handleInvestigate}
            className="w-full fw-button-primary"
            data-testid="disturbance-investigate-btn"
          >
            {opened ? "Investigation open" : "Open investigation"}
          </button>
        )}
        {demoMode && (
          <button
            type="button"
            onClick={handleSimulate}
            className="mt-2 w-full text-sm font-semibold px-4 py-2.5 rounded-md border border-[var(--surface-inset)] hover:bg-[var(--surface-subtle)]"
            data-testid="demo-simulate-alert"
          >
            Simulate a notification
          </button>
        )}
        {simulationNotice && (
          <p className="mt-2 text-xs text-[var(--text-secondary)]" data-testid="demo-simulated-delivery">
            {simulationNotice}
          </p>
        )}
        {trial.isTrial && !demoMode && (
          <TrialConversionCta moment="alert" />
        )}
      </section>
      </div>
    </SurfaceCard>
  );
}
