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

const STORAGE_KEY = "forestwatch.selectedOrganizationId";

const OrganizationContext = createContext(null);

export function OrganizationProvider({ children }) {
  const { user } = useAuth();
  const isAuthenticated = user && typeof user === "object";
  const [organizations, setOrganizations] = useState([]);
  const [selectedOrgId, setSelectedOrgIdState] = useState(null);
  const [organizationVersion, setOrganizationVersion] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadOrganizations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchOrganizations();
      const items = data?.items ?? [];
      setOrganizations(items);
      const stored = sessionStorage.getItem(STORAGE_KEY);
      const validStored = items.find((o) => o.id === stored);
      const nextId = validStored?.id ?? items[0]?.id ?? null;
      setSelectedOrgIdState(nextId);
      setOrganizationHeader(nextId);
      if (nextId) sessionStorage.setItem(STORAGE_KEY, nextId);
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
    if (!isAuthenticated) {
      setOrganizations([]);
      setSelectedOrgIdState(null);
      setOrganizationHeader(null);
      return;
    }
    if (isDemoUser(user)) {
      try {
        sessionStorage.removeItem(STORAGE_KEY);
      } catch {
        // ignore
      }
    }
    loadOrganizations();
  }, [isAuthenticated, loadOrganizations, user]);

  const setSelectedOrgId = useCallback(
    (orgId) => {
      const match = organizations.find((o) => o.id === orgId);
      if (!match) return;
      setSelectedOrgIdState(orgId);
      setOrganizationHeader(orgId);
      sessionStorage.setItem(STORAGE_KEY, orgId);
      setOrganizationVersion((v) => v + 1);
    },
    [organizations]
  );

  const currentOrganization = useMemo(
    () => organizations.find((o) => o.id === selectedOrgId) ?? null,
    [organizations, selectedOrgId]
  );

  const value = useMemo(
    () => ({
      organizations,
      currentOrganization,
      selectedOrgId,
      organizationVersion,
      setSelectedOrgId,
      loading,
      error,
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
