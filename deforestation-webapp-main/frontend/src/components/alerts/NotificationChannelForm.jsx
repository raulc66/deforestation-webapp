import { useState } from "react";
import { Button } from "@/components/ui/button";
import SurfaceCard from "@/components/product/SurfaceCard";
import { channelTypeLabel } from "@/design/semanticStates";

const inputClass =
  "w-full rounded-md border border-[var(--surface-inset)] bg-white px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]";

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

/**
 * Create / edit a notification channel.
 *
 * Webhook secrets are write-only: an existing secret is never sent to the
 * browser, and leaving the field blank on edit keeps the stored one.
 */
export default function NotificationChannelForm({
  channel,
  onSubmit,
  onCancel,
  submitting = false,
  error = null,
}) {
  const isEditing = Boolean(channel?.id);
  const [channelType, setChannelType] = useState(channel?.channel_type ?? "email");
  const [name, setName] = useState(channel?.name ?? "");
  const [enabled, setEnabled] = useState(channel?.enabled ?? true);
  const [recipients, setRecipients] = useState(
    (channel?.config?.recipients ?? []).join(", ")
  );
  const [url, setUrl] = useState(channel?.config?.url ?? "");
  const [secret, setSecret] = useState("");

  const secretAlreadyStored = Boolean(channel?.config?.secret_configured);

  const handleSubmit = (event) => {
    event.preventDefault();
    const config =
      channelType === "email"
        ? {
            recipients: recipients
              .split(",")
              .map((value) => value.trim())
              .filter(Boolean),
          }
        : { url: url.trim(), ...(secret.trim() ? { secret_token: secret.trim() } : {}) };

    onSubmit(
      isEditing
        ? { name, enabled, config }
        : { channel_type: channelType, name, enabled, config }
    );
  };

  return (
    <SurfaceCard variant="inset" className="p-5" testId="notification-channel-form">
      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <h3 className="text-base font-bold text-[var(--text-primary)]">
            {isEditing ? `Edit ${channelTypeLabel(channelType)}` : "New notification channel"}
          </h3>
          <p className="text-sm text-[var(--text-muted)] mt-1">
            Where alerts for this organization are delivered.
          </p>
        </div>

        {error && (
          <p className="text-sm text-[var(--signal-strong)]" data-testid="channel-form-error">
            {error}
          </p>
        )}

        {!isEditing && (
          <Field label="Channel type">
            <div className="flex gap-2" data-testid="channel-type-options">
              {["email", "webhook"].map((value) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={channelType === value}
                  data-testid={`channel-type-${value}`}
                  onClick={() => setChannelType(value)}
                  className={`rounded-md border px-3 py-1.5 text-xs transition-colors ${
                    channelType === value
                      ? "border-[var(--accent)] bg-[var(--surface-subtle)] font-semibold"
                      : "border-[var(--surface-inset)] text-[var(--text-muted)]"
                  }`}
                >
                  {channelTypeLabel(value)}
                </button>
              ))}
            </div>
          </Field>
        )}

        <Field label="Channel name" htmlFor="channel-name">
          <input
            id="channel-name"
            className={inputClass}
            data-testid="channel-name-input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={channelType === "email" ? "Field operations inbox" : "Dispatch webhook"}
            required
          />
        </Field>

        {channelType === "email" ? (
          <Field
            label="Recipients"
            htmlFor="channel-recipients"
            hint="Comma-separated email addresses."
          >
            <input
              id="channel-recipients"
              className={inputClass}
              data-testid="channel-recipients-input"
              value={recipients}
              onChange={(e) => setRecipients(e.target.value)}
              placeholder="operations@example.com, ranger@example.com"
            />
          </Field>
        ) : (
          <>
            <Field
              label="Endpoint URL"
              htmlFor="channel-url"
              hint="Must be an HTTPS endpoint that accepts JSON."
            >
              <input
                id="channel-url"
                className={inputClass}
                data-testid="channel-url-input"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/forestwatch"
              />
            </Field>
            <Field
              label="Signing secret"
              htmlFor="channel-secret"
              hint={
                secretAlreadyStored
                  ? "A secret is stored. Enter a new value to replace it, or leave blank to keep it."
                  : "Optional. Used to sign each delivery so you can verify it came from ForestWatch."
              }
            >
              <input
                id="channel-secret"
                type="password"
                autoComplete="new-password"
                className={inputClass}
                data-testid="channel-secret-input"
                value={secret}
                onChange={(e) => setSecret(e.target.value)}
                placeholder={secretAlreadyStored ? "Secret stored — enter to replace" : ""}
              />
            </Field>
          </>
        )}

        <Field label="Status">
          <label className="flex items-center gap-2 text-sm text-[var(--text-primary)]">
            <input
              type="checkbox"
              data-testid="channel-enabled-input"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
            />
            Active — deliver alerts through this channel
          </label>
        </Field>

        <div className="flex items-center gap-2 pt-1">
          <Button type="submit" disabled={submitting} data-testid="channel-submit-btn">
            {isEditing ? "Save channel" : "Create channel"}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={onCancel}
            data-testid="channel-cancel-btn"
          >
            Cancel
          </Button>
        </div>
      </form>
    </SurfaceCard>
  );
}
