import SurfaceCard from "@/components/product/SurfaceCard";

export default function DemoGuideRail({
  guide = [],
  currentStep,
  onSelect,
}) {
  if (!guide.length) return null;

  return (
    <SurfaceCard className="p-4" testId="demo-guide-rail">
      <div className="fw-kicker mb-3">Guided path</div>
      <p className="text-xs text-[var(--text-muted)] mb-3">
        Follow these steps, or explore the map and queue freely.
      </p>
      <ol className="space-y-1">
        {guide.map((step, index) => {
          const active = step.id === currentStep;
          return (
            <li key={step.id}>
              <button
                type="button"
                onClick={() => onSelect?.(step.id)}
                className={`w-full text-left rounded-md px-2.5 py-2 transition-colors ${
                  active
                    ? "bg-[var(--surface-subtle)] border border-[var(--accent)]"
                    : "border border-transparent hover:bg-[var(--surface-subtle)]"
                }`}
                data-testid={`demo-guide-step-${step.id}`}
              >
                <div className="flex items-baseline gap-2">
                  <span className="font-mono text-[10px] text-[var(--text-muted)]">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span className="text-sm font-semibold text-[var(--text-primary)]">
                    {step.title}
                  </span>
                </div>
                {active && step.body && (
                  <p className="text-xs text-[var(--text-secondary)] mt-1 ml-6">
                    {step.body}
                  </p>
                )}
              </button>
            </li>
          );
        })}
      </ol>
    </SurfaceCard>
  );
}
