import SurfaceCard from "@/components/product/SurfaceCard";

export default function DemoGuideRail({
  guide = [],
  currentStep,
  onSelect,
}) {
  if (!guide.length) return null;

  return (
    <SurfaceCard className="p-3 xl:p-4" testId="demo-guide-rail">
      <div className="fw-kicker mb-2 xl:mb-3">Guided path</div>
      <p
        className="hidden xl:block text-xs text-[var(--text-muted)] mb-3"
        data-testid="demo-guide-intro"
      >
        Follow these steps, or explore the map and queue freely.
      </p>
      <ol className="space-y-0 xl:space-y-1">
        {guide.map((step, index) => {
          const active = step.id === currentStep;
          return (
            <li key={step.id}>
              <button
                type="button"
                onClick={() => onSelect?.(step.id)}
                aria-current={active ? "step" : undefined}
                className={`w-full text-left rounded-md min-w-0 ${
                  active
                    ? "bg-[var(--surface-subtle)] border border-[var(--accent)] px-2.5 py-2"
                    : "border border-transparent hover:bg-[var(--surface-subtle)] px-2.5 py-0.5 xl:py-2"
                }`}
                data-testid={`demo-guide-step-${step.id}`}
              >
                <div className="flex items-baseline gap-2">
                  <span className="font-mono text-[10px] text-[var(--text-muted)]">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <span
                    className={`break-words min-w-0 ${
                      active
                        ? "text-sm font-semibold text-[var(--text-primary)]"
                        : "text-xs xl:text-sm font-medium xl:font-semibold text-[var(--text-secondary)] xl:text-[var(--text-primary)]"
                    }`}
                  >
                    {step.title}
                  </span>
                </div>
                {active && step.body && (
                  <p
                    className="text-xs text-[var(--text-secondary)] mt-1 ml-6"
                    data-testid={`demo-guide-step-body-${step.id}`}
                  >
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
