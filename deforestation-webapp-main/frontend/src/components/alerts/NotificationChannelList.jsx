import { Pause, Pencil, Play, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import SurfaceCard from "@/components/product/SurfaceCard";
import StatusBadge from "@/components/product/StatusBadge";
import { activationLabel, channelTypeLabel } from "@/design/semanticStates";

function ChannelDestination({ channel }) {
  if (channel.channel_type === "email") {
    const recipients = channel.config?.recipients ?? [];
    return (
      <span data-testid={`channel-${channel.id}-destination`}>
        {recipients.length ? recipients.join(", ") : "No recipients configured"}
      </span>
    );
  }
  return (
    <span data-testid={`channel-${channel.id}-destination`}>
      {channel.config?.url || "No endpoint configured"}
    </span>
  );
}

export default function NotificationChannelList({
  channels = [],
  canManage = false,
  alertDeliveryAvailable = true,
  loading = false,
  onCreate,
  onEdit,
  onToggle,
  onDelete,
}) {
  return (
    <SurfaceCard className="p-5" testId="notification-channel-list">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div>
          <h3 className="text-base font-bold text-[var(--text-primary)]">
            Notification channels
          </h3>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Destinations your alert policies can deliver to.
          </p>
        </div>
        {canManage && alertDeliveryAvailable && (
          <Button onClick={onCreate} data-testid="channel-create-btn">
            <Plus className="w-4 h-4" />
            New channel
          </Button>
        )}
      </div>

      {!canManage && (
        <p className="text-xs text-[var(--text-muted)] mb-4" data-testid="channel-read-only">
          You have view-only access to notification channels.
        </p>
      )}

      {loading ? (
        <div
          className="h-20 rounded-md bg-[var(--surface-inset)] animate-pulse"
          data-testid="channel-loading"
        />
      ) : channels.length === 0 ? (
        <p className="text-sm text-[var(--text-muted)]" data-testid="channel-empty">
          No notification channels yet. Add an email or webhook destination so alert policies
          have somewhere to deliver.
        </p>
      ) : (
        <ul className="space-y-3">
          {channels.map((channel) => (
            <li
              key={channel.id}
              className="p-4 border border-[var(--surface-inset)] rounded-md"
              data-testid={`notification-channel-${channel.id}`}
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h4 className="text-sm font-semibold text-[var(--text-primary)] truncate">
                      {channel.name}
                    </h4>
                    <StatusBadge
                      variant={channel.enabled ? "enabled" : "disabled"}
                      label={activationLabel(channel.enabled)}
                      testId={`notification-channel-${channel.id}-status`}
                    />
                  </div>
                  <p className="text-xs text-[var(--text-muted)] mt-1">
                    {channelTypeLabel(channel.channel_type)}
                  </p>
                  <p className="text-sm text-[var(--text-primary)] mt-2 break-all">
                    <ChannelDestination channel={channel} />
                  </p>
                  {channel.channel_type === "webhook" && (
                    <p
                      className="text-xs text-[var(--text-muted)] mt-1"
                      data-testid={`notification-channel-${channel.id}-secret`}
                    >
                      {channel.config?.secret_configured
                        ? "Signing secret stored — hidden for security"
                        : "No signing secret configured"}
                    </p>
                  )}
                </div>

                {canManage && (
                  <div className="flex items-center gap-1.5">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onEdit(channel)}
                      data-testid={`notification-channel-${channel.id}-edit`}
                    >
                      <Pencil className="w-3.5 h-3.5" />
                      <span className="sr-only">Edit {channel.name}</span>
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onToggle(channel)}
                      data-testid={`notification-channel-${channel.id}-toggle`}
                    >
                      {channel.enabled ? (
                        <Pause className="w-3.5 h-3.5" />
                      ) : (
                        <Play className="w-3.5 h-3.5" />
                      )}
                      <span className="sr-only">
                        {channel.enabled ? "Pause" : "Activate"} {channel.name}
                      </span>
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onDelete(channel)}
                      data-testid={`notification-channel-${channel.id}-delete`}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      <span className="sr-only">Delete {channel.name}</span>
                    </Button>
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </SurfaceCard>
  );
}
