import { Link } from "react-router-dom";
import SurfaceCard from "@/components/product/SurfaceCard";

export default function TrialOnboarding({ status }) {
  if (!status || status.onboarding?.complete) return null;
  if (status.commercial_lifecycle !== "trial") return null;

  return (
    <SurfaceCard className="p-4 mb-5" testId="trial-onboarding">
      <div className="fw-kicker mb-1">Trial setup</div>
      <h2 className="text-base font-semibold text-[var(--text-primary)]">
        Add a forest to monitor
      </h2>
      <p className="text-sm text-[var(--text-secondary)] mt-1 leading-relaxed max-w-xl">
        ForestWatch watches organization areas, then ranks disturbance that needs attention.
        Add one monitored forest to start using the Command Center with your own geometry.
      </p>
      <Link
        to="/trial/setup"
        className="inline-flex mt-3 fw-button-primary text-xs py-2 px-3"
        data-testid="trial-onboarding-continue"
      >
        Set up monitored area
      </Link>
    </SurfaceCard>
  );
}
