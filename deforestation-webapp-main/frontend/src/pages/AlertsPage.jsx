import { useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { BellRing } from "lucide-react";
import AppLayout from "@/components/layout/AppLayout";
import SurfaceCard from "@/components/product/SurfaceCard";
import StatusBadge from "@/components/product/StatusBadge";
import AlertPolicyList from "@/components/alerts/AlertPolicyList";
import AlertPolicyForm from "@/components/alerts/AlertPolicyForm";
import NotificationChannelList from "@/components/alerts/NotificationChannelList";
import NotificationChannelForm from "@/components/alerts/NotificationChannelForm";
import AlertDeliveryHistory from "@/components/alerts/AlertDeliveryHistory";
import { useOrganization } from "@/context/OrganizationContext";
import { useDemo } from "@/context/DemoContext";
import { useTrial } from "@/context/TrialContext";
import TrialConversionCta from "@/components/trial/TrialConversionCta";
import { fetchMonitoringAreas } from "@/api/monitoringAreas";
import {
  createAlertPolicy,
  createNotificationChannel,
  deleteAlertPolicy,
  deleteNotificationChannel,
  fetchAlertDeliveries,
  fetchAlertOptions,
  fetchAlertPolicies,
  fetchNotificationChannels,
  setAlertPolicyActive,
  setNotificationChannelActive,
  updateAlertPolicy,
  updateNotificationChannel,
} from "@/api/customerAlerts";

const TABS = [
  { id: "policies", label: "Alert policies" },
  { id: "channels", label: "Notification channels" },
  { id: "history", label: "Alert history" },
];

function errorMessage(err, fallback) {
  return err?.response?.data?.detail || err?.message || fallback;
}

/**
 * Organization-scoped alert configuration and history.
 *
 * All data is keyed on the active organization, and every surface is cleared
 * before a reload so no configuration from a previously selected organization
 * can stay on screen.
 */
export default function AlertsPage() {
  const { currentOrganization, selectedOrgId, organizationVersion } = useOrganization();
  const { isDemo } = useDemo();
  const trial = useTrial();

  const [activeTab, setActiveTab] = useState("policies");
  const [loading, setLoading] = useState(true);
  const [options, setOptions] = useState(null);
  const [policies, setPolicies] = useState([]);
  const [channels, setChannels] = useState([]);
  const [deliveries, setDeliveries] = useState([]);
  const [monitoredAreas, setMonitoredAreas] = useState([]);
  const [canManage, setCanManage] = useState(false);
  const [alertDeliveryAvailable, setAlertDeliveryAvailable] = useState(true);
  const [historyFilter, setHistoryFilter] = useState("");

  const [editingPolicy, setEditingPolicy] = useState(null);
  const [editingChannel, setEditingChannel] = useState(null);
  const [formError, setFormError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const resetSurfaces = useCallback(() => {
    setPolicies([]);
    setChannels([]);
    setDeliveries([]);
    setMonitoredAreas([]);
    setEditingPolicy(null);
    setEditingChannel(null);
    setFormError(null);
  }, []);

  const load = useCallback(
    async (lifecycle = "") => {
      setLoading(true);
      try {
        const [optionsData, policyData, channelData, deliveryData, areaData] =
          await Promise.all([
            fetchAlertOptions(),
            fetchAlertPolicies(),
            fetchNotificationChannels(),
            fetchAlertDeliveries(lifecycle ? { lifecycle } : {}),
            fetchMonitoringAreas(),
          ]);
        setOptions(optionsData);
        setPolicies(policyData?.items ?? []);
        setChannels(channelData?.items ?? []);
        setDeliveries(deliveryData?.items ?? []);
        setMonitoredAreas(areaData?.items ?? []);
        setCanManage(Boolean(policyData?.can_manage));
        setAlertDeliveryAvailable(policyData?.alert_delivery_available !== false);
      } catch (err) {
        resetSurfaces();
        toast.error(errorMessage(err, "Failed to load alert configuration"));
      } finally {
        setLoading(false);
      }
    },
    [resetSurfaces]
  );

  useEffect(() => {
    if (!selectedOrgId) return;
    resetSurfaces();
    setHistoryFilter("");
    load("");
  }, [selectedOrgId, organizationVersion, load, resetSurfaces]);

  const reloadHistory = useCallback(async (lifecycle) => {
    try {
      const data = await fetchAlertDeliveries(lifecycle ? { lifecycle } : {});
      setDeliveries(data?.items ?? []);
    } catch (err) {
      toast.error(errorMessage(err, "Failed to load alert history"));
    }
  }, []);

  const handleFilterChange = useCallback(
    (lifecycle) => {
      setHistoryFilter(lifecycle);
      reloadHistory(lifecycle);
    },
    [reloadHistory]
  );

  const submitPolicy = async (payload) => {
    setSubmitting(true);
    setFormError(null);
    try {
      if (editingPolicy?.id) {
        await updateAlertPolicy(editingPolicy.id, payload);
        toast.success("Alert policy updated");
      } else {
        await createAlertPolicy(payload);
        toast.success("Alert policy created");
      }
      setEditingPolicy(null);
      await load(historyFilter);
    } catch (err) {
      setFormError(errorMessage(err, "Could not save the alert policy"));
    } finally {
      setSubmitting(false);
    }
  };

  const submitChannel = async (payload) => {
    setSubmitting(true);
    setFormError(null);
    try {
      if (editingChannel?.id) {
        await updateNotificationChannel(editingChannel.id, payload);
        toast.success("Notification channel updated");
      } else {
        await createNotificationChannel(payload);
        toast.success("Notification channel created");
      }
      setEditingChannel(null);
      await load(historyFilter);
    } catch (err) {
      setFormError(errorMessage(err, "Could not save the notification channel"));
    } finally {
      setSubmitting(false);
    }
  };

  const togglePolicy = async (policy) => {
    try {
      await setAlertPolicyActive(policy.id, !policy.enabled);
      await load(historyFilter);
    } catch (err) {
      toast.error(errorMessage(err, "Could not change the policy status"));
    }
  };

  const removePolicy = async (policy) => {
    try {
      await deleteAlertPolicy(policy.id);
      toast.success("Alert policy deleted");
      await load(historyFilter);
    } catch (err) {
      toast.error(errorMessage(err, "Could not delete the policy"));
    }
  };

  const toggleChannel = async (channel) => {
    try {
      await setNotificationChannelActive(channel.id, !channel.enabled);
      await load(historyFilter);
    } catch (err) {
      toast.error(errorMessage(err, "Could not change the channel status"));
    }
  };

  const removeChannel = async (channel) => {
    try {
      await deleteNotificationChannel(channel.id);
      toast.success("Notification channel deleted");
      await load(historyFilter);
    } catch (err) {
      toast.error(errorMessage(err, "Could not delete the channel"));
    }
  };

  const activeAreas = useMemo(
    () => monitoredAreas.filter((area) => area.enabled !== false),
    [monitoredAreas]
  );

  return (
    <AppLayout>
      <div className="p-6 md:p-8 max-w-6xl mx-auto space-y-6">
        <SurfaceCard variant="emphasis" className="p-5" testId="alerts-page-header">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="fw-kicker mb-1">Alerts</div>
              <h1
                className="text-xl font-bold tracking-tight text-[var(--text-primary)]"
                data-testid="alerts-page-org-name"
              >
                {currentOrganization?.name ?? "Organization"}
              </h1>
              <p className="text-sm text-[var(--text-muted)] mt-1">
                {isDemo
                  ? "Demonstration policies and channels are shared and read-only. Simulate a notification from an investigation. No email is sent."
                  : "Configure who gets notified about disturbances in your monitored forests, and review what has already been delivered."}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <BellRing className="w-4 h-4 text-[var(--text-muted)]" strokeWidth={1.7} />
              <StatusBadge
                variant={alertDeliveryAvailable ? "enabled" : "not-enabled"}
                label={alertDeliveryAvailable ? "Alert delivery available" : "Alert delivery not available"}
                testId="alerts-page-availability"
              />
            </div>
          </div>

          <nav className="flex flex-wrap gap-1.5 mt-5" data-testid="alerts-page-tabs">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                aria-pressed={activeTab === tab.id}
                data-testid={`alerts-tab-${tab.id}`}
                onClick={() => setActiveTab(tab.id)}
                className={`rounded-md border px-3 py-1.5 text-xs transition-colors ${
                  activeTab === tab.id
                    ? "border-[var(--accent)] bg-[var(--surface-subtle)] font-semibold"
                    : "border-[var(--surface-inset)] text-[var(--text-muted)]"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </SurfaceCard>

        {trial.isTrial && trial.status?.alert_delivery_mode === "account_email" && (
          <p className="text-xs text-[var(--text-muted)]" data-testid="trial-alert-destination">
            Trial delivery is limited to your account email. Webhooks are not available on the trial.
          </p>
        )}
        {trial.isTrial && policies.length > 0 && <TrialConversionCta moment="alert" />}
        {trial.isExpired && <TrialConversionCta moment="expired" />}

        {activeTab === "policies" && (
          <>
            {editingPolicy && (
              <AlertPolicyForm
                policy={editingPolicy.id ? editingPolicy : null}
                options={options}
                monitoredAreas={activeAreas}
                channels={channels}
                submitting={submitting}
                error={formError}
                onSubmit={submitPolicy}
                onCancel={() => {
                  setEditingPolicy(null);
                  setFormError(null);
                }}
              />
            )}
            <AlertPolicyList
              policies={policies}
              options={options}
              monitoredAreas={activeAreas}
              channels={channels}
              canManage={canManage && !isDemo}
              alertDeliveryAvailable={alertDeliveryAvailable}
              loading={loading}
              onCreate={() => {
                setFormError(null);
                setEditingPolicy({});
              }}
              onEdit={(policy) => {
                setFormError(null);
                setEditingPolicy(policy);
              }}
              onToggle={togglePolicy}
              onDelete={removePolicy}
            />
          </>
        )}

        {activeTab === "channels" && (
          <>
            {editingChannel && (
              <NotificationChannelForm
                channel={editingChannel.id ? editingChannel : null}
                submitting={submitting}
                error={formError}
                onSubmit={submitChannel}
                onCancel={() => {
                  setEditingChannel(null);
                  setFormError(null);
                }}
              />
            )}
            <NotificationChannelList
              channels={channels}
              canManage={canManage && !isDemo}
              alertDeliveryAvailable={alertDeliveryAvailable}
              loading={loading}
              onCreate={() => {
                setFormError(null);
                setEditingChannel({});
              }}
              onEdit={(channel) => {
                setFormError(null);
                setEditingChannel(channel);
              }}
              onToggle={toggleChannel}
              onDelete={removeChannel}
            />
          </>
        )}

        {activeTab === "history" && (
          <AlertDeliveryHistory
            deliveries={deliveries}
            loading={loading}
            activeFilter={historyFilter}
            onFilterChange={handleFilterChange}
          />
        )}
      </div>
    </AppLayout>
  );
}
