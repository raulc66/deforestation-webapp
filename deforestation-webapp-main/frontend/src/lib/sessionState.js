import { setOrganizationHeader } from "@/api/organizations";

export const SELECTED_ORG_STORAGE_KEY = "forestwatch.selectedOrganizationId";

export function clearClientWorkspaceState() {
  setOrganizationHeader(null);
  try {
    sessionStorage.removeItem(SELECTED_ORG_STORAGE_KEY);
  } catch {
    // Private mode or blocked storage must not block logout.
  }
}

export function isSignOutRequiredDemoError(err) {
  const status = err?.response?.status;
  const detail = err?.response?.data?.detail;
  if (status !== 403) return false;
  return typeof detail === "string" && /sign out before starting/i.test(detail);
}

export function isUnreachableApiError(err) {
  return Boolean(err) && !err.response && err.code !== "ERR_CANCELED";
}
