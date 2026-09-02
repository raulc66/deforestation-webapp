import { Link } from "react-router-dom";
import SurfaceCard from "@/components/product/SurfaceCard";

const COPY = {
  investigation: {
    title: "Monitor a forest like this",
    body: "Create a trial organization and watch your own stands with the same investigation workflow.",
    action: "Create your trial organization",
    to: "/register?from=demo",
  },
  alert: {
    title: "Stay informed when this changes",
    body: "Alert policies belong to your organization. Trial delivery goes only to your account email.",
    action: "Configure alerts for your forest",
    to: "/alerts",
  },
  area_limit: {
    title: "Add more monitored forests with Professional",
    body: "Your trial includes two forests. Existing areas stay in place.",
    action: "View plans",
    to: "/billing",
  },
  expired: {
    title: "Continue monitoring",
    body: "Historical intelligence remains available. New monitoring and alert delivery resume with a paid plan.",
    action: "Continue monitoring",
    to: "/billing",
  },
  setup: {
    title: "Monitor a forest like this",
    body: "Name the organization and add a monitored area to reach the Command Center.",
    action: "Set up your trial",
    to: "/trial/setup",
  },
};

export default function TrialConversionCta({ moment, to, onClick }) {
  const copy = COPY[moment];
  if (!copy) return null;
  const href = to || copy.to;

  return (
    <SurfaceCard variant="inset" className="p-4 mt-4" testId={`trial-conversion-${moment}`}>
      <div className="fw-kicker mb-1">Next</div>
      <h3 className="text-sm font-semibold text-[var(--text-primary)]">{copy.title}</h3>
      <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">{copy.body}</p>
      <Link
        to={href}
        onClick={onClick}
        className="inline-flex mt-3 fw-button-primary text-xs py-2 px-3"
        data-testid="trial-conversion-cta"
      >
        {copy.action}
      </Link>
    </SurfaceCard>
  );
}
