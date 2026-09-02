import { remainingLabel } from "@/lib/demo";

const METERS = [
  { key: "investigation", label: "Demo analyses remaining" },
  { key: "alert_simulation", label: "Alert simulations remaining" },
  { key: "report", label: "Reports remaining" },
];

export default function DemoBudgetBar({ status }) {
  const investigation = remainingLabel(status, "investigation");
  if (!status?.budget) return null;

  return (
    <div
      className="flex flex-wrap items-center gap-x-5 gap-y-1 text-xs text-[var(--text-secondary)]"
      data-testid="demo-budget-bar"
    >
      {METERS.map((meter) => {
        const values = remainingLabel(status, meter.key);
        if (!values) return null;
        return (
          <span key={meter.key} data-testid={`demo-budget-${meter.key}`}>
            {meter.label}:{" "}
            <span className="font-mono tabular-nums font-semibold text-[var(--text-primary)]">
              {values.remaining} / {values.limit}
            </span>
          </span>
        );
      })}
      {investigation && investigation.remaining === 0 && (
        <span className="text-[var(--signal)]" data-testid="demo-budget-exhausted-hint">
          Analyses used
        </span>
      )}
    </div>
  );
}
