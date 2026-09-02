import StatusBadge from "./StatusBadge";
import { PRIORITY_LABELS } from "@/design/semanticStates";

export default function PriorityBadge({ priority, testId }) {
  const key = String(priority || "medium").toLowerCase();
  const label = PRIORITY_LABELS[key] ?? priority ?? "—";
  return (
    <StatusBadge
      variant={["critical", "high", "medium", "low"].includes(key) ? key : "medium"}
      label={`${label} priority`}
      testId={testId ?? `priority-badge-${key}`}
    />
  );
}
