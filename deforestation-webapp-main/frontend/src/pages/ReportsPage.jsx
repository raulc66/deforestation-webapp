import { useState, useEffect, useCallback, useRef } from "react";
import {
  FileText,
  Download,
  Trash2,
  Plus,
  RefreshCw,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  FileJson,
  FileSpreadsheet,
  Calendar,
} from "lucide-react";
import AppLayout from "@/components/layout/AppLayout";
import { Button } from "@/components/ui/button";
import {
  fetchReports,
  fetchReport,
  generateReport,
  deleteReport,
  getDownloadUrl,
} from "@/api/reports";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const REPORT_TYPES = [
  { value: "daily",    label: "Daily",    description: "Last 24 hours" },
  { value: "weekly",   label: "Weekly",   description: "Last 7 days" },
  { value: "monthly",  label: "Monthly",  description: "Last 30 days" },
  { value: "on_demand",label: "On-Demand",description: "Custom period" },
];

const REPORT_FORMATS = [
  { value: "pdf",  label: "PDF",  Icon: FileText,       description: "Print-ready report" },
  { value: "csv",  label: "CSV",  Icon: FileSpreadsheet, description: "Machine-readable data" },
  { value: "json", label: "JSON", Icon: FileJson,        description: "API integration" },
];

const STATUS_CONFIG = {
  pending:    { label: "Pending",    color: "text-yellow-700 bg-yellow-50 border-yellow-200", Icon: Clock },
  generating: { label: "Generating", color: "text-blue-700 bg-blue-50 border-blue-200",     Icon: Loader2 },
  complete:   { label: "Complete",   color: "text-green-700 bg-green-50 border-green-200",  Icon: CheckCircle },
  failed:     { label: "Failed",     color: "text-red-700 bg-red-50 border-red-200",        Icon: XCircle },
};

const FORMAT_ICONS = { pdf: FileText, csv: FileSpreadsheet, json: FileJson };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("en-GB", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

function fmtPeriod(start, end) {
  const s = start ? new Date(start).toLocaleDateString("en-GB", { day: "2-digit", month: "short" }) : "?";
  const e = end   ? new Date(end).toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }) : "?";
  return `${s} – ${e}`;
}

function fmtSize(bytes) {
  if (!bytes) return "—";
  if (bytes < 1024)       return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function fmtMs(ms) {
  if (!ms) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function isInProgress(status) {
  return status === "pending" || status === "generating";
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusBadge({ status }) {
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
  const { Icon } = cfg;
  const spinning = status === "generating";
  return (
    <span
      className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded-full border ${cfg.color}`}
    >
      <Icon className={`w-3 h-3 ${spinning ? "animate-spin" : ""}`} strokeWidth={2} />
      {cfg.label}
    </span>
  );
}

function FormatBadge({ format }) {
  const Icon = FORMAT_ICONS[format] || FileText;
  return (
    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#4a524a] bg-[#f4f5f2] px-2 py-0.5 rounded border border-[#eaece6]">
      <Icon className="w-3 h-3" strokeWidth={1.8} />
      {(format || "—").toUpperCase()}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Generate Report Modal
// ---------------------------------------------------------------------------

function GenerateModal({ onClose, onGenerate }) {
  const [type, setType] = useState("daily");
  const [format, setFormat] = useState("pdf");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await onGenerate(type, format);
      onClose();
    } catch (err) {
      setError(err?.response?.data?.detail || "Generation failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
        {/* Header */}
        <div className="bg-[#2d5a27] px-6 py-4">
          <h2 className="text-white font-bold text-lg">Generate Report</h2>
          <p className="text-[#b7d1b1] text-sm mt-0.5">
            Create a new intelligence report
          </p>
        </div>

        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Report Type */}
          <div>
            <label className="block text-sm font-semibold text-[#1a1e1a] mb-2">
              Report Type
            </label>
            <div className="grid grid-cols-2 gap-2">
              {REPORT_TYPES.map((rt) => (
                <button
                  key={rt.value}
                  type="button"
                  onClick={() => setType(rt.value)}
                  className={`text-left px-3 py-2.5 rounded-lg border text-sm transition-colors ${
                    type === rt.value
                      ? "border-[#2d5a27] bg-[#f4f5f2] text-[#2d5a27]"
                      : "border-[#eaece6] text-[#4a524a] hover:bg-[#f4f5f2]"
                  }`}
                >
                  <div className="font-semibold">{rt.label}</div>
                  <div className="text-[11px] text-[#7b827b]">{rt.description}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Format */}
          <div>
            <label className="block text-sm font-semibold text-[#1a1e1a] mb-2">
              Format
            </label>
            <div className="grid grid-cols-3 gap-2">
              {REPORT_FORMATS.map((fmt) => (
                <button
                  key={fmt.value}
                  type="button"
                  onClick={() => setFormat(fmt.value)}
                  className={`flex flex-col items-center py-3 px-2 rounded-lg border text-xs transition-colors ${
                    format === fmt.value
                      ? "border-[#2d5a27] bg-[#f4f5f2] text-[#2d5a27]"
                      : "border-[#eaece6] text-[#4a524a] hover:bg-[#f4f5f2]"
                  }`}
                >
                  <fmt.Icon className="w-5 h-5 mb-1" strokeWidth={1.6} />
                  <span className="font-semibold">{fmt.label}</span>
                  <span className="text-[10px] text-[#7b827b] text-center">{fmt.description}</span>
                </button>
              ))}
            </div>
          </div>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2 border border-red-200">
              {error}
            </div>
          )}

          <div className="flex gap-3 pt-1">
            <Button
              type="button"
              variant="outline"
              className="flex-1 border-[#eaece6]"
              onClick={onClose}
              disabled={loading}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={loading}
              className="flex-1 bg-[#2d5a27] hover:bg-[#3a7a34] text-white"
            >
              {loading ? (
                <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Submitting…</>
              ) : (
                <><Plus className="w-4 h-4 mr-2" /> Generate</>
              )}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Report Row
// ---------------------------------------------------------------------------

function ReportRow({ report, onDelete, onRefresh }) {
  const [deleting, setDeleting] = useState(false);
  const inProgress = isInProgress(report.status);

  const handleDelete = async () => {
    if (!window.confirm("Delete this report and its file?")) return;
    setDeleting(true);
    try {
      await deleteReport(report.id);
      onDelete(report.id);
    } catch {
      setDeleting(false);
    }
  };

  return (
    <tr className="border-b border-[#f4f5f2] hover:bg-[#fafafa] transition-colors">
      {/* Type */}
      <td className="px-4 py-3">
        <span className="font-semibold text-sm text-[#1a1e1a] capitalize">
          {report.type?.replace("_", " ")}
        </span>
      </td>

      {/* Format */}
      <td className="px-4 py-3">
        <FormatBadge format={report.format} />
      </td>

      {/* Status */}
      <td className="px-4 py-3">
        <StatusBadge status={report.status} />
      </td>

      {/* Period */}
      <td className="px-4 py-3 text-sm text-[#4a524a]">
        <div className="flex items-center gap-1.5">
          <Calendar className="w-3.5 h-3.5 text-[#7b827b]" strokeWidth={1.6} />
          {fmtPeriod(report.period_start, report.period_end)}
        </div>
      </td>

      {/* Generated At */}
      <td className="px-4 py-3 text-sm text-[#4a524a]">
        {fmtDate(report.generated_at)}
      </td>

      {/* Size */}
      <td className="px-4 py-3 text-sm text-[#7b827b] text-right tabular-nums">
        {fmtSize(report.file_size)}
      </td>

      {/* Time */}
      <td className="px-4 py-3 text-sm text-[#7b827b] text-right tabular-nums">
        {fmtMs(report.generation_time_ms)}
      </td>

      {/* Actions */}
      <td className="px-4 py-3">
        <div className="flex items-center gap-1.5 justify-end">
          {inProgress && (
            <button
              onClick={() => onRefresh(report.id)}
              title="Refresh status"
              className="p-1.5 rounded text-[#7b827b] hover:text-[#2d5a27] hover:bg-[#f4f5f2] transition-colors"
            >
              <RefreshCw className="w-3.5 h-3.5" strokeWidth={1.8} />
            </button>
          )}
          {report.status === "complete" && (
            <a
              href={getDownloadUrl(report.id)}
              target="_blank"
              rel="noopener noreferrer"
              title="Download"
              className="p-1.5 rounded text-[#2d5a27] hover:bg-[#f4f5f2] transition-colors"
            >
              <Download className="w-3.5 h-3.5" strokeWidth={1.8} />
            </a>
          )}
          <button
            onClick={handleDelete}
            disabled={deleting || inProgress}
            title="Delete"
            className="p-1.5 rounded text-[#7b827b] hover:text-red-600 hover:bg-red-50 transition-colors disabled:opacity-40"
          >
            {deleting ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Trash2 className="w-3.5 h-3.5" strokeWidth={1.8} />
            )}
          </button>
        </div>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Summary cards
// ---------------------------------------------------------------------------

function SummaryCard({ label, value, color = "#2d5a27" }) {
  return (
    <div className="bg-white rounded-xl border border-[#eaece6] px-5 py-4 flex flex-col gap-1">
      <div className="text-xs text-[#7b827b] font-medium uppercase tracking-wide">{label}</div>
      <div className="text-2xl font-bold" style={{ color }}>{value}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function ReportsPage() {
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const pollRef = useRef(null);

  const loadReports = useCallback(async () => {
    try {
      const data = await fetchReports();
      setReports(data.reports ?? []);
      setError(null);
    } catch (err) {
      setError("Failed to load reports.");
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    loadReports();
  }, [loadReports]);

  // Poll every 3 s while any report is in progress
  useEffect(() => {
    const hasInProgress = reports.some((r) => isInProgress(r.status));
    if (hasInProgress) {
      pollRef.current = setInterval(loadReports, 3000);
    } else if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [reports, loadReports]);

  const handleGenerate = async (type, format) => {
    const pending = await generateReport(type, format);
    setReports((prev) => [pending, ...prev]);
  };

  const handleDelete = (id) => {
    setReports((prev) => prev.filter((r) => r.id !== id));
  };

  const handleRefresh = async (id) => {
    try {
      const updated = await fetchReport(id);
      setReports((prev) => prev.map((r) => (r.id === id ? updated : r)));
    } catch {
      /* ignore */
    }
  };

  // Summary stats
  const total   = reports.length;
  const complete = reports.filter((r) => r.status === "complete").length;
  const pending  = reports.filter((r) => isInProgress(r.status)).length;
  const failed   = reports.filter((r) => r.status === "failed").length;
  const pdfs     = reports.filter((r) => r.format === "pdf").length;

  return (
    <AppLayout>
      <div className="max-w-7xl mx-auto px-4 md:px-8 py-8">

        {/* Page header */}
        <div className="flex items-start justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-[#1a1e1a] tracking-tight">
              Operational Reports
            </h1>
            <p className="text-sm text-[#7b827b] mt-1">
              Generate and download intelligence reports for government agencies,
              forestry organizations, and commercial customers.
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={loadReports}
              className="border-[#eaece6] text-[#4a524a] hover:bg-[#f4f5f2]"
            >
              <RefreshCw className="w-4 h-4 mr-1.5" strokeWidth={1.6} />
              Refresh
            </Button>
            <Button
              onClick={() => setShowModal(true)}
              className="bg-[#2d5a27] hover:bg-[#3a7a34] text-white"
            >
              <Plus className="w-4 h-4 mr-1.5" strokeWidth={2} />
              Generate Report
            </Button>
          </div>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <SummaryCard label="Total Reports" value={total} />
          <SummaryCard label="Complete" value={complete} color="#22c55e" />
          <SummaryCard label="In Progress" value={pending} color="#3b82f6" />
          <SummaryCard label="PDF Reports" value={pdfs} color="#2d5a27" />
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl px-4 py-3 text-sm mb-6">
            {error}
          </div>
        )}

        {/* Reports table */}
        <div className="bg-white rounded-xl border border-[#eaece6] overflow-hidden">
          <div className="px-5 py-3.5 border-b border-[#eaece6] flex items-center justify-between">
            <div className="font-semibold text-[#1a1e1a] text-sm">Report History</div>
            {pending > 0 && (
              <div className="flex items-center gap-1.5 text-xs text-blue-600">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                {pending} report{pending !== 1 ? "s" : ""} generating…
              </div>
            )}
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-16 text-[#7b827b]">
              <Loader2 className="w-5 h-5 animate-spin mr-2" />
              Loading reports…
            </div>
          ) : reports.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-[#7b827b]">
              <FileText className="w-10 h-10 mb-3 text-[#eaece6]" strokeWidth={1.2} />
              <div className="font-medium text-[#4a524a]">No reports yet</div>
              <div className="text-sm mt-1">
                Click "Generate Report" to create your first intelligence report.
              </div>
              <Button
                onClick={() => setShowModal(true)}
                className="mt-4 bg-[#2d5a27] hover:bg-[#3a7a34] text-white text-sm"
              >
                <Plus className="w-4 h-4 mr-1.5" />
                Generate Report
              </Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b border-[#eaece6] bg-[#f4f5f2]">
                    {[
                      "Type", "Format", "Status", "Period",
                      "Generated At", "Size", "Time", "Actions",
                    ].map((h) => (
                      <th
                        key={h}
                        className="px-4 py-3 text-xs font-semibold text-[#7b827b] uppercase tracking-wide"
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {reports.map((report) => (
                    <ReportRow
                      key={report.id}
                      report={report}
                      onDelete={handleDelete}
                      onRefresh={handleRefresh}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Failed details */}
        {failed > 0 && (
          <div className="mt-4 space-y-2">
            {reports
              .filter((r) => r.status === "failed" && r.error)
              .map((r) => (
                <div
                  key={r.id}
                  className="bg-red-50 border border-red-200 rounded-lg px-4 py-2.5 text-sm text-red-700"
                >
                  <span className="font-semibold capitalize">{r.type}</span> report failed:{" "}
                  <span className="font-mono text-xs">{r.error}</span>
                </div>
              ))}
          </div>
        )}

        {/* Info box */}
        <div className="mt-6 bg-[#f4f5f2] rounded-xl border border-[#eaece6] px-5 py-4 text-sm text-[#4a524a]">
          <div className="font-semibold text-[#1a1e1a] mb-1.5">About Reports</div>
          <ul className="space-y-1 text-xs text-[#7b827b]">
            <li>• <strong>Daily</strong> reports cover the last 24 hours of intelligence data.</li>
            <li>• <strong>Weekly</strong> reports cover the last 7 days with trend analysis.</li>
            <li>• <strong>Monthly</strong> reports provide a 30-day comprehensive overview.</li>
            <li>• <strong>PDF</strong> reports include executive summary, charts, and maps — suitable for printing.</li>
            <li>• <strong>CSV/JSON</strong> exports are machine-readable and suitable for integrations.</li>
            <li>• Reports are generated asynchronously. Refresh the page to see the latest status.</li>
          </ul>
        </div>
      </div>

      {showModal && (
        <GenerateModal
          onClose={() => setShowModal(false)}
          onGenerate={handleGenerate}
        />
      )}
    </AppLayout>
  );
}
