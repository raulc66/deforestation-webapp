export default function DemoScenarioSwitcher({
  scenarios = [],
  focused,
  onSelect,
}) {
  if (!scenarios.length) return null;

  return (
    <div data-testid="demo-scenario-switcher">
      <div className="fw-kicker mb-2">Demonstration scenarios</div>
      <div className="flex flex-wrap gap-2">
        {scenarios.map((scenario) => {
          const active = focused === scenario.id;
          return (
            <button
              key={scenario.id}
              type="button"
              onClick={() => onSelect?.(scenario.id)}
              className={`text-xs px-3 py-1.5 rounded-md border transition-colors ${
                active
                  ? "border-[var(--accent)] bg-[var(--surface-subtle)] font-semibold"
                  : "border-[var(--surface-inset)] text-[var(--text-secondary)] hover:bg-[var(--surface-subtle)]"
              }`}
              data-testid={`demo-scenario-${scenario.id}`}
            >
              {scenario.title}
            </button>
          );
        })}
      </div>
      {focused && (
        <p className="text-xs text-[var(--text-muted)] mt-2" data-testid="demo-scenario-summary">
          {scenarios.find((item) => item.id === focused)?.summary}
        </p>
      )}
    </div>
  );
}
