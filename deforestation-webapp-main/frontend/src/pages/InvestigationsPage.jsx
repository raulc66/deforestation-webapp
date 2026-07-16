import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams, Link } from "react-router-dom";
import {
  ClipboardList,
  Plus,
  Search,
  RefreshCw,
  ArrowLeft,
  X,
} from "lucide-react";
import AppLayout from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import {
  fetchInvestigations,
  fetchInvestigation,
  createInvestigation,
  closeInvestigation,
  archiveInvestigation,
} from "@/api/investigations";
import { formatApiErrorDetail } from "@/lib/api";
import InvestigationTimeline, {
  StatusBadge,
  PriorityBadge,
  fmtDate,
} from "@/components/investigations/InvestigationTimeline";

const STATUS_FILTERS = [
  { value: "", label: "All statuses" },
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In Progress" },
  { value: "waiting", label: "Waiting" },
  { value: "resolved", label: "Resolved" },
  { value: "closed", label: "Closed" },
];

const PRIORITY_FILTERS = [
  { value: "", label: "All priorities" },
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "critical", label: "Critical" },
];

function CreateModal({ open, onClose, onCreated, initialIntelEvent }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("medium");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (open && initialIntelEvent) {
      setTitle(`Investigation: ${initialIntelEvent.region} anomaly`);
      setDescription(
        `Follow-up for ${initialIntelEvent.event_type} in ${initialIntelEvent.region}. ` +
          `Severity: ${initialIntelEvent.severity}. Priority score: ${initialIntelEvent.priority_score ?? 0}.`
      );
      const sev = initialIntelEvent.severity;
      setPriority(sev === "critical" ? "critical" : sev === "high" ? "high" : "medium");
    }
  }, [open, initialIntelEvent]);

  if (!open) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const body = { title, description, priority };
      if (initialIntelEvent?.id) {
        body.intelligence_event_id = initialIntelEvent.id;
      }
      const created = await createInvestigation(body);
      onCreated(created);
      onClose();
    } catch (err) {
      setError(formatApiErrorDetail(err?.response?.data?.detail) || err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" data-testid="create-investigation-modal">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">Create Investigation</h3>
          <button type="button" onClick={onClose} aria-label="Close">
            <X className="w-5 h-5 text-[#7b827b]" />
          </button>
        </div>
        {error && (
          <p className="text-sm text-[#9b2226] mb-3" data-testid="create-error">{error}</p>
        )}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-xs font-semibold text-[#7b827b] uppercase tracking-wider">Title</label>
            <input
              className="w-full mt-1 border border-[#eaece6] rounded-md px-3 py-2 text-sm"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              data-testid="create-title-input"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-[#7b827b] uppercase tracking-wider">Description</label>
            <textarea
              className="w-full mt-1 border border-[#eaece6] rounded-md px-3 py-2 text-sm min-h-[80px]"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              data-testid="create-description-input"
            />
          </div>
          <div>
            <label className="text-xs font-semibold text-[#7b827b] uppercase tracking-wider">Priority</label>
            <select
              className="w-full mt-1 border border-[#eaece6] rounded-md px-3 py-2 text-sm"
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              data-testid="create-priority-select"
            >
              {PRIORITY_FILTERS.filter((p) => p.value).map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </div>
          <div className="flex gap-2 justify-end">
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={submitting} data-testid="create-submit-btn">
              {submitting ? "Creating…" : "Create"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

function DetailPanel({ investigationId, onBack, onRefresh }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [closing, setClosing] = useState(false);
  const [resolution, setResolution] = useState("");

  const load = useCallback(async () => {
    if (!investigationId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchInvestigation(investigationId);
      setData(result);
    } catch (err) {
      setError(formatApiErrorDetail(err?.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  }, [investigationId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleClose = async () => {
    if (!resolution.trim()) return;
    setClosing(true);
    try {
      await closeInvestigation(investigationId, { resolution });
      await load();
      onRefresh?.();
    } catch (err) {
      setError(formatApiErrorDetail(err?.response?.data?.detail) || err.message);
    } finally {
      setClosing(false);
    }
  };

  const inv = data?.investigation;

  return (
    <div className="bg-white border border-[#eaece6] rounded-lg p-6" data-testid="investigation-detail">
      <button
        type="button"
        onClick={onBack}
        className="flex items-center gap-1 text-sm text-[#2d5a27] font-semibold mb-4 hover:underline"
        data-testid="detail-back-btn"
      >
        <ArrowLeft className="w-4 h-4" /> Back to list
      </button>

      {loading && <p className="text-[#7b827b]" data-testid="detail-loading">Loading…</p>}
      {error && <p className="text-[#9b2226]" data-testid="detail-error">{error}</p>}

      {!loading && inv && (
        <>
          <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
            <div>
              <h2 className="text-xl font-semibold text-[#1a1e1a]" data-testid="detail-title">
                {inv.title}
              </h2>
              <p className="text-sm text-[#7b827b] mt-1">{inv.region || "No region"}</p>
            </div>
            <div className="flex gap-2">
              <StatusBadge status={inv.status} />
              <PriorityBadge priority={inv.priority} />
            </div>
          </div>

          <p className="text-sm text-[#4a524a] mb-4">{inv.description || "—"}</p>

          <dl className="grid grid-cols-2 gap-3 text-sm mb-6">
            <div>
              <dt className="text-[#7b827b] text-xs uppercase tracking-wider">Assigned to</dt>
              <dd className="font-medium">{inv.assigned_to || "Unassigned"}</dd>
            </div>
            <div>
              <dt className="text-[#7b827b] text-xs uppercase tracking-wider">Organization</dt>
              <dd className="font-medium">{inv.organization || "—"}</dd>
            </div>
            <div>
              <dt className="text-[#7b827b] text-xs uppercase tracking-wider">Created</dt>
              <dd>{fmtDate(inv.created_at)}</dd>
            </div>
            <div>
              <dt className="text-[#7b827b] text-xs uppercase tracking-wider">Updated</dt>
              <dd>{fmtDate(inv.updated_at)}</dd>
            </div>
          </dl>

          {inv.status !== "closed" && (
            <div className="mb-6 p-4 bg-[#f4f5f2] rounded-md" data-testid="close-investigation-form">
              <label className="text-xs font-semibold text-[#7b827b] uppercase tracking-wider">
                Close investigation
              </label>
              <textarea
                className="w-full mt-1 border border-[#eaece6] rounded-md px-3 py-2 text-sm min-h-[60px]"
                placeholder="Resolution summary…"
                value={resolution}
                onChange={(e) => setResolution(e.target.value)}
                data-testid="close-resolution-input"
              />
              <Button
                className="mt-2"
                onClick={handleClose}
                disabled={closing || !resolution.trim()}
                data-testid="close-submit-btn"
              >
                {closing ? "Closing…" : "Close Investigation"}
              </Button>
            </div>
          )}

          {inv.resolution && (
            <div className="mb-4 p-3 border border-[#eaece6] rounded-md">
              <div className="text-xs uppercase tracking-wider text-[#7b827b] font-semibold">Resolution</div>
              <p className="text-sm mt-1">{inv.resolution}</p>
            </div>
          )}

          <h3 className="text-sm font-semibold mb-3">Timeline</h3>
          <InvestigationTimeline timeline={data.timeline} loading={false} />
        </>
      )}
    </div>
  );
}

export default function InvestigationsPage() {
  const { id: detailId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const [investigations, setInvestigations] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  const intelEventId = searchParams.get("intel_event_id");
  const intelRegion = searchParams.get("region");
  const initialIntelEvent = intelEventId
    ? {
        id: intelEventId,
        region: intelRegion || "Unknown",
        event_type: searchParams.get("event_type") || "anomaly",
        severity: searchParams.get("severity") || "medium",
        priority_score: parseFloat(searchParams.get("priority_score") || "0"),
      }
    : null;

  useEffect(() => {
    if (intelEventId) setShowCreate(true);
  }, [intelEventId]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (statusFilter) params.status = statusFilter;
      if (priorityFilter) params.priority = priorityFilter;
      if (search.trim()) params.search = search.trim();
      const data = await fetchInvestigations(params);
      setInvestigations(data.investigations ?? []);
      setTotal(data.total ?? 0);
    } catch (err) {
      setError(formatApiErrorDetail(err?.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, priorityFilter, search]);

  useEffect(() => {
    if (!detailId) load();
  }, [load, detailId]);

  const handleCreated = (created) => {
    setSearchParams({});
    load();
    if (created?.id) navigate(`/investigations/${created.id}`);
  };

  if (detailId) {
    return (
      <AppLayout>
        <div className="p-6 md:p-8 max-w-4xl">
          <DetailPanel
            investigationId={detailId}
            onBack={() => navigate("/investigations")}
            onRefresh={load}
          />
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="p-6 md:p-8" data-testid="investigations-page">
        <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
          <div>
            <div className="label-eyebrow flex items-center gap-1.5">
              <ClipboardList className="w-3 h-3" strokeWidth={2} />
              Operations
            </div>
            <h1 className="text-2xl font-semibold tracking-tight mt-1">Investigations</h1>
            <p className="text-sm text-[#7b827b] mt-1">
              Operational follow-up for intelligence events
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={load} data-testid="refresh-btn">
              <RefreshCw className="w-4 h-4 mr-1" /> Refresh
            </Button>
            <Button onClick={() => setShowCreate(true)} data-testid="create-investigation-btn">
              <Plus className="w-4 h-4 mr-1" /> New Investigation
            </Button>
          </div>
        </div>

        {error && (
          <div className="mb-4 text-sm text-[#9b2226]" data-testid="list-error">{error}</div>
        )}

        <div className="flex flex-wrap gap-3 mb-4">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#7b827b]" />
            <input
              className="w-full pl-9 pr-3 py-2 border border-[#eaece6] rounded-md text-sm"
              placeholder="Search investigations…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && load()}
              data-testid="search-input"
            />
          </div>
          <select
            className="border border-[#eaece6] rounded-md px-3 py-2 text-sm"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            data-testid="status-filter"
          >
            {STATUS_FILTERS.map((f) => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
          <select
            className="border border-[#eaece6] rounded-md px-3 py-2 text-sm"
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            data-testid="priority-filter"
          >
            {PRIORITY_FILTERS.map((f) => (
              <option key={f.value} value={f.value}>{f.label}</option>
            ))}
          </select>
          <Button variant="outline" onClick={load} data-testid="apply-filters-btn">Apply</Button>
        </div>

        <div className="bg-white border border-[#eaece6] rounded-lg overflow-hidden">
          <table className="w-full text-sm" data-testid="investigations-table">
            <thead className="bg-[#f4f5f2] text-[#7b827b]">
              <tr>
                <th className="text-left font-semibold px-5 py-3">Title</th>
                <th className="text-left font-semibold px-5 py-3 hidden sm:table-cell">Region</th>
                <th className="text-left font-semibold px-5 py-3">Status</th>
                <th className="text-left font-semibold px-5 py-3">Priority</th>
                <th className="text-right font-semibold px-5 py-3 hidden md:table-cell">Updated</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr data-testid="investigations-loading">
                  <td colSpan={5} className="px-5 py-6 text-center text-[#7b827b]">Loading…</td>
                </tr>
              )}
              {!loading && investigations.length === 0 && (
                <tr data-testid="investigations-empty">
                  <td colSpan={5} className="px-5 py-6 text-center text-[#7b827b]">
                    No investigations found.
                  </td>
                </tr>
              )}
              {!loading &&
                investigations.map((inv) => (
                  <tr
                    key={inv.id}
                    className="border-t border-[#eaece6] hover:bg-[#f4f5f2]/60 cursor-pointer"
                    data-testid={`investigation-row-${inv.id}`}
                    onClick={() => navigate(`/investigations/${inv.id}`)}
                  >
                    <td className="px-5 py-3 font-medium text-[#1a1e1a]">
                      <Link to={`/investigations/${inv.id}`} className="hover:underline">
                        {inv.title}
                      </Link>
                    </td>
                    <td className="px-5 py-3 hidden sm:table-cell text-[#4a524a]">
                      {inv.region || "—"}
                    </td>
                    <td className="px-5 py-3"><StatusBadge status={inv.status} /></td>
                    <td className="px-5 py-3"><PriorityBadge priority={inv.priority} /></td>
                    <td className="px-5 py-3 text-right hidden md:table-cell text-[#7b827b] text-xs">
                      {fmtDate(inv.updated_at)}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>

        <p className="text-xs text-[#7b827b] mt-3" data-testid="investigations-total">
          {total} investigation{total !== 1 ? "s" : ""}
        </p>
      </div>

      <CreateModal
        open={showCreate}
        onClose={() => {
          setShowCreate(false);
          setSearchParams({});
        }}
        onCreated={handleCreated}
        initialIntelEvent={initialIntelEvent}
      />
    </AppLayout>
  );
}
