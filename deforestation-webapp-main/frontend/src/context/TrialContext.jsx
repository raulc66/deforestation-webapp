import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { fetchTrialStatus, startTrial as startTrialRequest } from "@/api/trial";
import { useAuth } from "@/context/AuthContext";
import { useOrganization } from "@/context/OrganizationContext";
import { isDemoOrganization, isDemoUser } from "@/lib/demo";

const IDLE = {
  status: null,
  loading: false,
  isTrial: false,
  isExpired: false,
  startTrial: async () => null,
  reload: async () => {},
};

const TrialContext = createContext(null);

export function TrialProvider({ children }) {
  const { user } = useAuth();
  const {
    selectedOrgId,
    organizationVersion,
    currentOrganization,
    loading: orgLoading,
    reload: reloadOrgs,
  } = useOrganization();
  const isAuthenticated = user && typeof user === "object";
  const demo = isDemoUser(user);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  const reload = useCallback(async () => {
    if (
      !isAuthenticated ||
      demo ||
      !selectedOrgId ||
      orgLoading ||
      isDemoOrganization(currentOrganization)
    ) {
      setStatus(null);
      return null;
    }
    setLoading(true);
    try {
      const data = await fetchTrialStatus();
      setStatus(data);
      return data;
    } catch {
      setStatus(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, [currentOrganization, demo, isAuthenticated, orgLoading, selectedOrgId]);

  useEffect(() => {
    reload();
  }, [reload, organizationVersion]);

  const startTrial = useCallback(
    async (payload = {}) => {
      const data = await startTrialRequest(payload);
      setStatus(data);
      await reloadOrgs();
      return data;
    },
    [reloadOrgs]
  );

  const value = useMemo(
    () => ({
      status,
      loading,
      isTrial: status?.commercial_lifecycle === "trial",
      isExpired: status?.commercial_lifecycle === "trial_expired",
      startTrial,
      reload,
    }),
    [loading, reload, startTrial, status]
  );

  return <TrialContext.Provider value={value}>{children}</TrialContext.Provider>;
}

export function useTrial() {
  return useContext(TrialContext) ?? IDLE;
}
