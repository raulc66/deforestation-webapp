import { Link } from "react-router-dom";
import SurfaceCard from "@/components/product/SurfaceCard";

const COPY = {
  investigation: {
    title: "Monitor a forest like this one",
    body: "Create a trial organization to watch your own stands with the same investigation workflow.",
  },
  alert: {
    title: "Get notified when this happens in your forests",
    body: "Alert policies belong to your organization. Demonstration delivery is simulated and never sends email.",
  },
  exhausted: {
    title: "Create your trial organization",
    body: "You've explored the ForestWatch intelligence engine. Continue monitoring your own forests.",
  },
};

export default function DemoConversionCta({ moment, onClick }) {
  const copy = COPY[moment];
  if (!copy) return null;

  return (
    <SurfaceCard variant="inset" className="p-4 mt-4" testId={`demo-conversion-${moment}`}>
      <div className="fw-kicker mb-1">Next</div>
      <h3 className="text-sm font-semibold text-[var(--text-primary)]">{copy.title}</h3>
      <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">{copy.body}</p>
      <Link
        to="/register?from=demo"
        onClick={onClick}
        className="inline-flex mt-3 fw-button-primary text-xs py-2 px-3"
        data-testid="demo-conversion-cta"
      >
        Create your trial organization
      </Link>
    </SurfaceCard>
  );
}
