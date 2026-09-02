import { Pause, Pencil, Play, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import SurfaceCard from "@/components/product/SurfaceCard";
import StatusBadge from "@/components/product/StatusBadge";
import UpgradePrompt from "@/components/billing/UpgradePrompt";
import {
  PRIORITY_LABELS,
  activationLabel,
  channelTypeLabel,
  formatCooldown,
} from "@/design/semanticStates";

function categoryLabel(value, options) {
  const match = (options?.incident_categories ?? []).find((c) => c.value === value);
  return match?.label ?? String(value).replace(/_/g, " ");
}

function PolicyRow({ policy, options, areasById, channelsById, canManage, onEdit, onToggle, onDelete }) {
  const areaNames = (policy.monitored_area_ids ?? [])
    .map((id) => areasById[id])
    .filter(Boolean);
  const channelNames = (policy.notification_channel_ids ?? [])
    .map((id) => channelsById[id])
    .filter(Boolean);

  return (
    <li
      className="p-4 border border-[var(--surface-inset)] rounded-md"
      data-testid={`alert-policy-${policy.id}`}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-semibold text-[var(--text-primary)] truncate">
              {policy.name}
            </h4>
            <StatusBadge
              variant={policy.enabled ? "enabled" : "disabled"}
              label={activationLabel(policy.enabled)}
              testId={`alert-policy-${policy.id}-status`}
            />
          </div>
          <p className="text-xs text-[var(--text-muted)] mt-1">
            Watches{" "}
            {(policy.incident_categories ?? [])
              .map((c) => categoryLabel(c, options))
              .join(", ") || "all intelligence"}
          </p>
        </div>

        {canManage && (
          <div className="flex items-center gap-1.5">
            <Button
              variant="outline"
              size="sm"
              onClick={() => onEdit(policy)}
              data-testid={`alert-policy-${policy.id}-edit`}
            >
              <Pencil className="w-3.5 h-3.5" />
              <span className="sr-only">Edit {policy.name}</span>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onToggle(policy)}
              data-testid={`alert-policy-${policy.id}-toggle`}
            >
              {policy.enabled ? (
                <Pause className="w-3.5 h-3.5" />
              ) : (
                <Play className="w-3.5 h-3.5" />
              )}
              <span className="sr-only">
                {policy.enabled ? "Pause" : "Activate"} {policy.name}
              </span>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onDelete(policy)}
              data-testid={`alert-policy-${policy.id}-delete`}
            >
              <Trash2 className="w-3.5 h-3.5" />
              <span className="sr-only">Delete {policy.name}</span>
            </Button>
          </div>
        )}
      </div>

      <dl className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4">
        <div>
          <dt className="fw-kicker">Triggers at</dt>
          <dd className="text-sm text-[var(--text-primary)] mt-0.5">
            {PRIORITY_LABELS[policy.minimum_investigation_priority] ??
              policy.minimum_investigation_priority}{" "}
            priority
          </dd>
        </div>
        <div>
          <dt className="fw-kicker">Monitored areas</dt>
          <dd
            className="text-sm text-[var(--text-primary)] mt-0.5"
            data-testid={`alert-policy-${policy.id}-areas`}
          >
            {areaNames.length ? areaNames.join(", ") : "All monitored areas"}
          </dd>
        </div>
        <div>
          <dt className="fw-kicker">Delivers to</dt>
          <dd
            className="text-sm text-[var(--text-primary)] mt-0.5"
            data-testid={`alert-policy-${policy.id}-channels`}
          >
            {channelNames.length ? channelNames.join(", ") : "No channel selected"}
          </dd>
        </div>
        <div>
          <dt className="fw-kicker">Cooldown</dt>
          <dd className="text-sm text-[var(--text-primary)] mt-0.5">
            {formatCooldown(policy.cooldown_minutes)}
          </dd>
        </div>
      </dl>
    </li>
  );
}

/**
 * Organization-scoped alert policy list. Members without management permission
 * see the same configuration without controls.
 */
export default function AlertPolicyList({
  policies = [],
  options,
  monitoredAreas = [],
  channels = [],
  canManage = false,
  alertDeliveryAvailable = true,
  loading = false,
  onCreate,
  onEdit,
  onToggle,
  onDelete,
}) {
  const areasById = Object.fromEntries(monitoredAreas.map((a) => [a.id, a.name]));
  const channelsById = Object.fromEntries(
    channels.map((c) => [c.id, `${c.name} (${channelTypeLabel(c.channel_type)})`])
  );

  return (
    <SurfaceCard className="p-5" testId="alert-policy-list">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <h3 className="text-base font-bold text-[var(--text-primary)]">Alert policies</h3>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Rules that decide when your organization is notified about monitored forests.
          </p>
        </div>
        {canManage && alertDeliveryAvailable && (
          <Button onClick={onCreate} data-testid="alert-policy-create-btn">
            <Plus className="w-4 h-4" />
            New policy
          </Button>
        )}
      </div>

      {!alertDeliveryAvailable && (
        <div
          className="mb-4 p-3 rounded-md border border-[var(--surface-inset)] bg-[var(--surface-subtle)]"
          data-testid="alert-delivery-unavailable"
        >
          <div className="flex items-center gap-2">
            <span className="fw-kicker">Alert delivery</span>
            <StatusBadge variant="not-enabled" label="Not available" />
          </div>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Alert delivery is not part of this organization&apos;s current plan. Existing
            configuration stays visible and inactive.
          </p>
          <UpgradePrompt
            message="Alert delivery is not included in your current plan."
            actionLabel="Upgrade to enable customer alerts"
            testId="alert-delivery-upgrade"
            compact
          />
        </div>
      )}

      {!canManage && (
        <p className="text-xs text-[var(--text-muted)] mb-4" data-testid="alert-policy-read-only">
          You have view-only access to alert configuration. An organization owner or admin can
          make changes.
        </p>
      )}

      {loading ? (
        <div className="h-20 rounded-md bg-[var(--surface-inset)] animate-pulse" data-testid="alert-policy-loading" />
      ) : policies.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]" data-testid="alert-policy-empty">
          No alert policies yet. Create one to be notified about disturbances inside your
          monitored forests.
        </p>
      ) : (
        <ul className="space-y-3">
          {policies.map((policy) => (
            <PolicyRow
              key={policy.id}
              policy={policy}
              options={options}
              areasById={areasById}
              channelsById={channelsById}
              canManage={canManage}
              onEdit={onEdit}
              onToggle={onToggle}
              onDelete={onDelete}
            />
          ))}
        </ul>
      )}
    </SurfaceCard>
  );
}
