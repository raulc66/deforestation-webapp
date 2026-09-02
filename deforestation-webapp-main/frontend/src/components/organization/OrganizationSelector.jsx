import { ChevronDown, Building2 } from "lucide-react";
import { useOrganization } from "@/context/OrganizationContext";

/**
 * Persistent organization identity — uses backend organization list only.
 */
export default function OrganizationSelector({ compact = false }) {
  const {
    organizations,
    currentOrganization,
    selectedOrgId,
    setSelectedOrgId,
    loading,
  } = useOrganization();

  if (loading && !currentOrganization) {
    return (
      <div
        className="animate-pulse h-9 bg-[var(--surface-inset)] rounded-md"
        data-testid="organization-selector-loading"
      />
    );
  }

  if (!currentOrganization) return null;

  const multiOrg = organizations.length > 1;

  return (
    <div
      className={compact ? "min-w-0" : "px-6 py-4 border-b border-[var(--surface-inset)]"}
      data-testid="organization-selector"
    >
      {!compact && (
        <div className="fw-kicker mb-2 flex items-center gap-1.5">
          <Building2 className="w-3 h-3" strokeWidth={2} />
          Organization
        </div>
      )}

      <div className="flex items-center gap-2 min-w-0">
        {multiOrg ? (
          <label className="flex-1 min-w-0">
            <span className="sr-only">Select organization</span>
            <div className="relative">
              <select
                value={selectedOrgId ?? ""}
                onChange={(e) => setSelectedOrgId(e.target.value)}
                className="w-full appearance-none bg-[var(--surface-subtle)] border border-[var(--surface-inset)] rounded-md pl-3 pr-8 py-2 text-sm font-semibold text-[var(--text-primary)] truncate focus:outline-none focus:ring-2 focus:ring-[var(--accent)]/30"
                data-testid="organization-select"
              >
                {organizations.map((org) => (
                  <option key={org.id} value={org.id}>
                    {org.name}
                  </option>
                ))}
              </select>
              <ChevronDown
                className="w-4 h-4 absolute right-2 top-1/2 -translate-y-1/2 text-[var(--text-muted)] pointer-events-none"
                aria-hidden
              />
            </div>
          </label>
        ) : (
          <div
            className="text-sm font-semibold text-[var(--text-primary)] truncate"
            data-testid="organization-name"
          >
            {currentOrganization.name}
          </div>
        )}

        <span
          className="shrink-0 text-[10px] uppercase tracking-wider font-bold px-2 py-1 rounded bg-[var(--surface-inset)] text-[var(--text-secondary)] capitalize"
          data-testid="organization-role"
        >
          {currentOrganization.role}
        </span>
      </div>
    </div>
  );
}
