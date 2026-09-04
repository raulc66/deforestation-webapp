import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  fetchOrganizations,
  setOrganizationHeader,
} from "@/api/organizations";
import { useAuth } from "@/context/AuthContext";
import { isDemoUser } from "@/lib/demo";
import {
  SELECTED_ORG_STORAGE_KEY,
  isUnreachableApiError,
} from "@/lib/sessionState";

const OrganizationContext = createContext(null);

function identityKeyFor(user) {
  if (user === null) return "hydrating";
  if (user && typeof user === "object") return `user:${user.id}`;
  return "anonymous";
}

export function OrganizationProvider({ children }) {
  const { user } = useAuth();
  const isAuthenticated = user && typeof user === "object";
  const identityKey = identityKeyFor(user);
  const demoSession = isDemoUser(user);
  const [organizations, setOrganizations] = useState([]);
  const [selectedOrgId, setSelectedOrgIdState] = useState(null);
  const [organizationVersion, setOrganizationVersion] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [prevIdentityKey, setPrevIdentityKey] = useState(identityKey);

  if (prevIdentityKey !== identityKey) {
    setPrevIdentityKey(identityKey);
    const leftUser = prevIdentityKey.startsWith("user:");
    const enteredUser = identityKey.startsWith("user:");
    const crossedIdentities = leftUser && enteredUser && prevIdentityKey !== identityKey;
    if (identityKey === "anonymous" || crossedIdentities || demoSession) {
      try {
        sessionStorage.removeItem(SELECTED_ORG_STORAGE_KEY);
      } catch {
        // ignore
      }
    }
    if (identityKey !== "hydrating") {
      setOrganizations([]);
      setSelectedOrgIdState(null);
      setOrganizationHeader(null);
    }
  }

  const loadOrganizations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let data;
      try {
        data = await fetchOrganizations();
      } catch (err) {
        if (!isUnreachableApiError(err)) throw err;
        data = await fetchOrganizations();
      }
      const items = data?.items ?? [];
      setOrganizations(items);
      const stored = sessionStorage.getItem(SELECTED_ORG_STORAGE_KEY);
      const validStored = items.find((o) => o.id === stored);
      const nextId = validStored?.id ?? items[0]?.id ?? null;
      setSelectedOrgIdState(nextId);
      setOrganizationHeader(nextId);
      if (nextId) sessionStorage.setItem(SELECTED_ORG_STORAGE_KEY, nextId);
      else {
        try {
          sessionStorage.removeItem(SELECTED_ORG_STORAGE_KEY);
        } catch {
          // ignore
        }
      }
    } catch (err) {
      setError(err.message || "Failed to load organizations");
      setOrganizations([]);
      setSelectedOrgIdState(null);
      setOrganizationHeader(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (identityKey === "hydrating") {
      return;
    }
    if (!isAuthenticated) {
      setOrganizations([]);
      setSelectedOrgIdState(null);
      setOrganizationHeader(null);
      try {
        sessionStorage.removeItem(SELECTED_ORG_STORAGE_KEY);
      } catch {
        // ignore
      }
      setLoading(false);
      setError(null);
      return;
    }
    if (demoSession) {
      try {
        sessionStorage.removeItem(SELECTED_ORG_STORAGE_KEY);
      } catch {
        // ignore
      }
    }
    loadOrganizations();
  }, [demoSession, identityKey, isAuthenticated, loadOrganizations]);

  const setSelectedOrgId = useCallback(
    (orgId) => {
      const match = organizations.find((o) => o.id === orgId);
      if (!match) return;
      setSelectedOrgIdState(orgId);
      setOrganizationHeader(orgId);
      sessionStorage.setItem(SELECTED_ORG_STORAGE_KEY, orgId);
      setOrganizationVersion((v) => v + 1);
    },
    [organizations]
  );

  const currentOrganization = useMemo(
    () => organizations.find((o) => o.id === selectedOrgId) ?? null,
    [organizations, selectedOrgId]
  );

  const orgReady = Boolean(selectedOrgId) && !loading;

  const value = useMemo(
    () => ({
      organizations,
      currentOrganization,
      selectedOrgId,
      organizationVersion,
      setSelectedOrgId,
      loading,
      error,
      orgReady,
      reload: loadOrganizations,
    }),
    [
      organizations,
      currentOrganization,
      selectedOrgId,
      organizationVersion,
      setSelectedOrgId,
      loading,
      error,
      orgReady,
      loadOrganizations,
    ]
  );

  return (
    <OrganizationContext.Provider value={value}>
      {children}
    </OrganizationContext.Provider>
  );
}

export function useOrganization() {
  const ctx = useContext(OrganizationContext);
  if (!ctx) {
    throw new Error("useOrganization must be used inside OrganizationProvider");
  }
  return ctx;
}
