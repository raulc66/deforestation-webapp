import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import SurfaceCard from "@/components/product/SurfaceCard";
import { PRIORITY_LABELS, EVIDENCE_LABELS, channelTypeLabel } from "@/design/semanticStates";

const DEFAULT_POLICY = {
  name: "",
  enabled: true,
  incident_categories: ["forest_disturbance"],
  minimum_investigation_priority: "medium",
  minimum_severity: "medium",
  minimum_evidence_state: "",
  monitored_area_ids: [],
  notification_channel_ids: [],
  cooldown_minutes: 60,
};

function toggle(list, value) {
  return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
}

function Field({ label, hint, htmlFor, children }) {
  return (
    <div className="space-y-1.5">
      <label className="fw-kicker block" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
      {hint && <p className="text-xs text-[var(--text-muted)]">{hint}</p>}
    </div>
  );
}

const inputClass =
  "w-full rounded-md border border-[var(--surface-inset)] bg-white px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]";

/**
 * Create / edit an alert policy in customer language: what it watches, when it
 * triggers, where it delivers, and how often it may repeat.
 */
export default function AlertPolicyForm({
  policy,
  options,
  monitoredAreas = [],
  channels = [],
  onSubmit,
  onCancel,
  submitting = false,
  error = null,
}) {
  const [draft, setDraft] = useState(() => ({
    ...DEFAULT_POLICY,
    ...(policy
      ? {
          name: policy.name ?? "",
          enabled: policy.enabled ?? true,
          incident_categories: policy.incident_categories ?? ["forest_disturbance"],
          minimum_investigation_priority: policy.minimum_investigation_priority ?? "medium",
          minimum_severity: policy.minimum_severity ?? "medium",
          minimum_evidence_state: policy.minimum_evidence_state ?? "",
          monitored_area_ids: policy.monitored_area_ids ?? [],
          notification_channel_ids: policy.notification_channel_ids ?? [],
          cooldown_minutes: policy.cooldown_minutes ?? 60,
        }
      : {}),
  }));

  const categories = useMemo(
    () =>
      options?.incident_categories ?? [
        { value: "forest_disturbance", label: "Forest Disturbance" },
      ],
    [options]
  );
  const priorities = options?.investigation_priorities ?? ["low", "medium", "high", "critical"];
  const severities = options?.severity_levels ?? ["low", "medium", "high", "critical"];
  const evidenceStates = options?.evidence_states ?? [];

  const isEditing = Boolean(policy?.id);

  const handleSubmit = (event) => {
    event.preventDefault();
    onSubmit({
      ...draft,
      cooldown_minutes: Number(draft.cooldown_minutes) || 0,
      minimum_evidence_state: draft.minimum_evidence_state || null,
    });
  };

  return (
    <SurfaceCard variant="inset" className="p-5" testId="alert-policy-form">
      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <h3 className="text-base font-bold text-[var(--text-primary)]">
            {isEditing ? "Edit alert policy" : "New alert policy"}
          </h3>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Decide which forest intelligence reaches your team, and how often.
          </p>
        </div>

        {error && (
          <p className="text-sm text-[var(--signal-strong)]" data-testid="alert-policy-form-error">
            {error}
          </p>
        )}

        <Field label="Policy name" htmlFor="policy-name">
          <input
            id="policy-name"
            className={inputClass}
            data-testid="policy-name-input"
            value={draft.name}
            onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            placeholder="Harghita concession watch"
            required
          />
        </Field>

        <Field
          label="Intelligence watched"
          hint="Only categories your organization monitors are listed."
        >
          <div className="flex flex-wrap gap-2" data-testid="policy-categories">
            {categories.map((category) => {
              const active = draft.incident_categories.includes(category.value);
              return (
                <button
                  key={category.value}
                  type="button"
                  data-testid={`policy-category-${category.value}`}
                  aria-pressed={active}
                  onClick={() =>
                    setDraft({
                      ...draft,
                      incident_categories: toggle(draft.incident_categories, category.value),
                    })
                  }
                  className={`rounded-md border px-3 py-1.5 text-xs transition-colors ${
                    active
                      ? "border-[var(--accent)] bg-[var(--surface-subtle)] font-semibold"
                      : "border-[var(--surface-inset)] text-[var(--text-muted)]"
                  }`}
                >
                  {category.label}
                </button>
              );
            })}
          </div>
        </Field>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Field label="Triggers at investigation priority" htmlFor="policy-priority">
            <select
              id="policy-priority"
              className={inputClass}
              data-testid="policy-priority-select"
              value={draft.minimum_investigation_priority}
              onChange={(e) =>
                setDraft({ ...draft, minimum_investigation_priority: e.target.value })
              }
            >
              {priorities.map((value) => (
                <option key={value} value={value}>
                  {PRIORITY_LABELS[value] ?? value} and above
                </option>
              ))}
            </select>
          </Field>

          <Field label="Triggers at severity" htmlFor="policy-severity">
            <select
              id="policy-severity"
              className={inputClass}
              data-testid="policy-severity-select"
              value={draft.minimum_severity}
              onChange={(e) => setDraft({ ...draft, minimum_severity: e.target.value })}
            >
              {severities.map((value) => (
                <option key={value} value={value}>
                  {PRIORITY_LABELS[value] ?? value} and above
                </option>
              ))}
            </select>
          </Field>

          <Field
            label="Minimum evidence"
            htmlFor="policy-evidence"
            hint="Optional. Requires supporting evidence before notifying."
          >
            <select
              id="policy-evidence"
              className={inputClass}
              data-testid="policy-evidence-select"
              value={draft.minimum_evidence_state}
              onChange={(e) => setDraft({ ...draft, minimum_evidence_state: e.target.value })}
            >
              <option value="">Any evidence</option>
              {evidenceStates.map((value) => (
                <option key={value} value={value}>
                  {EVIDENCE_LABELS[value] ?? value}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <Field
          label="Monitored areas"
          hint="Leave empty to cover every monitored area in this organization."
        >
          {monitoredAreas.length === 0 ? (
            <p className="text-sm text-[var(--text-muted)]" data-testid="policy-no-areas">
              No monitored areas configured yet.
            </p>
          ) : (
            <div className="space-y-1.5" data-testid="policy-areas">
              {monitoredAreas.map((area) => (
                <label
                  key={area.id}
                  className="flex items-center gap-2 text-sm text-[var(--text-primary)]"
                >
                  <input
                    type="checkbox"
                    data-testid={`policy-area-${area.id}`}
                    checked={draft.monitored_area_ids.includes(area.id)}
                    onChange={() =>
                      setDraft({
                        ...draft,
                        monitored_area_ids: toggle(draft.monitored_area_ids, area.id),
                      })
                    }
                  />
                  {area.name}
                </label>
              ))}
            </div>
          )}
        </Field>

        <Field label="Notification channels">
          {channels.length === 0 ? (
            <p className="text-sm text-[var(--text-muted)]" data-testid="policy-no-channels">
              Add a notification channel before this policy can deliver alerts.
            </p>
          ) : (
            <div className="space-y-1.5" data-testid="policy-channels">
              {channels.map((channel) => (
                <label
                  key={channel.id}
                  className="flex items-center gap-2 text-sm text-[var(--text-primary)]"
                >
                  <input
                    type="checkbox"
                    data-testid={`policy-channel-${channel.id}`}
                    checked={draft.notification_channel_ids.includes(channel.id)}
                    onChange={() =>
                      setDraft({
                        ...draft,
                        notification_channel_ids: toggle(
                          draft.notification_channel_ids,
                          channel.id
                        ),
                      })
                    }
                  />
                  <span>{channel.name}</span>
                  <span className="text-xs text-[var(--text-muted)]">
                    {channelTypeLabel(channel.channel_type)}
                    {channel.enabled ? "" : " · Paused"}
                  </span>
                </label>
              ))}
            </div>
          )}
        </Field>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field
            label="Cooldown (minutes)"
            htmlFor="policy-cooldown"
            hint="Minimum wait before this policy notifies again about the same forest."
          >
            <input
              id="policy-cooldown"
              type="number"
              min={0}
              max={options?.max_cooldown_minutes ?? 10080}
              className={inputClass}
              data-testid="policy-cooldown-input"
              value={draft.cooldown_minutes}
              onChange={(e) => setDraft({ ...draft, cooldown_minutes: e.target.value })}
            />
          </Field>

          <Field label="Status">
            <label className="flex items-center gap-2 text-sm text-[var(--text-primary)]">
              <input
                type="checkbox"
                data-testid="policy-enabled-input"
                checked={draft.enabled}
                onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
              />
              Active — deliver alerts for this policy
            </label>
          </Field>
        </div>

        <div className="flex items-center gap-2 pt-1">
          <Button type="submit" disabled={submitting} data-testid="policy-submit-btn">
            {isEditing ? "Save policy" : "Create policy"}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={onCancel}
            data-testid="policy-cancel-btn"
          >
            Cancel
          </Button>
        </div>
      </form>
    </SurfaceCard>
  );
}
