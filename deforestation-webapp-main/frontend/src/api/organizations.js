import { api } from "@/lib/api";

export const ORGANIZATION_ID_HEADER = "X-Organization-Id";

/**
 * @returns {Promise<{ items: Array<{ id: string, name: string, slug: string, role: string, status: string }> }>}
 */
export async function fetchOrganizations() {
  const { data } = await api.get("/organizations");
  return data;
}

export async function updateOrganization(organizationId, payload) {
  const { data } = await api.put(`/organizations/${organizationId}`, payload);
  return data;
}

export function setOrganizationHeader(organizationId) {
  if (organizationId) {
    api.defaults.headers.common[ORGANIZATION_ID_HEADER] = organizationId;
  } else {
    delete api.defaults.headers.common[ORGANIZATION_ID_HEADER];
  }
}
