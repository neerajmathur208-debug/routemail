import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import {
  Network,
  Inbox,
  Globe,
  Activity,
  AlertTriangle,
  Pause,
  CheckCircle2,
  Loader2,
  Search,
  FileSpreadsheet,
  FileText,
  Edit2,
  X,
  Filter,
  CalendarDays,
  Wand2,
  Calculator,
  ChevronDown,
  ChevronUp,
  Copy,
  CheckCircle,
  TrendingUp,
  Target,
  Plus,
  Trash2,
  Download,
  RefreshCcw,
  ShieldCheck,
  AlertCircle,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "../components/ui/dialog";
import Sidebar from "../components/Sidebar";
import { api } from "../App";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_COLOR = {
  Available: "bg-emerald-100 text-emerald-700",
  "Partially Available": "bg-amber-100 text-amber-700",
  "Fully Reserved": "bg-rose-100 text-rose-700",
  "Warming Up": "bg-sky-100 text-sky-700",
  Paused: "bg-slate-100 text-slate-600",
  Risky: "bg-red-100 text-red-700",
};

export default function Infrastructure({ user, setUser }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [summary, setSummary] = useState(null);
  const [inboxes, setInboxes] = useState([]);
  const [filterOptions, setFilterOptions] = useState({ ownership: [], domain: [] });

  // Filters
  const [search, setSearch] = useState("");
  const [ownership, setOwnership] = useState("__all__");
  const [domain, setDomain] = useState("__all__");
  const [statusFilter, setStatusFilter] = useState("__all__");
  const [warmupFilter, setWarmupFilter] = useState("__all__");
  const [minRemaining, setMinRemaining] = useState("0");

  // Ownership edit dialog
  const [ownerEdit, setOwnerEdit] = useState(null); // { account_id, email, ownership }
  const [ownerSaving, setOwnerSaving] = useState(false);

  // Replacement dialog
  const [replaceFor, setReplaceFor] = useState(null); // {row, preview, loading, saving}

  // Per-inbox 120-day calendar drill-down
  const [calendarFor, setCalendarFor] = useState(null); // the inbox row
  const [calendarData, setCalendarData] = useState(null);
  const [calendarLoading, setCalendarLoading] = useState(false);

  useEffect(() => {
    if (!calendarFor) {
      setCalendarData(null);
      return;
    }
    let cancelled = false;
    (async () => {
      setCalendarLoading(true);
      try {
        const res = await api.get(
          `/infrastructure/calendar/${calendarFor.account_id}?window_days=120`
        );
        if (!cancelled) setCalendarData(res.data);
      } catch (e) {
        if (!cancelled) toast.error(e?.response?.data?.detail || "Failed to load calendar");
      } finally {
        if (!cancelled) setCalendarLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [calendarFor]);

  // Permission gate — non-permitted users get redirected. The Sidebar already
  // hides the link, but this is defence in depth.
  useEffect(() => {
    if (user && !(user.role === "super_admin" || user.can_access_infrastructure)) {
      navigate("/dashboard", { replace: true });
    }
  }, [user, navigate]);

  const fetchSummary = useCallback(async () => {
    try {
      const res = await api.get("/infrastructure/summary");
      setSummary(res.data);
    } catch (e) {
      // 403 handled by axios interceptor / redirect
    }
  }, []);

  const fetchInboxes = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (ownership && ownership !== "__all__") params.set("ownership", ownership);
      if (domain && domain !== "__all__") params.set("domain", domain);
      if (statusFilter && statusFilter !== "__all__") params.set("status", statusFilter);
      if (warmupFilter && warmupFilter !== "__all__") params.set("warmup_status", warmupFilter);
      if (minRemaining && parseInt(minRemaining, 10) > 0)
        params.set("min_remaining", minRemaining);
      if (search.trim()) params.set("search", search.trim());
      const res = await api.get(`/infrastructure/inboxes?${params.toString()}`);
      setInboxes(res.data.inboxes || []);
      setFilterOptions(res.data.filter_options || { ownership: [], domain: [] });
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to load infrastructure inventory");
    } finally {
      setLoading(false);
    }
  }, [ownership, domain, statusFilter, warmupFilter, minRemaining, search]);

  useEffect(() => {
    fetchSummary();
    fetchInboxes();
  }, [fetchSummary, fetchInboxes]);

  const resetFilters = () => {
    setSearch("");
    setOwnership("__all__");
    setDomain("__all__");
    setStatusFilter("__all__");
    setWarmupFilter("__all__");
    setMinRemaining("0");
  };

  const downloadExport = async (type, format) => {
    try {
      const res = await axios.get(
        `${API}/infrastructure/export?type=${type}&format=${format}`,
        { withCredentials: true, responseType: "blob" }
      );
      const cd = res.headers["content-disposition"] || "";
      const m = cd.match(/filename="([^"]+)"/);
      const fname = m ? m[1] : `infrastructure_${type}.${format}`;
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = fname;
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success("Export downloaded");
    } catch (e) {
      toast.error("Export failed");
    }
  };

  const saveOwnership = async () => {
    if (!ownerEdit) return;
    setOwnerSaving(true);
    try {
      await api.put(`/accounts/${ownerEdit.account_id}/ownership`, {
        ownership: ownerEdit.ownership || "",
      });
      toast.success("Ownership updated");
      setOwnerEdit(null);
      fetchInboxes();
      fetchSummary();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to update ownership");
    } finally {
      setOwnerSaving(false);
    }
  };

  const domainSummary = useMemo(() => {
    if (!summary?.domains) return [];
    return Object.entries(summary.domains)
      .map(([dom, info]) => ({ domain: dom, ...info }))
      .sort((a, b) => (a.domain < b.domain ? -1 : 1));
  }, [summary]);

  return (
    <div className="flex bg-slate-50 min-h-screen">
      <Sidebar user={user} setUser={setUser} />
      <main className="flex-1 min-w-0 p-4 sm:p-6 lg:p-8 pt-24 lg:pt-8">
        {/* Header */}
        <div className="flex items-start justify-between flex-wrap gap-4 mb-6">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <Network className="text-sky-600" size={28} strokeWidth={1.5} />
              <h1 className="text-2xl sm:text-3xl font-bold text-slate-900">Infrastructure</h1>
              <span
                className="px-2 py-0.5 text-[10px] font-semibold rounded-full bg-sky-100 text-sky-700 uppercase tracking-wide"
                data-testid="infra-internal-badge"
              >
                Internal Only
              </span>
            </div>
            <p className="text-slate-500 text-sm max-w-2xl">
              Live 120-day projection, per-inbox calendar drill-down, diversification-aware
              auto-allocation and a capacity planner — all from real send data.
            </p>
          </div>
          <div className="flex flex-wrap gap-2 w-full sm:w-auto">
            <Button
              variant="outline"
              size="sm"
              onClick={() => downloadExport("inboxes", "xlsx")}
              data-testid="infra-export-inboxes-xlsx"
            >
              <FileSpreadsheet size={16} className="mr-1.5" />
              <span className="hidden sm:inline">Inbox Inventory (xlsx)</span>
              <span className="sm:hidden">Inboxes XLSX</span>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={async () => {
                try {
                  const res = await axios.get(`${API}/infrastructure/accounts/export?format=xlsx`, { withCredentials: true, responseType: "blob" });
                  const cd = res.headers["content-disposition"] || ""; const m = cd.match(/filename="([^"]+)"/);
                  const url = window.URL.createObjectURL(new Blob([res.data])); const a = document.createElement("a");
                  a.href = url; a.download = m ? m[1] : "accounts.xlsx"; a.click(); window.URL.revokeObjectURL(url);
                  toast.success("Email accounts exported");
                } catch { toast.error("Export failed"); }
              }}
              data-testid="infra-export-accounts-xlsx"
            >
              <FileSpreadsheet size={16} className="mr-1.5" />
              <span className="hidden sm:inline">Email Accounts</span>
              <span className="sm:hidden">Accounts</span>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => downloadExport("inboxes", "csv")}
              data-testid="infra-export-inboxes-csv"
            >
              <FileText size={16} className="mr-1.5" /> CSV
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => downloadExport("domains", "xlsx")}
              data-testid="infra-export-domains-xlsx"
            >
              <FileSpreadsheet size={16} className="mr-1.5" />
              <span className="hidden sm:inline">Domain Inventory</span>
              <span className="sm:hidden">Domains</span>
            </Button>
          </div>
        </div>

        {/* Summary cards */}
        <section
          className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3 mb-6"
          data-testid="infra-summary-cards"
        >
          <SummaryCard
            label="Available"
            value={summary?.inbox_counts?.available ?? 0}
            icon={CheckCircle2}
            color="text-emerald-600"
            testid="card-available-inboxes"
          />
          <SummaryCard
            label="Partial"
            value={summary?.inbox_counts?.partially_available ?? 0}
            icon={Activity}
            color="text-amber-600"
            testid="card-partial-inboxes"
          />
          <SummaryCard
            label="Reserved"
            value={summary?.inbox_counts?.fully_reserved ?? 0}
            icon={Inbox}
            color="text-rose-600"
            testid="card-reserved-inboxes"
          />
          <SummaryCard
            label="Warming Up"
            value={summary?.inbox_counts?.warming_up ?? 0}
            icon={Activity}
            color="text-sky-600"
            testid="card-warming-inboxes"
          />
          <SummaryCard
            label="Paused"
            value={summary?.inbox_counts?.paused ?? 0}
            icon={Pause}
            color="text-slate-500"
            testid="card-paused-inboxes"
          />
          <SummaryCard
            label="Risky"
            value={summary?.inbox_counts?.risky ?? 0}
            icon={AlertTriangle}
            color="text-red-600"
            testid="card-risky-inboxes"
          />
        </section>

        <section
          className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8"
          data-testid="infra-capacity-cards"
        >
          <CapacityCard
            label="Remaining Today"
            value={summary?.capacity?.remaining_today ?? 0}
            testid="card-cap-today"
          />
          <CapacityCard
            label="Next 7 Days"
            value={summary?.capacity?.remaining_week ?? 0}
            testid="card-cap-week"
          />
          <CapacityCard
            label="Next 30 Days"
            value={summary?.capacity?.remaining_30_days ?? 0}
            testid="card-cap-30d"
          />
          <CapacityCard
            label="Next 120 Days"
            value={summary?.capacity?.remaining_window ?? 0}
            testid="card-cap-120d"
          />
        </section>

        {/* Phase A — Forecasting + Domain Tracking */}
        <ForecastSection />
        <ReputationSummaryCard />
        <DomainTrackingSection />

        {/* Domain rollup table */}
        <section
          className="bg-white border border-slate-200 rounded-2xl p-4 mb-6"
          data-testid="infra-domain-section"
        >
          <div className="flex items-center justify-between mb-3 px-2">
            <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
              <Globe size={18} className="text-sky-600" /> Domain Capacity
            </h2>
            <span className="text-xs text-slate-500">
              {domainSummary.length} domains
            </span>
          </div>
          {domainSummary.length === 0 ? (
            <div className="px-2 py-6 text-sm text-slate-500">
              No domains found yet.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium">Domain</th>
                    <th className="text-right px-3 py-2 font-medium">Inboxes</th>
                    <th className="text-right px-3 py-2 font-medium">Total / Day</th>
                    <th className="text-right px-3 py-2 font-medium">Used</th>
                    <th className="text-right px-3 py-2 font-medium">Remaining</th>
                    <th className="text-right px-3 py-2 font-medium">Projected (120d)</th>
                    <th className="text-left px-3 py-2 font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {domainSummary.map((d) => (
                    <tr
                      key={d.domain}
                      className="border-t border-slate-100 hover:bg-slate-50"
                      data-testid={`domain-row-${d.domain}`}
                    >
                      <td className="px-3 py-2 font-medium text-slate-800">{d.domain}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{d.inbox_count}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{d.total}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{d.used}</td>
                      <td className="px-3 py-2 text-right tabular-nums font-semibold">
                        {d.remaining}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-slate-700">
                        {(d.projected_window || 0).toLocaleString()}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            STATUS_COLOR[d.status] || "bg-slate-100 text-slate-700"
                          }`}
                        >
                          {d.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Inbox Availability summary card (Phase 3 Batch 2 — full table moved to /infrastructure/inboxes) */}
        <section
          className="bg-white border border-slate-200 rounded-2xl p-4"
          data-testid="infra-inbox-section"
        >
          <div className="flex items-center justify-between mb-4 px-2 flex-wrap gap-3">
            <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
              <Inbox size={18} className="text-sky-600" /> Inbox Availability
            </h2>
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate("/infrastructure/inboxes")}
              data-testid="view-inbox-availability-btn"
            >
              View Inbox Availability →
            </Button>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 px-2" data-testid="inbox-summary-cards">
            {(() => {
              const counts = { total: inboxes.length };
              for (const r of inboxes) {
                const k = (r.status || "").replace(/\s+/g, "_").toLowerCase();
                counts[k] = (counts[k] || 0) + 1;
              }
              const items = [
                { label: "Total Inboxes", value: counts.total, tone: "slate", testid: "inbox-stat-total" },
                { label: "Available", value: counts.available || 0, tone: "emerald", testid: "inbox-stat-available" },
                { label: "Partially Available", value: counts.partially_available || 0, tone: "sky", testid: "inbox-stat-partial" },
                { label: "In Use", value: (counts.in_use || 0) + (counts.fully_reserved || 0), tone: "amber", testid: "inbox-stat-in-use" },
                { label: "Paused", value: counts.paused || 0, tone: "slate", testid: "inbox-stat-paused" },
                { label: "Risky", value: counts.risky || 0, tone: "rose", testid: "inbox-stat-risky" },
              ];
              return items.map((c) => <BucketCard key={c.label} {...c} />);
            })()}
          </div>

          {inboxes.length > 0 && (
            <p className="text-xs text-slate-500 mt-3 px-2">
              The full searchable, filterable, exportable table now lives on{" "}
              <button
                onClick={() => navigate("/infrastructure/inboxes")}
                className="text-indigo-600 hover:text-indigo-700 underline"
                data-testid="inbox-summary-cta-link"
              >
                Inbox Availability
              </button>.
            </p>
          )}
        </section>

        {/* Ownership edit dialog */}
        <Dialog open={!!ownerEdit} onOpenChange={(o) => !o && setOwnerEdit(null)}>
          <DialogContent
            className="sm:max-w-[440px]"
            data-testid="ownership-edit-dialog"
          >
            <DialogHeader>
              <DialogTitle>Set Ownership</DialogTitle>
            </DialogHeader>
            <div className="space-y-3">
              <div className="text-sm text-slate-600">
                Inbox:{" "}
                <span className="font-medium text-slate-900">{ownerEdit?.email}</span>
              </div>
              <div>
                <Label className="mb-1.5">Ownership label</Label>
                <Input
                  data-testid="ownership-input"
                  placeholder="e.g. Perfect Digitals, Client A, Internal"
                  value={ownerEdit?.ownership || ""}
                  onChange={(e) =>
                    setOwnerEdit({ ...ownerEdit, ownership: e.target.value })
                  }
                  autoFocus
                />
                <p className="text-xs text-slate-500 mt-1">
                  Leave empty to clear. Used to filter inboxes and group them in
                  capacity reports.
                </p>
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setOwnerEdit(null)}
                data-testid="ownership-cancel"
              >
                <X size={14} className="mr-1" /> Cancel
              </Button>
              <Button
                onClick={saveOwnership}
                disabled={ownerSaving}
                className="bg-sky-600 hover:bg-sky-700 text-white"
                data-testid="ownership-save"
              >
                {ownerSaving ? (
                  <Loader2 size={14} className="mr-1.5 animate-spin" />
                ) : (
                  <CheckCircle2 size={14} className="mr-1.5" />
                )}
                Save
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        {/* Per-inbox 120-day calendar dialog */}
        <CalendarDialog
          open={!!calendarFor}
          onClose={() => setCalendarFor(null)}
          inbox={calendarFor}
          data={calendarData}
          loading={calendarLoading}
        />

        {/* Auto-Allocation + Capacity Planner — Phase 3 */}
        <AllocatorSection />
        <PlannerSection />
        <ReplacementSection
          onRequestReplace={async (row) => {
            setReplaceFor({ row, preview: null, loading: true, saving: false });
            try {
              const res = await api.get(`/infrastructure/replacements/candidate/${row.account_id}`);
              setReplaceFor({ row, preview: res.data, loading: false, saving: false });
            } catch (e) {
              toast.error(e?.response?.data?.detail || "Preview failed");
              setReplaceFor(null);
            }
          }}
        />
        <IssuesDashboardCard />

        {/* Replacement preview / confirm dialog */}
        <Dialog open={!!replaceFor} onOpenChange={(o) => !o && setReplaceFor(null)}>
          <DialogContent className="sm:max-w-[640px]" data-testid="replace-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <RefreshCcw size={18} className="text-violet-600" />
                Replace inbox
              </DialogTitle>
            </DialogHeader>
            {replaceFor?.loading ? (
              <div className="py-8 text-center text-slate-500 text-sm" data-testid="replace-loading">
                <Loader2 className="inline-block animate-spin mr-2" size={14} /> Finding the best replacement…
              </div>
            ) : replaceFor?.preview ? (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div className="border border-rose-200 bg-rose-50/50 rounded-lg p-3" data-testid="replace-from">
                    <div className="text-[11px] uppercase tracking-wider text-rose-600 mb-1">Replacing</div>
                    <div className="font-semibold text-slate-900">{replaceFor.preview.replaced.email}</div>
                    <div className="text-xs text-slate-600 mt-1">
                      {replaceFor.preview.replaced.domain} · {replaceFor.preview.replaced.status}
                    </div>
                  </div>
                  {replaceFor.preview.candidate ? (
                    <div className="border border-emerald-200 bg-emerald-50/50 rounded-lg p-3" data-testid="replace-to">
                      <div className="text-[11px] uppercase tracking-wider text-emerald-700 mb-1">With</div>
                      <div className="font-semibold text-slate-900">{replaceFor.preview.candidate.email}</div>
                      <div className="text-xs text-slate-600 mt-1">
                        {replaceFor.preview.candidate.domain} · {replaceFor.preview.candidate.remaining_capacity} remaining
                        {replaceFor.preview.candidate.cross_domain && (
                          <span className="ml-1 px-1.5 py-0.5 rounded-full bg-violet-100 text-violet-700 text-[10px]">
                            cross-domain
                          </span>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="border border-amber-200 bg-amber-50/50 rounded-lg p-3" data-testid="replace-nocand">
                      <div className="text-[11px] uppercase tracking-wider text-amber-700 mb-1">No candidate</div>
                      <div className="text-xs text-slate-700">{replaceFor.preview.no_candidate_reason}</div>
                    </div>
                  )}
                </div>

                <div className="border border-slate-200 rounded-lg p-3">
                  <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-2">Affected workloads</div>
                  {(replaceFor.preview.affected.campaigns.length === 0 &&
                    replaceFor.preview.affected.drips.length === 0) ? (
                    <div className="text-xs text-slate-500" data-testid="replace-noaffected">
                      No running campaigns or drips currently use this inbox.
                    </div>
                  ) : (
                    <ul className="space-y-1 text-sm" data-testid="replace-affected-list">
                      {replaceFor.preview.affected.campaigns.map((c) => (
                        <li key={`c-${c.campaign_id}`} className="text-slate-700">
                          <span className="px-1.5 py-0.5 rounded bg-sky-100 text-sky-700 text-[10px] mr-1.5">
                            campaign
                          </span>
                          {c.name} <span className="text-xs text-slate-400">· {c.status}</span>
                        </li>
                      ))}
                      {replaceFor.preview.affected.drips.map((d) => (
                        <li key={`d-${d.drip_id}`} className="text-slate-700">
                          <span className="px-1.5 py-0.5 rounded bg-violet-100 text-violet-700 text-[10px] mr-1.5">
                            drip
                          </span>
                          {d.name} <span className="text-xs text-slate-400">· {d.status}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            ) : null}
            <DialogFooter>
              <Button variant="outline" onClick={() => setReplaceFor(null)} data-testid="replace-cancel">
                Cancel
              </Button>
              <Button
                disabled={
                  !replaceFor?.preview?.candidate || replaceFor?.saving || replaceFor?.loading
                }
                onClick={async () => {
                  if (!replaceFor?.preview?.candidate) return;
                  setReplaceFor({ ...replaceFor, saving: true });
                  try {
                    const res = await api.post(
                      `/infrastructure/replacements/execute/${replaceFor.row.account_id}`,
                      {
                        replacement_account_id: replaceFor.preview.candidate.account_id,
                        manual: true,
                      }
                    );
                    const sc = res.data?.swap_counts || { campaigns: 0, drips: 0 };
                    toast.success(
                      `Replaced — ${sc.campaigns} campaign(s) and ${sc.drips} drip(s) updated`
                    );
                    setReplaceFor(null);
                    fetchInboxes();
                    fetchSummary();
                  } catch (e) {
                    toast.error(e?.response?.data?.detail?.message || e?.response?.data?.detail || "Replacement failed");
                    setReplaceFor({ ...replaceFor, saving: false });
                  }
                }}
                className="bg-violet-600 hover:bg-violet-700 text-white"
                data-testid="replace-confirm"
              >
                {replaceFor?.saving ? (
                  <Loader2 className="mr-2 animate-spin" size={14} />
                ) : (
                  <RefreshCcw className="mr-2" size={14} />
                )}
                Confirm Replace
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
}

function SummaryCard({ label, value, icon: Icon, color, testid }) {
  return (
    <div
      data-testid={testid}
      className="bg-white border border-slate-200 rounded-xl p-3 flex items-center gap-3"
    >
      <Icon className={color} size={22} strokeWidth={1.5} />
      <div>
        <div className="text-2xl font-bold tabular-nums text-slate-900">{value}</div>
        <div className="text-[11px] uppercase tracking-wider text-slate-500">
          {label}
        </div>
      </div>
    </div>
  );
}

function CapacityCard({ label, value, testid }) {
  return (
    <div
      data-testid={testid}
      className="bg-gradient-to-br from-sky-50 to-white border border-sky-100 rounded-xl p-4"
    >
      <div className="text-xs uppercase tracking-wider text-slate-500 mb-1">
        {label}
      </div>
      <div className="text-3xl font-bold text-sky-700 tabular-nums">
        {(value || 0).toLocaleString()}
      </div>
      <div className="text-xs text-slate-500 mt-1">Emails</div>
    </div>
  );
}

function FilterSelect({ label, value, onChange, options, testid }) {
  return (
    <div className="flex flex-col">
      <Label className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">
        {label}
      </Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="min-w-[140px]" data-testid={testid}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="__all__">All</SelectItem>
          {options.map((o) => (
            <SelectItem key={o} value={o}>
              {o}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

/* ============================================================
 * Per-inbox 120-day calendar dialog
 *   • Heatmap on top — 17 weeks × 7 days, colour-coded by usage
 *   • Expandable daily table below
 * ============================================================ */
const HEATMAP_LEGEND = [
  { label: "Available", className: "bg-emerald-200", testid: "heat-legend-available" },
  { label: "Partial",  className: "bg-amber-300",  testid: "heat-legend-partial" },
  { label: "Reserved", className: "bg-rose-400",   testid: "heat-legend-reserved" },
];

function heatColour(day) {
  if (!day) return "bg-slate-100";
  if (day.status === "Reserved") return "bg-rose-400";
  if (day.status === "Partial")  return "bg-amber-300";
  // Available — shade by absolute remaining vs limit so the eye can spot
  // partially-saturated trends even on light-green days.
  return "bg-emerald-200";
}

function CalendarDialog({ open, onClose, inbox, data, loading }) {
  const [showTable, setShowTable] = useState(false);
  const days = data?.days || [];
  const window_days = data?.window_days || 120;
  const totals = data?.totals || { projected: 0, remaining: 0, capacity: 0 };

  // Build a "weeks" matrix that starts on the Monday of the first day's week,
  // so the grid lines up vertically. Pad leading + trailing slots with null.
  const weeks = [];
  if (days.length > 0) {
    const firstWeekday = days[0].weekday; // 0=Mon
    let row = Array(firstWeekday).fill(null);
    for (const d of days) {
      row.push(d);
      if (row.length === 7) {
        weeks.push(row);
        row = [];
      }
    }
    if (row.length > 0) {
      while (row.length < 7) row.push(null);
      weeks.push(row);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent
        className="sm:max-w-[860px] max-h-[90vh] overflow-y-auto"
        data-testid="calendar-dialog"
      >
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <CalendarDays size={20} className="text-sky-600" />
            120-Day Availability Calendar
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4">
          <div className="text-sm text-slate-600">
            <span className="font-medium text-slate-900">{inbox?.email}</span>
            {" · "}Daily limit: <span className="font-medium">{inbox?.daily_limit}</span>
            {" · "}Window: <span className="font-medium">{window_days} days</span>
          </div>

          {/* Totals summary */}
          <div className="grid grid-cols-3 gap-2" data-testid="calendar-totals">
            <Mini label="Total Capacity" value={totals.capacity} />
            <Mini label="Projected" value={totals.projected} />
            <Mini label="Remaining" value={totals.remaining} highlight />
          </div>

          {/* Legend */}
          <div className="flex items-center gap-3 text-xs text-slate-500">
            <span>Legend:</span>
            {HEATMAP_LEGEND.map((l) => (
              <span
                key={l.label}
                className="flex items-center gap-1.5"
                data-testid={l.testid}
              >
                <span className={`inline-block w-3 h-3 rounded-sm ${l.className}`} />
                {l.label}
              </span>
            ))}
          </div>

          {/* Heatmap */}
          {loading ? (
            <div className="py-12 text-center text-slate-500" data-testid="calendar-loading">
              <Loader2 className="inline animate-spin mr-2" size={16} /> Loading…
            </div>
          ) : (
            <div data-testid="calendar-heatmap" className="bg-white border border-slate-200 rounded-lg p-3 overflow-x-auto">
              <div className="flex gap-[3px]">
                {/* Day-of-week labels */}
                <div className="flex flex-col gap-[3px] mr-2 mt-[18px] text-[10px] text-slate-400">
                  {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
                    <div key={d} className="h-3 leading-3">{d}</div>
                  ))}
                </div>
                {weeks.map((week, wIdx) => (
                  <div key={wIdx} className="flex flex-col gap-[3px]">
                    {/* Tiny week label every 4 weeks */}
                    <div className="h-3 text-[10px] text-slate-400 text-center">
                      {wIdx % 4 === 0 && week.find(Boolean)
                        ? new Date(week.find(Boolean).date).toLocaleDateString(undefined, { month: "short", day: "numeric" })
                        : ""}
                    </div>
                    {week.map((day, dIdx) => (
                      <div
                        key={dIdx}
                        title={day ? `${day.date}: ${day.used}/${day.limit} used (${day.remaining} remaining) — ${day.status}` : ""}
                        className={`w-3 h-3 rounded-[2px] ${heatColour(day)} ${
                          day ? "hover:ring-1 hover:ring-sky-400 cursor-help" : "opacity-30"
                        }`}
                        data-testid={day ? `heat-cell-${day.date}` : undefined}
                      />
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Expandable table */}
          <div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowTable((s) => !s)}
              data-testid="calendar-toggle-table"
            >
              {showTable ? "Hide" : "Show"} day-by-day table
            </Button>
            {showTable && (
              <div className="mt-3 max-h-[40vh] overflow-y-auto border border-slate-200 rounded-lg" data-testid="calendar-table">
                <table className="w-full text-sm">
                  <thead className="text-xs uppercase tracking-wide text-slate-500 bg-slate-50 sticky top-0">
                    <tr>
                      <th className="text-left px-3 py-2 font-medium">Date</th>
                      <th className="text-right px-3 py-2 font-medium">Limit</th>
                      <th className="text-right px-3 py-2 font-medium">Projected</th>
                      <th className="text-right px-3 py-2 font-medium">Used</th>
                      <th className="text-right px-3 py-2 font-medium">Remaining</th>
                      <th className="text-left px-3 py-2 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {days.map((d) => (
                      <tr
                        key={d.date}
                        className="border-t border-slate-100"
                        data-testid={`calendar-row-${d.date}`}
                      >
                        <td className="px-3 py-1.5 font-medium text-slate-700">
                          {d.date}
                          <span className="text-slate-400 ml-2 text-xs">
                            {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][d.weekday]}
                          </span>
                        </td>
                        <td className="px-3 py-1.5 text-right tabular-nums">{d.limit}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums">{d.projected}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums">{d.used}</td>
                        <td className="px-3 py-1.5 text-right tabular-nums font-semibold">
                          {d.remaining}
                        </td>
                        <td className="px-3 py-1.5">
                          <span
                            className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                              d.status === "Reserved"
                                ? "bg-rose-100 text-rose-700"
                                : d.status === "Partial"
                                ? "bg-amber-100 text-amber-700"
                                : "bg-emerald-100 text-emerald-700"
                            }`}
                          >
                            {d.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} data-testid="calendar-close">
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Mini({ label, value, highlight }) {
  return (
    <div
      className={`rounded-lg p-3 text-center ${
        highlight ? "bg-sky-50 border border-sky-100" : "bg-slate-50"
      }`}
    >
      <div className="text-[10px] uppercase tracking-wider text-slate-500">{label}</div>
      <div
        className={`text-2xl font-bold tabular-nums ${
          highlight ? "text-sky-700" : "text-slate-900"
        }`}
      >
        {(value || 0).toLocaleString()}
      </div>
    </div>
  );
}


/* ============================================================
 *  Auto-Allocation — standalone tool (Phase 3)
 *  Diversification-aware inbox picker. Calls POST /infrastructure/allocate.
 * ============================================================ */
function AllocatorSection() {
  const [open, setOpen] = useState(true);
  const [required, setRequired] = useState(8);
  const [minRemaining, setMinRemaining] = useState(10);
  const [domainFloor, setDomainFloor] = useState(10);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const run = async () => {
    setLoading(true);
    setResult(null);
    try {
      const res = await api.post("/infrastructure/allocate", {
        required: Number(required) || 1,
        min_remaining_per_inbox: Number(minRemaining) || 0,
        domain_capacity_floor: Number(domainFloor) || 0,
      });
      setResult(res.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail?.[0]?.msg || e?.response?.data?.detail || "Allocation failed");
    } finally {
      setLoading(false);
    }
  };

  const copyEmails = async () => {
    if (!result?.inboxes?.length) return;
    // Comma-separated so the output drops cleanly into the campaign /
    // drip-campaign account selector's paste handler.
    const text = result.inboxes.map((i) => i.email).join(", ");
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast.success(`Copied ${result.inboxes.length} emails`);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error("Clipboard blocked by the browser");
    }
  };

  return (
    <section
      className="bg-white border border-slate-200 rounded-2xl p-4 mt-6"
      data-testid="infra-allocator-section"
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-2"
        data-testid="infra-allocator-toggle"
      >
        <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
          <Wand2 size={18} className="text-violet-600" /> Auto-Allocate Inboxes
        </h2>
        {open ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
      </button>

      {open && (
        <div className="mt-4 px-2 space-y-4">
          <p className="text-sm text-slate-500 max-w-3xl">
            Pick inboxes diversification-first — one per domain before reusing any, prefer
            highest remaining capacity, skip warming/paused/risky inboxes and domains near
            today&apos;s exhaustion floor.
          </p>

          <div className="flex flex-wrap items-end gap-3">
            <div>
              <Label className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">
                Required inboxes
              </Label>
              <Input
                type="number"
                min={1}
                value={required}
                onChange={(e) => setRequired(e.target.value)}
                className="w-32"
                data-testid="allocator-required-input"
              />
            </div>
            <div>
              <Label className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">
                Min remaining / inbox
              </Label>
              <Input
                type="number"
                min={0}
                value={minRemaining}
                onChange={(e) => setMinRemaining(e.target.value)}
                className="w-32"
                data-testid="allocator-min-remaining-input"
              />
            </div>
            <div>
              <Label className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">
                Domain capacity floor
              </Label>
              <Input
                type="number"
                min={0}
                value={domainFloor}
                onChange={(e) => setDomainFloor(e.target.value)}
                className="w-32"
                data-testid="allocator-domain-floor-input"
              />
            </div>
            <Button
              onClick={run}
              disabled={loading}
              className="bg-violet-600 hover:bg-violet-700 text-white"
              data-testid="allocator-run-btn"
            >
              {loading ? (
                <Loader2 className="mr-2 animate-spin" size={16} />
              ) : (
                <Wand2 className="mr-2" size={16} />
              )}
              Recommend
            </Button>
          </div>

          {result && (
            <div data-testid="allocator-result" className="border border-slate-200 rounded-lg p-4 bg-slate-50/50">
              <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
                <div className="flex items-center gap-4 text-sm">
                  <span className="font-semibold text-slate-900">
                    {result.allocated}
                  </span>
                  <span className="text-slate-500">of {result.requested} requested</span>
                  <span className="text-slate-300">·</span>
                  <span>
                    Domains used: <span className="font-semibold">{result.domains_used.length}</span>
                  </span>
                  <span className="text-slate-300">·</span>
                  <span>
                    Avg per domain:{" "}
                    <span className="font-semibold">{result.avg_inboxes_per_domain}</span>
                  </span>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={copyEmails}
                  disabled={!result.inboxes.length}
                  data-testid="allocator-copy-btn"
                >
                  {copied ? (
                    <CheckCircle className="mr-1.5 text-emerald-600" size={14} />
                  ) : (
                    <Copy className="mr-1.5" size={14} />
                  )}
                  {copied ? "Copied" : "Copy emails"}
                </Button>
              </div>

              {result.warnings?.length > 0 && (
                <ul
                  className="mb-3 space-y-1 text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded p-3"
                  data-testid="allocator-warnings"
                >
                  {result.warnings.map((w, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                      <span>{w}</span>
                    </li>
                  ))}
                </ul>
              )}

              {result.inboxes.length === 0 ? (
                <div className="text-sm text-slate-500" data-testid="allocator-empty">
                  No eligible inboxes match the current filters.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-xs uppercase tracking-wide text-slate-500">
                      <tr>
                        <th className="text-left px-3 py-2 font-medium">Email</th>
                        <th className="text-left px-3 py-2 font-medium">Domain</th>
                        <th className="text-left px-3 py-2 font-medium">Ownership</th>
                        <th className="text-right px-3 py-2 font-medium">Daily Limit</th>
                        <th className="text-right px-3 py-2 font-medium">Remaining</th>
                        <th className="text-left px-3 py-2 font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.inboxes.map((i) => (
                        <tr
                          key={i.account_id}
                          className="border-t border-slate-100"
                          data-testid={`allocator-row-${i.account_id}`}
                        >
                          <td className="px-3 py-1.5 font-medium text-slate-900">{i.email}</td>
                          <td className="px-3 py-1.5 text-slate-600">{i.domain}</td>
                          <td className="px-3 py-1.5 text-slate-600">
                            {i.ownership || <span className="text-slate-400 italic">none</span>}
                          </td>
                          <td className="px-3 py-1.5 text-right tabular-nums">{i.daily_limit}</td>
                          <td className="px-3 py-1.5 text-right tabular-nums font-semibold">
                            {i.remaining_capacity}
                          </td>
                          <td className="px-3 py-1.5">
                            <span
                              className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                                STATUS_COLOR[i.status] || "bg-slate-100 text-slate-700"
                              }`}
                            >
                              {i.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}


/* ============================================================
 *  Capacity Planner — Phase 3
 *  Leads × Steps × Duration → required inboxes + Ready/Insufficient verdict.
 * ============================================================ */
function PlannerSection() {
  const [open, setOpen] = useState(true);
  const [mode, setMode] = useState("standard"); // "standard" | "batch"
  const [leads, setLeads] = useState(10000);
  const [steps, setSteps] = useState(3);
  const [days, setDays] = useState(30);
  const [sdpw, setSdpw] = useState(5);
  const [dailyLimit, setDailyLimit] = useState(50);
  const [preferredPerDomain, setPreferredPerDomain] = useState(5);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const buildPayload = () => ({
    leads: Number(leads) || 1,
    steps: Number(steps) || 1,
    duration_days: Number(days) || 1,
    sending_days_per_week: Number(sdpw) || 5,
    daily_limit_per_inbox: Number(dailyLimit) || 50,
    preferred_inboxes_per_domain: Number(preferredPerDomain) || 5,
  });

  const run = async () => {
    setLoading(true);
    setResult(null);
    try {
      const res = await api.post("/infrastructure/planner", buildPayload());
      setResult(res.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail?.[0]?.msg || e?.response?.data?.detail || "Planner failed");
    } finally {
      setLoading(false);
    }
  };

  const exportPlan = async (fmt) => {
    try {
      const res = await axios.post(
        `${API}/infrastructure/planner/export?format=${fmt}`,
        buildPayload(),
        { withCredentials: true, responseType: "blob" }
      );
      const cd = res.headers["content-disposition"] || "";
      const m = cd.match(/filename="([^"]+)"/);
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = m ? m[1] : `capacity-planner.${fmt}`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      toast.error("Export failed");
    }
  };

  const o = result?.outputs;
  const status = result?.status;

  return (
    <section
      className="bg-white border border-slate-200 rounded-2xl p-4 mt-6 mb-10"
      data-testid="infra-planner-section"
    >
      <button
        type="button"
        onClick={() => setOpen((p) => !p)}
        className="w-full flex items-center justify-between px-2"
        data-testid="infra-planner-toggle"
      >
        <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
          <Calculator size={18} className="text-emerald-600" /> Capacity Planner
        </h2>
        {open ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
      </button>

      {open && (
        <div className="mt-4 px-2 space-y-4">
          <p className="text-sm text-slate-500 max-w-3xl">
            Tell us the size of the outreach you&apos;re planning — we&apos;ll tell you whether your
            current inbox pool can absorb it, and how many more inboxes you&apos;d need if not.
          </p>

          {/* Mode selector */}
          <div className="flex items-center gap-2" data-testid="planner-mode-row">
            <Label className="text-[11px] uppercase tracking-wider text-slate-500">Planning Mode</Label>
            <div className="inline-flex rounded-lg border border-slate-200 overflow-hidden">
              <button
                type="button"
                onClick={() => setMode("standard")}
                data-testid="planner-mode-standard"
                className={`px-3 py-1.5 text-xs font-medium ${
                  mode === "standard"
                    ? "bg-emerald-600 text-white"
                    : "bg-white text-slate-600 hover:bg-slate-50"
                }`}
              >
                Standard Campaign Volume
              </button>
              <button
                type="button"
                onClick={() => setMode("batch")}
                data-testid="planner-mode-batch"
                className={`px-3 py-1.5 text-xs font-medium ${
                  mode === "batch"
                    ? "bg-emerald-600 text-white"
                    : "bg-white text-slate-600 hover:bg-slate-50"
                }`}
              >
                Batch-Based Weekly Sending
              </button>
            </div>
          </div>

          {mode === "batch" ? <BatchPlannerForm /> : (
          <>
          <div className="flex flex-wrap items-end gap-3">
            <PlannerInput label="Leads" value={leads} onChange={setLeads} testid="planner-leads" min={1} />
            <PlannerInput label="Steps" value={steps} onChange={setSteps} testid="planner-steps" min={1} max={20} />
            <PlannerInput label="Duration (days)" value={days} onChange={setDays} testid="planner-days" min={1} max={365} />
            <PlannerInput label="Sending days / week" value={sdpw} onChange={setSdpw} testid="planner-sdpw" min={1} max={7} />
            <PlannerInput label="Daily limit / inbox" value={dailyLimit} onChange={setDailyLimit} testid="planner-daily-limit" min={1} max={10000} />
            <PlannerInput label="Inboxes / domain" value={preferredPerDomain} onChange={setPreferredPerDomain} testid="planner-preferred-per-domain" min={1} max={100} />
            <Button
              onClick={run}
              disabled={loading}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
              data-testid="planner-run-btn"
            >
              {loading ? (
                <Loader2 className="mr-2 animate-spin" size={16} />
              ) : (
                <Calculator className="mr-2" size={16} />
              )}
              Calculate
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => exportPlan("xlsx")}
              data-testid="planner-export-xlsx"
            >
              <FileSpreadsheet size={14} className="mr-1.5" /> XLSX
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => exportPlan("csv")}
              data-testid="planner-export-csv"
            >
              <FileText size={14} className="mr-1.5" /> CSV
            </Button>
          </div>

          {result && (
            <div
              data-testid="planner-result"
              className="border border-slate-200 rounded-lg p-4 bg-slate-50/50"
            >
              <div className="flex items-center gap-2 mb-3">
                {status === "Ready" ? (
                  <span
                    className="px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700 flex items-center gap-1"
                    data-testid="planner-status-ready"
                  >
                    <CheckCircle size={14} /> Ready
                  </span>
                ) : (
                  <span
                    className="px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-100 text-rose-700 flex items-center gap-1"
                    data-testid="planner-status-insufficient"
                  >
                    <AlertTriangle size={14} /> Insufficient Capacity
                  </span>
                )}
                <span className="text-sm text-slate-500">
                  Estimated completion in{" "}
                  <span className="font-semibold text-slate-900">
                    {o?.estimated_completion_days}
                  </span>{" "}
                  days
                </span>
              </div>

              {result.warnings?.length > 0 && (
                <ul
                  className="mb-3 space-y-1 text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded p-3"
                  data-testid="planner-warnings"
                >
                  {result.warnings.map((w, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                      <span>{w}</span>
                    </li>
                  ))}
                </ul>
              )}

              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                <PlannerStat label="Total Emails" value={o?.total_emails} />
                <PlannerStat label="Required Daily Volume" value={o?.required_daily_volume} />
                <PlannerStat label="Required Inboxes" value={o?.required_inboxes} highlight />
                <PlannerStat label="Required Domains" value={o?.required_domains} highlight testid="planner-required-domains" />
                <PlannerStat label="Daily Capacity (total)" value={o?.daily_capacity_total} testid="planner-daily-capacity" />
                <PlannerStat label="Per Domain / day" value={o?.daily_capacity_per_domain} testid="planner-per-domain" />
                <PlannerStat label="Per Inbox / day" value={o?.daily_sends_per_inbox} testid="planner-per-inbox" />
                <PlannerStat label="Available Inboxes" value={o?.available_inboxes} />
                <PlannerStat label="Additional Inboxes" value={o?.additional_inboxes_required} testid="planner-additional-needed" />
                <PlannerStat label="Additional Domains" value={o?.additional_domains_required} testid="planner-additional-domains" />
                <PlannerStat label="Current Inboxes" value={o?.current_inboxes} />
                <PlannerStat label="Current Domains" value={o?.current_domains} />
              </div>
            </div>
          )}
          </>
          )}
        </div>
      )}
    </section>
  );
}

function PlannerInput({ label, value, onChange, testid, min, max }) {
  return (
    <div>
      <Label className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">
        {label}
      </Label>
      <Input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-36"
        data-testid={testid}
      />
    </div>
  );
}

function PlannerStat({ label, value, highlight, testid }) {
  return (
    <div
      data-testid={testid}
      className={`rounded-lg p-3 ${
        highlight ? "bg-emerald-50 border border-emerald-100" : "bg-white border border-slate-200"
      }`}
    >
      <div className="text-[10px] uppercase tracking-wider text-slate-500">{label}</div>
      <div
        className={`text-xl font-bold tabular-nums ${
          highlight ? "text-emerald-700" : "text-slate-900"
        }`}
      >
        {(value ?? 0).toLocaleString()}
      </div>
    </div>
  );
}

/* ============================================================
 *  Batch-Based Weekly Sending Planner
 *    POST /infrastructure/planner/batch         → calculates schedule
 *    POST /infrastructure/planner/batch/export  → xlsx | csv
 * ============================================================ */
const WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const STATUS_PILL = {
  Ready: "bg-emerald-100 text-emerald-700",
  "Partial Capacity": "bg-amber-100 text-amber-700",
  "Insufficient Capacity": "bg-rose-100 text-rose-700",
};

function BatchPlannerForm() {
  const [leads, setLeads] = useState(4000);
  const [steps, setSteps] = useState(3);
  const [delayDays, setDelayDays] = useState(7);
  const [sendingDays, setSendingDays] = useState([0, 1, 2, 3, 4]); // Mon–Fri
  const [accounts, setAccounts] = useState(20);
  const [perAccount, setPerAccount] = useState(40);
  const [startDate, setStartDate] = useState(() =>
    new Date().toISOString().slice(0, 10)
  );
  const [tz, setTz] = useState("UTC");
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(false);

  const includeWeekends = sendingDays.includes(5) || sendingDays.includes(6);
  const toggleDay = (idx) =>
    setSendingDays((prev) =>
      prev.includes(idx) ? prev.filter((d) => d !== idx) : [...prev, idx].sort()
    );
  const toggleWeekends = () =>
    setSendingDays((prev) => {
      const weekdays = prev.filter((d) => d <= 4);
      if (includeWeekends) return weekdays;
      return Array.from(new Set([...weekdays, 5, 6])).sort();
    });

  const run = async () => {
    if (!sendingDays.length) {
      toast.error("Pick at least one sending day");
      return;
    }
    setLoading(true);
    setPlan(null);
    try {
      const res = await api.post("/infrastructure/planner/batch", {
        leads: Number(leads) || 1,
        steps: Number(steps) || 1,
        delay_days: Number(delayDays) || 7,
        sending_days: sendingDays,
        start_date: startDate,
        timezone_name: tz,
        accounts: Number(accounts) || 1,
        daily_limit_per_account: Number(perAccount) || 1,
      });
      setPlan(res.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail?.[0]?.msg || e?.response?.data?.detail || "Batch planner failed");
    } finally {
      setLoading(false);
    }
  };

  const downloadExport = async (fmt) => {
    try {
      const res = await axios.post(
        `${API}/infrastructure/planner/batch/export?format=${fmt}`,
        {
          leads: Number(leads) || 1,
          steps: Number(steps) || 1,
          delay_days: Number(delayDays) || 7,
          sending_days: sendingDays,
          start_date: startDate,
          timezone_name: tz,
          accounts: Number(accounts) || 1,
          daily_limit_per_account: Number(perAccount) || 1,
        },
        { withCredentials: true, responseType: "blob" }
      );
      const cd = res.headers["content-disposition"] || "";
      const m = cd.match(/filename="([^"]+)"/);
      const fname = m ? m[1] : `batch_plan.${fmt}`;
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = fname;
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success("Plan exported");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Export failed");
    }
  };

  const dailyCapacity = (Number(accounts) || 0) * (Number(perAccount) || 0);
  const s = plan?.summary;

  return (
    <div className="space-y-4" data-testid="batch-planner-form">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        <PlannerInput label="Total leads" value={leads} onChange={setLeads} testid="batch-leads" min={1} />
        <PlannerInput label="Steps" value={steps} onChange={setSteps} testid="batch-steps" min={1} max={20} />
        <PlannerInput label="Delay between steps (days)" value={delayDays} onChange={setDelayDays} testid="batch-delay" min={1} max={90} />
        <PlannerInput label="Email accounts" value={accounts} onChange={setAccounts} testid="batch-accounts" min={1} />
        <PlannerInput label="Daily limit / account" value={perAccount} onChange={setPerAccount} testid="batch-per-account" min={1} />
        <div>
          <Label className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">
            Start date
          </Label>
          <Input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            data-testid="batch-start-date"
            className="w-44"
          />
        </div>
        <div>
          <Label className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">
            Timezone
          </Label>
          <Input
            value={tz}
            onChange={(e) => setTz(e.target.value)}
            placeholder="e.g. Europe/Dublin"
            className="w-44"
            data-testid="batch-tz"
          />
        </div>
        <div className="flex items-end">
          <div
            className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm w-44"
            data-testid="batch-daily-capacity-readout"
          >
            <div className="text-[10px] uppercase tracking-wider text-slate-500">
              Daily capacity
            </div>
            <div className="font-bold tabular-nums text-slate-900">
              {dailyCapacity.toLocaleString()}
            </div>
          </div>
        </div>
      </div>

      {/* Sending days */}
      <div data-testid="batch-sending-days-row">
        <Label className="text-[11px] uppercase tracking-wider text-slate-500 mb-1 block">
          Sending days
        </Label>
        <div className="flex flex-wrap items-center gap-2">
          {WEEKDAY_NAMES.map((d, idx) => {
            const on = sendingDays.includes(idx);
            return (
              <button
                key={d}
                type="button"
                onClick={() => toggleDay(idx)}
                data-testid={`batch-day-${d.toLowerCase()}`}
                className={`px-3 py-1.5 text-xs font-medium rounded border ${
                  on
                    ? "bg-emerald-600 text-white border-emerald-600"
                    : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                }`}
              >
                {d}
              </button>
            );
          })}
          <button
            type="button"
            onClick={toggleWeekends}
            data-testid="batch-include-weekends"
            className={`ml-2 text-xs font-medium px-3 py-1.5 rounded border ${
              includeWeekends
                ? "bg-amber-50 border-amber-200 text-amber-800"
                : "bg-white border-slate-200 text-slate-600 hover:bg-slate-50"
            }`}
          >
            {includeWeekends ? "Weekends ON" : "Include weekends"}
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          onClick={run}
          disabled={loading}
          className="bg-emerald-600 hover:bg-emerald-700 text-white"
          data-testid="batch-run-btn"
        >
          {loading ? (
            <Loader2 className="mr-2 animate-spin" size={16} />
          ) : (
            <Calculator className="mr-2" size={16} />
          )}
          Build batch plan
        </Button>
        {plan && (
          <>
            <Button
              variant="outline"
              onClick={() => downloadExport("xlsx")}
              data-testid="batch-export-xlsx-btn"
            >
              Export xlsx
            </Button>
            <Button
              variant="outline"
              onClick={() => downloadExport("csv")}
              data-testid="batch-export-csv-btn"
            >
              Export CSV
            </Button>
          </>
        )}
      </div>

      {plan && (
        <div
          data-testid="batch-plan-result"
          className="border border-slate-200 rounded-lg p-4 bg-slate-50/50 space-y-4"
        >
          {/* Status badge */}
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={`px-2.5 py-1 rounded-full text-xs font-semibold ${
                STATUS_PILL[s.status] || "bg-slate-100 text-slate-700"
              }`}
              data-testid={`batch-status-${(s.status || "").replace(/ /g, "-").toLowerCase()}`}
            >
              {s.status}
            </span>
            <span className="text-sm text-slate-600">
              {s.first_send_date} → {s.last_send_date} · {s.duration_days} days
            </span>
          </div>

          {/* Warnings */}
          {plan.warnings?.length > 0 && (
            <ul
              className="space-y-1 text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded p-3"
              data-testid="batch-warnings"
            >
              {plan.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          )}

          {/* Summary cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <PlannerStat label="Total leads" value={s.total_leads} />
            <PlannerStat label="Total batches" value={s.total_batches} highlight />
            <PlannerStat label="Daily capacity" value={s.daily_capacity} />
            <PlannerStat label="Total emails" value={s.total_emails} />
          </div>

          {/* Batch list */}
          <div>
            <Label className="text-[11px] uppercase tracking-wider text-slate-500 mb-1 block">
              Batches
            </Label>
            <div className="flex flex-wrap gap-2" data-testid="batch-list">
              {plan.batches.map((b) => (
                <div
                  key={b.batch}
                  data-testid={`batch-card-${b.batch}`}
                  className="border border-slate-200 rounded px-3 py-2 bg-white text-xs"
                >
                  <div className="font-semibold text-slate-900">Batch {b.batch}</div>
                  <div className="text-slate-600">
                    {b.weekday_name} {b.step_1_date}
                  </div>
                  <div className="text-slate-500">{b.leads.toLocaleString()} leads</div>
                </div>
              ))}
            </div>
          </div>

          {/* Schedule table */}
          <div className="max-h-[440px] overflow-y-auto border border-slate-200 rounded-lg" data-testid="batch-schedule-table">
            <table className="w-full text-sm">
              <thead className="text-xs uppercase tracking-wide text-slate-500 bg-slate-50 sticky top-0">
                <tr>
                  <th className="text-left px-3 py-2 font-medium">Date</th>
                  <th className="text-left px-3 py-2 font-medium">Day</th>
                  <th className="text-right px-3 py-2 font-medium">Batch</th>
                  <th className="text-right px-3 py-2 font-medium">Step</th>
                  <th className="text-right px-3 py-2 font-medium">Leads</th>
                  <th className="text-right px-3 py-2 font-medium">Required</th>
                  <th className="text-right px-3 py-2 font-medium">Available</th>
                  <th className="text-left px-3 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {plan.schedule.map((r, i) => (
                  <tr
                    key={i}
                    className="border-t border-slate-100"
                    data-testid={`batch-row-${r.date}-${r.batch}-${r.step}`}
                  >
                    <td className="px-3 py-1.5 font-medium text-slate-800">{r.date}</td>
                    <td className="px-3 py-1.5 text-slate-600">{r.weekday_name}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{r.batch}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{r.step}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{r.leads.toLocaleString()}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{r.required_capacity.toLocaleString()}</td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{r.available_capacity.toLocaleString()}</td>
                    <td className="px-3 py-1.5">
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                          STATUS_PILL[r.status] || "bg-slate-100 text-slate-700"
                        }`}
                      >
                        {r.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// PHASE A — FORECASTING
// ──────────────────────────────────────────────────────────────────────────
function ForecastSection() {
  const [open, setOpen] = useState(true);
  const [target, setTarget] = useState(1500000);
  const [preferredPerDomain, setPreferredPerDomain] = useState(5);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const run = useCallback(async (t, p) => {
    setLoading(true);
    try {
      const res = await api.get(
        `/infrastructure/forecast?monthly_target=${t}&preferred_inboxes_per_domain=${p}`
      );
      setData(res.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Forecast failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    run(target, preferredPerDomain);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fmt = (n) => (typeof n === "number" ? n.toLocaleString() : "—");

  return (
    <section
      className="bg-white border border-slate-200 rounded-2xl p-4 mb-6"
      data-testid="infra-forecast-section"
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-2"
        data-testid="infra-forecast-toggle"
      >
        <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
          <TrendingUp size={18} className="text-indigo-600" /> Infrastructure Forecast
        </h2>
        {open ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
      </button>

      {open && (
        <div className="mt-4 px-2 space-y-4">
          <p className="text-sm text-slate-500 max-w-3xl">
            Compare your current sending capacity against your monthly target. We&apos;ll
            recommend how many additional inboxes / domains you need to close the gap.
          </p>

          <div className="flex flex-wrap items-end gap-3">
            <div>
              <Label className="text-[11px] uppercase tracking-wider text-slate-500 mb-1 flex items-center gap-1">
                <Target size={12} /> Monthly recipient target
              </Label>
              <Input
                type="number"
                min={0}
                step={50000}
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                className="w-48"
                data-testid="forecast-target-input"
              />
            </div>
            <div>
              <Label className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">
                Preferred Inboxes Per Domain
              </Label>
              <Input
                type="number"
                min={1}
                max={100}
                value={preferredPerDomain}
                onChange={(e) => setPreferredPerDomain(e.target.value)}
                className="w-48"
                data-testid="forecast-preferred-per-domain-input"
              />
            </div>
            <Button
              onClick={() => run(Number(target) || 0, Number(preferredPerDomain) || 5)}
              disabled={loading}
              className="bg-indigo-600 hover:bg-indigo-700 text-white"
              data-testid="forecast-run-btn"
            >
              {loading ? (
                <Loader2 className="mr-2 animate-spin" size={16} />
              ) : (
                <Calculator className="mr-2" size={16} />
              )}
              Recalculate
            </Button>
          </div>

          {data && (
            <div className="space-y-4" data-testid="forecast-result">
              {/* Current snapshot */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <ForecastStat
                  label="Active Domains"
                  value={`${fmt(data.summary.active_domains)} / ${fmt(data.summary.total_domains)}`}
                  testid="forecast-active-domains"
                />
                <ForecastStat
                  label="Active Inboxes"
                  value={`${fmt(data.summary.active_inboxes)} / ${fmt(data.summary.total_inboxes)}`}
                  testid="forecast-active-inboxes"
                />
                <ForecastStat
                  label="Daily Capacity"
                  value={fmt(data.summary.total_daily_capacity)}
                  testid="forecast-daily-capacity"
                />
                <ForecastStat
                  label="Monthly Capacity"
                  value={fmt(data.summary.total_monthly_capacity)}
                  testid="forecast-monthly-capacity"
                />
              </div>

              {/* Capacity windows */}
              <div className="grid grid-cols-3 gap-3">
                <ForecastStat
                  label="Projected next 30 days"
                  value={fmt(data.capacity.next_30_days)}
                  testid="forecast-cap-30"
                />
                <ForecastStat
                  label="Projected next 60 days"
                  value={fmt(data.capacity.next_60_days)}
                  testid="forecast-cap-60"
                />
                <ForecastStat
                  label="Projected next 90 days"
                  value={fmt(data.capacity.next_90_days)}
                  testid="forecast-cap-90"
                />
              </div>

              {/* Gap analysis */}
              <div
                className={`border rounded-xl p-4 ${
                  data.gap.shortfall_monthly > 0
                    ? "border-amber-200 bg-amber-50/60"
                    : "border-emerald-200 bg-emerald-50/60"
                }`}
                data-testid="forecast-gap-card"
              >
                <div className="flex items-center justify-between flex-wrap gap-3">
                  <div>
                    <div className="text-xs uppercase tracking-wider text-slate-500 mb-1">
                      Gap analysis
                    </div>
                    <div className="text-sm text-slate-700">
                      Target{" "}
                      <span className="font-semibold tabular-nums">
                        {fmt(data.gap.target_monthly)}
                      </span>{" "}
                      / month · Current capacity{" "}
                      <span className="font-semibold tabular-nums">
                        {fmt(data.gap.current_monthly)}
                      </span>
                    </div>
                  </div>
                  <div
                    className={`text-2xl font-bold tabular-nums ${
                      data.gap.shortfall_monthly > 0 ? "text-amber-700" : "text-emerald-700"
                    }`}
                    data-testid="forecast-shortfall"
                  >
                    {data.gap.shortfall_monthly > 0
                      ? `-${fmt(data.gap.shortfall_monthly)} short`
                      : "On target"}
                  </div>
                </div>

                {data.gap.shortfall_monthly > 0 && (
                  <div className="mt-3 pt-3 border-t border-amber-200/70 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 text-sm">
                    <div>
                      <div className="text-[11px] uppercase tracking-wider text-slate-500">
                        Add inboxes
                      </div>
                      <div
                        className="font-semibold text-slate-900 tabular-nums"
                        data-testid="forecast-add-inboxes"
                      >
                        +{fmt(data.recommendation.additional_inboxes)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] uppercase tracking-wider text-slate-500">
                        Add domains
                      </div>
                      <div
                        className="font-semibold text-slate-900 tabular-nums"
                        data-testid="forecast-add-domains"
                      >
                        +{fmt(data.recommendation.additional_domains)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] uppercase tracking-wider text-slate-500">
                        Median daily limit
                      </div>
                      <div className="font-semibold text-slate-900 tabular-nums">
                        {fmt(data.recommendation.median_daily_limit)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] uppercase tracking-wider text-slate-500">
                        Monthly / Inbox
                      </div>
                      <div
                        className="font-semibold text-slate-900 tabular-nums"
                        data-testid="forecast-monthly-per-inbox"
                      >
                        {fmt(data.recommendation.monthly_capacity_per_inbox)}
                      </div>
                    </div>
                    <div>
                      <div className="text-[11px] uppercase tracking-wider text-slate-500">
                        Monthly / Domain
                      </div>
                      <div
                        className="font-semibold text-slate-900 tabular-nums"
                        data-testid="forecast-monthly-per-domain"
                      >
                        {fmt(data.recommendation.monthly_capacity_per_domain)}
                      </div>
                    </div>
                    <div className="md:col-span-3 lg:col-span-5 pt-2 border-t border-amber-200/50">
                      <div className="text-[11px] uppercase tracking-wider text-slate-500">
                        Capacity after expansion
                      </div>
                      <div className="font-semibold text-emerald-700 tabular-nums text-lg">
                        {fmt(data.recommendation.estimated_capacity_after_expansion)}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function ForecastStat({ label, value, testid }) {
  return (
    <div
      className="border border-slate-200 rounded-lg p-3 bg-slate-50/40"
      data-testid={testid}
    >
      <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">
        {label}
      </div>
      <div className="text-lg font-semibold text-slate-900 tabular-nums">{value}</div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// PHASE A — DOMAIN TRACKING (Registrar / Expiry / Renewal report)
// ──────────────────────────────────────────────────────────────────────────
function DomainTrackingSection() {
  const [open, setOpen] = useState(true);
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState({ domains: [], counts: {} });
  const [editing, setEditing] = useState(null); // {domain, registrar, purchase_date, expiry_date, renewal_date, notes}
  const [saving, setSaving] = useState(false);
  const [repByDomain, setRepByDomain] = useState({}); // {domain: {score_30d, score_7d, bucket_30d}}

  const fetchDomains = useCallback(async () => {
    setLoading(true);
    try {
      const [domsRes, repRes] = await Promise.all([
        api.get("/infrastructure/domains"),
        api.get("/infrastructure/reputation").catch(() => ({ data: { domains: [] } })),
      ]);
      setData(domsRes.data || { domains: [], counts: {} });
      const map = {};
      for (const d of repRes.data?.domains || []) {
        map[d.domain] = d;
      }
      setRepByDomain(map);
    } catch (e) {
      toast.error("Failed to load tracked domains");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDomains();
  }, [fetchDomains]);

  const save = async () => {
    if (!editing?.domain) {
      toast.error("Domain is required");
      return;
    }
    setSaving(true);
    try {
      await api.post("/infrastructure/domains", {
        domain: editing.domain.trim().toLowerCase(),
        registrar: editing.registrar || null,
        purchase_date: editing.purchase_date || null,
        expiry_date: editing.expiry_date || null,
        renewal_date: editing.renewal_date || null,
        notes: editing.notes || null,
      });
      toast.success("Domain saved");
      setEditing(null);
      fetchDomains();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const removeDomain = async (dom) => {
    if (!window.confirm(`Stop tracking ${dom}?`)) return;
    try {
      await api.delete(`/infrastructure/domains/${dom}`);
      toast.success("Removed");
      fetchDomains();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Delete failed");
    }
  };

  const downloadRenewal = async (format) => {
    try {
      const res = await axios.get(
        `${API}/infrastructure/domains/renewal-report?format=${format}`,
        { withCredentials: true, responseType: "blob" }
      );
      const cd = res.headers["content-disposition"] || "";
      const m = cd.match(/filename="([^"]+)"/);
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = m ? m[1] : `renewal-report.${format}`;
      a.click();
      window.URL.revokeObjectURL(url);
      toast.success("Renewal report downloaded");
    } catch {
      toast.error("Export failed");
    }
  };

  const bucketStyle = (days) => {
    if (days === null || days === undefined) return "bg-slate-100 text-slate-600";
    if (days < 0) return "bg-red-100 text-red-700";
    if (days <= 7) return "bg-red-100 text-red-700";
    if (days <= 30) return "bg-amber-100 text-amber-700";
    if (days <= 60) return "bg-amber-50 text-amber-600";
    if (days <= 90) return "bg-sky-50 text-sky-700";
    return "bg-emerald-50 text-emerald-700";
  };

  const bucketLabel = (days) => {
    if (days === null || days === undefined) return "No expiry set";
    if (days < 0) return `Expired ${Math.abs(days)}d ago`;
    return `${days} days left`;
  };

  const c = data.counts || {};

  return (
    <section
      className="bg-white border border-slate-200 rounded-2xl p-4 mb-6"
      data-testid="infra-domain-tracking-section"
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-2"
        data-testid="infra-domain-tracking-toggle"
      >
        <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
          <Globe size={18} className="text-amber-600" /> Domain Tracking & Expiry
        </h2>
        {open ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
      </button>

      {open && (
        <div className="mt-4 px-2">
          {/* Bucket cards */}
          <div className="grid grid-cols-2 md:grid-cols-6 gap-2 mb-4">
            <BucketCard label="Total tracked" value={c.total ?? 0} tone="slate" testid="dom-bucket-total" />
            <BucketCard label="Healthy" value={(c.active ?? 0) - ((c.expiring_90 ?? 0) + (c.expiring_60 ?? 0) + (c.expiring_30 ?? 0) + (c.expiring_7 ?? 0))} tone="emerald" testid="dom-bucket-healthy" />
            <BucketCard label="≤ 90 days" value={c.expiring_90 ?? 0} tone="sky" testid="dom-bucket-90" />
            <BucketCard label="≤ 60 days" value={c.expiring_60 ?? 0} tone="amber" testid="dom-bucket-60" />
            <BucketCard label="≤ 30 days" value={c.expiring_30 ?? 0} tone="amber" testid="dom-bucket-30" />
            <BucketCard label="Expired / ≤ 7 days" value={(c.expired ?? 0) + (c.expiring_7 ?? 0)} tone="rose" testid="dom-bucket-critical" />
          </div>

          {/* Toolbar */}
          <div className="flex flex-wrap items-center gap-2 mb-3">
            <Button
              onClick={() =>
                setEditing({ domain: "", registrar: "", purchase_date: "", expiry_date: "", renewal_date: "", notes: "" })
              }
              className="bg-amber-600 hover:bg-amber-700 text-white"
              data-testid="dom-add-btn"
            >
              <Plus size={16} className="mr-1.5" /> Track Domain
            </Button>
            <Button
              variant="outline"
              onClick={() => downloadRenewal("xlsx")}
              data-testid="dom-renewal-xlsx"
            >
              <Download size={16} className="mr-1.5" /> Renewal Report (xlsx)
            </Button>
            <Button
              variant="outline"
              onClick={() => downloadRenewal("csv")}
              data-testid="dom-renewal-csv"
            >
              <FileText size={16} className="mr-1.5" /> CSV
            </Button>
          </div>

          {/* Table */}
          {loading ? (
            <div className="py-8 text-center text-sm text-slate-500" data-testid="dom-loading">
              <Loader2 className="inline-block animate-spin mr-2" size={14} /> Loading…
            </div>
          ) : data.domains.length === 0 ? (
            <div className="px-2 py-8 text-sm text-slate-500 text-center border border-dashed border-slate-200 rounded-lg" data-testid="dom-empty">
              No domains tracked yet. Click <span className="font-medium">Track Domain</span> to add one.
            </div>
          ) : (
            <div className="overflow-x-auto border border-slate-200 rounded-lg">
              <table className="min-w-full text-sm" data-testid="dom-table">
                <thead className="bg-slate-50 text-slate-600 uppercase text-[11px] tracking-wider">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium">Domain</th>
                    <th className="text-left px-3 py-2 font-medium">Registrar</th>
                    <th className="text-left px-3 py-2 font-medium">Purchased</th>
                    <th className="text-left px-3 py-2 font-medium">Expires</th>
                    <th className="text-right px-3 py-2 font-medium">Age (d)</th>
                    <th className="text-left px-3 py-2 font-medium">Reputation</th>
                    <th className="text-left px-3 py-2 font-medium">Status</th>
                    <th className="text-right px-3 py-2 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {data.domains.map((d) => (
                    <tr
                      key={d.domain}
                      className="border-t border-slate-100"
                      data-testid={`dom-row-${d.domain}`}
                    >
                      <td className="px-3 py-2 font-medium text-slate-800">{d.domain}</td>
                      <td className="px-3 py-2 text-slate-600">{d.registrar || "—"}</td>
                      <td className="px-3 py-2 text-slate-600">{d.purchase_date || "—"}</td>
                      <td className="px-3 py-2 text-slate-600">{d.expiry_date || "—"}</td>
                      <td className="px-3 py-2 text-right tabular-nums text-slate-600">
                        {d.days_in_infrastructure ?? "—"}
                      </td>
                      <td className="px-3 py-2" data-testid={`dom-rep-${d.domain}`}>
                        <ReputationBadge rep={repByDomain[d.domain]} />
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={`px-2 py-0.5 rounded-full text-xs font-medium ${bucketStyle(
                            d.days_to_expiry
                          )}`}
                        >
                          {bucketLabel(d.days_to_expiry)}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right">
                        <button
                          onClick={() => setEditing({ ...d })}
                          className="text-slate-500 hover:text-slate-900 mr-2"
                          data-testid={`dom-edit-${d.domain}`}
                          title="Edit"
                        >
                          <Edit2 size={14} />
                        </button>
                        <button
                          onClick={() => removeDomain(d.domain)}
                          className="text-rose-500 hover:text-rose-700"
                          data-testid={`dom-delete-${d.domain}`}
                          title="Delete"
                        >
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Edit / Add dialog */}
          <Dialog open={!!editing} onOpenChange={(v) => !v && setEditing(null)}>
            <DialogContent data-testid="dom-edit-dialog">
              <DialogHeader>
                <DialogTitle>
                  {editing?.domain_id ? `Edit ${editing.domain}` : "Track a domain"}
                </DialogTitle>
              </DialogHeader>
              {editing && (
                <div className="space-y-3">
                  <div>
                    <Label className="text-xs text-slate-500">Domain *</Label>
                    <Input
                      value={editing.domain || ""}
                      onChange={(e) => setEditing({ ...editing, domain: e.target.value })}
                      placeholder="example.com"
                      disabled={!!editing.domain_id}
                      data-testid="dom-form-domain"
                    />
                  </div>
                  <div>
                    <Label className="text-xs text-slate-500">Registrar</Label>
                    <Input
                      value={editing.registrar || ""}
                      onChange={(e) => setEditing({ ...editing, registrar: e.target.value })}
                      placeholder="GoDaddy, Namecheap, Cloudflare…"
                      data-testid="dom-form-registrar"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <Label className="text-xs text-slate-500">Purchase date</Label>
                      <Input
                        type="date"
                        value={editing.purchase_date || ""}
                        onChange={(e) => setEditing({ ...editing, purchase_date: e.target.value })}
                        data-testid="dom-form-purchase"
                      />
                    </div>
                    <div>
                      <Label className="text-xs text-slate-500">Expiry date</Label>
                      <Input
                        type="date"
                        value={editing.expiry_date || ""}
                        onChange={(e) => setEditing({ ...editing, expiry_date: e.target.value })}
                        data-testid="dom-form-expiry"
                      />
                    </div>
                  </div>
                  <div>
                    <Label className="text-xs text-slate-500">Renewal date</Label>
                    <Input
                      type="date"
                      value={editing.renewal_date || ""}
                      onChange={(e) => setEditing({ ...editing, renewal_date: e.target.value })}
                      data-testid="dom-form-renewal"
                    />
                  </div>
                  <div>
                    <Label className="text-xs text-slate-500">Notes</Label>
                    <Input
                      value={editing.notes || ""}
                      onChange={(e) => setEditing({ ...editing, notes: e.target.value })}
                      placeholder="Optional"
                      data-testid="dom-form-notes"
                    />
                  </div>
                </div>
              )}
              <DialogFooter>
                <Button variant="outline" onClick={() => setEditing(null)} data-testid="dom-form-cancel">
                  Cancel
                </Button>
                <Button
                  onClick={save}
                  disabled={saving}
                  className="bg-amber-600 hover:bg-amber-700 text-white"
                  data-testid="dom-form-save"
                >
                  {saving ? <Loader2 className="mr-2 animate-spin" size={14} /> : null}
                  Save
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      )}
    </section>
  );
}

function BucketCard({ label, value, tone = "slate", testid }) {
  const tones = {
    slate: "border-slate-200 bg-slate-50/60 text-slate-900",
    emerald: "border-emerald-200 bg-emerald-50/60 text-emerald-800",
    sky: "border-sky-200 bg-sky-50/60 text-sky-800",
    amber: "border-amber-200 bg-amber-50/60 text-amber-800",
    rose: "border-rose-200 bg-rose-50/60 text-rose-800",
  };
  return (
    <div
      className={`border rounded-lg px-3 py-2 ${tones[tone] || tones.slate}`}
      data-testid={testid}
    >
      <div className="text-[10px] uppercase tracking-wider opacity-70">{label}</div>
      <div className="text-xl font-bold tabular-nums">{value}</div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// PHASE B — REPLACEMENT SECTION (recent activity + auto-scan trigger)
// ──────────────────────────────────────────────────────────────────────────
function ReplacementSection({ onRequestReplace }) {
  const [open, setOpen] = useState(true);
  const [items, setItems] = useState([]);
  const [counts, setCounts] = useState({});
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [atRisk, setAtRisk] = useState([]);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [hist, inb] = await Promise.all([
        api.get("/infrastructure/replacements?limit=5"),
        api.get("/infrastructure/inboxes?status=paused,risky"),
      ]);
      setItems(hist.data?.items || []);
      setCounts(hist.data?.counts || {});
      const at = (inb.data?.inboxes || []).filter((r) => r.active_campaign_count > 0);
      setAtRisk(at);
    } catch {
      // silent — section degrades gracefully
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const runScan = async () => {
    setScanning(true);
    try {
      const res = await api.post("/infrastructure/replacements/auto-scan");
      const c = res.data?.completed?.length || 0;
      const n = res.data?.no_candidate?.length || 0;
      if (c === 0 && n === 0) toast.message("No at-risk inboxes found");
      else toast.success(`Auto-scan complete — ${c} replaced${n ? `, ${n} unresolved` : ""}`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Auto-scan failed");
    } finally {
      setScanning(false);
    }
  };

  return (
    <section
      className="bg-white border border-slate-200 rounded-2xl p-4 mt-6"
      data-testid="infra-replacement-section"
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-2"
        data-testid="infra-replacement-toggle"
      >
        <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
          <RefreshCcw size={18} className="text-violet-600" /> Automatic Infrastructure Replacement
        </h2>
        {open ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
      </button>

      {open && (
        <div className="mt-4 px-2 space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <BucketCard label="At-risk in campaigns" value={atRisk.length} tone="rose" testid="rep-atrisk" />
            <BucketCard label="Replacements logged" value={items.length > 0 ? (counts.completed || 0) + (counts.no_candidate || 0) + (counts.failed || 0) : 0} tone="slate" testid="rep-logged" />
            <BucketCard label="Completed" value={counts.completed || 0} tone="emerald" testid="rep-completed" />
            <BucketCard label="No candidate" value={counts.no_candidate || 0} tone="amber" testid="rep-nocand" />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              onClick={runScan}
              disabled={scanning}
              className="bg-violet-600 hover:bg-violet-700 text-white"
              data-testid="rep-scan-btn"
            >
              {scanning ? <Loader2 className="mr-2 animate-spin" size={14} /> : <Wand2 className="mr-2" size={14} />}
              Scan & Auto-Replace
            </Button>
            <Button
              variant="outline"
              onClick={() => navigate("/infrastructure/replacements")}
              data-testid="rep-history-link"
            >
              View full history →
            </Button>
          </div>

          {atRisk.length > 0 && (
            <div className="border border-rose-200 bg-rose-50/40 rounded-lg p-3" data-testid="rep-atrisk-list">
              <div className="text-[11px] uppercase tracking-wider text-rose-700 mb-2 flex items-center gap-1">
                <AlertTriangle size={12} /> At-risk inboxes currently in campaigns
              </div>
              <ul className="space-y-1 text-sm">
                {atRisk.slice(0, 5).map((r) => (
                  <li key={r.account_id} className="flex items-center justify-between">
                    <span>
                      <span className="font-medium text-slate-900">{r.email}</span>
                      <span className="text-slate-500 text-xs ml-2">
                        {r.status} · {r.active_campaign_count} active
                      </span>
                    </span>
                    <button
                      onClick={() => onRequestReplace(r)}
                      className="text-violet-600 hover:text-violet-700 text-xs font-medium inline-flex items-center gap-1"
                      data-testid={`rep-row-replace-${r.account_id}`}
                    >
                      <RefreshCcw size={11} /> Replace
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Recent activity */}
          <div>
            <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-2">
              Recent activity
            </div>
            {loading ? (
              <div className="py-4 text-center text-xs text-slate-500" data-testid="rep-section-loading">
                <Loader2 className="inline-block animate-spin mr-2" size={12} /> Loading…
              </div>
            ) : items.length === 0 ? (
              <div className="py-4 text-center text-xs text-slate-500 border border-dashed border-slate-200 rounded-lg" data-testid="rep-section-empty">
                No replacements yet.
              </div>
            ) : (
              <ul className="divide-y divide-slate-100 border border-slate-200 rounded-lg" data-testid="rep-recent-list">
                {items.map((it) => (
                  <li
                    key={it.replacement_id}
                    className="px-3 py-2 text-sm flex items-center justify-between"
                    data-testid={`rep-recent-${it.replacement_id}`}
                  >
                    <div>
                      <span className="font-medium text-slate-900">{it.replaced_email}</span>
                      <span className="text-slate-400 mx-1">→</span>
                      <span className="font-medium text-slate-900">
                        {it.replacement_email || <span className="italic text-slate-400">—</span>}
                      </span>
                      <span className="text-xs text-slate-500 ml-2">
                        {it.reason} · {it.triggered_by}
                      </span>
                    </div>
                    <span
                      className={`text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full ${
                        it.status === "completed"
                          ? "bg-emerald-100 text-emerald-700"
                          : it.status === "no_candidate"
                          ? "bg-amber-100 text-amber-700"
                          : "bg-rose-100 text-rose-700"
                      }`}
                    >
                      {it.status}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </section>
  );
}


// ──────────────────────────────────────────────────────────────────────────
// PHASE C — REPUTATION SUMMARY CARD + DOMAIN REPUTATION BADGE
// ──────────────────────────────────────────────────────────────────────────
function scoreColor(score) {
  if (score === null || score === undefined) return "bg-slate-100 text-slate-500";
  if (score >= 80) return "bg-emerald-100 text-emerald-700";
  if (score >= 60) return "bg-sky-100 text-sky-700";
  if (score >= 40) return "bg-amber-100 text-amber-700";
  if (score >= 20) return "bg-orange-100 text-orange-700";
  return "bg-rose-100 text-rose-700";
}

function ReputationBadge({ rep }) {
  if (!rep) return <span className="text-slate-400 italic text-xs">no data</span>;
  return (
    <div className="flex flex-col gap-0.5">
      <span
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold w-fit ${scoreColor(
          rep.score_30d
        )}`}
        title="30-day score"
      >
        <ShieldCheck size={11} />
        {Number(rep.score_30d ?? 0).toFixed(0)} / 100
      </span>
      <span className="text-[10px] text-slate-500">
        7-day: {Number(rep.score_7d ?? 0).toFixed(0)}
      </span>
    </div>
  );
}

function ReputationSummaryCard() {
  const [open, setOpen] = useState(true);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/infrastructure/reputation");
      setData(res.data);
    } catch (e) {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const recompute = async () => {
    setRecomputing(true);
    try {
      const r = await api.post("/infrastructure/reputation/recompute");
      toast.success(`Recomputed ${r.data?.domain_count || 0} domains`);
      load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Recompute failed");
    } finally {
      setRecomputing(false);
    }
  };

  const s = data?.summary || {};

  return (
    <section
      className="bg-white border border-slate-200 rounded-2xl p-4 mb-6"
      data-testid="infra-reputation-section"
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-2"
        data-testid="infra-reputation-toggle"
      >
        <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
          <ShieldCheck size={18} className="text-emerald-600" /> Domain Reputation
          {data?.stale && (
            <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700">
              recomputing…
            </span>
          )}
        </h2>
        {open ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
      </button>

      {open && (
        <div className="mt-4 px-2 space-y-4">
          {loading ? (
            <div className="py-6 text-sm text-slate-500 text-center" data-testid="rep-summary-loading">
              <Loader2 className="inline-block animate-spin mr-2" size={14} /> Loading…
            </div>
          ) : !data || data.domains.length === 0 ? (
            <div className="py-6 text-sm text-slate-500 text-center border border-dashed border-slate-200 rounded-lg" data-testid="rep-summary-empty">
              No reputation data yet. Click <span className="font-medium">Recompute</span> to build the cache.
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <ScoreCard label="Average — 30 days" value={s.avg_score_30d} testid="rep-avg-30d" />
                <ScoreCard label="Average — 7 days" value={s.avg_score_7d} testid="rep-avg-7d" />
                <BucketCard label="Domains tracked" value={s.total_domains || 0} tone="slate" testid="rep-total-domains" />
                <BucketCard
                  label="Critical / Poor"
                  value={(s.buckets?.critical || 0) + (s.buckets?.poor || 0)}
                  tone="rose"
                  testid="rep-poor-count"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="border border-rose-200 bg-rose-50/40 rounded-lg p-3" data-testid="rep-worst">
                  <div className="text-[11px] uppercase tracking-wider text-rose-700 mb-2 flex items-center gap-1">
                    <AlertCircle size={12} /> Worst-performing
                  </div>
                  {(s.worst || []).length === 0 ? (
                    <div className="text-xs text-slate-500">—</div>
                  ) : (
                    <ul className="text-sm space-y-1">
                      {s.worst.map((w) => (
                        <li key={`worst-${w.domain}`} className="flex justify-between items-center">
                          <span className="font-medium text-slate-900">{w.domain}</span>
                          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${scoreColor(w.score_30d)}`}>
                            {Number(w.score_30d).toFixed(0)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div className="border border-emerald-200 bg-emerald-50/40 rounded-lg p-3" data-testid="rep-best">
                  <div className="text-[11px] uppercase tracking-wider text-emerald-700 mb-2 flex items-center gap-1">
                    <CheckCircle2 size={12} /> Best-performing
                  </div>
                  {(s.best || []).length === 0 ? (
                    <div className="text-xs text-slate-500">—</div>
                  ) : (
                    <ul className="text-sm space-y-1">
                      {s.best.map((b) => (
                        <li key={`best-${b.domain}`} className="flex justify-between items-center">
                          <span className="font-medium text-slate-900">{b.domain}</span>
                          <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${scoreColor(b.score_30d)}`}>
                            {Number(b.score_30d).toFixed(0)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </>
          )}

          <div className="flex items-center justify-between text-xs text-slate-500">
            <span>
              Score formula: Reply 50% · Bounce 20% · Age 10% · Warmup 10% · Unsub 5% · Errors 5%
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={recompute}
              disabled={recomputing}
              data-testid="rep-recompute-btn"
            >
              {recomputing ? <Loader2 className="mr-1.5 animate-spin" size={12} /> : <RefreshCcw className="mr-1.5" size={12} />}
              Recompute
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}

function ScoreCard({ label, value, testid }) {
  const s = Number(value || 0);
  return (
    <div
      className={`border rounded-lg p-3 ${scoreColor(s)} bg-opacity-50`}
      data-testid={testid}
    >
      <div className="text-[10px] uppercase tracking-wider opacity-70">{label}</div>
      <div className="text-3xl font-bold tabular-nums">{s.toFixed(1)}</div>
      <div className="text-[10px] opacity-70">/ 100</div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// PHASE C — INLINE ISSUES DASHBOARD CARD
// ──────────────────────────────────────────────────────────────────────────
function IssuesDashboardCard() {
  const [open, setOpen] = useState(true);
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState({ counts: {}, paused: [], risky: [], errored: [] });
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get("/infrastructure/issues");
      setData(res.data);
    } catch (e) {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const cards = [
    { label: "Paused", count: data.counts.paused || 0, tone: "amber" },
    { label: "Risky", count: data.counts.risky || 0, tone: "rose" },
    { label: "Errored", count: data.counts.errored || 0, tone: "slate" },
  ];

  return (
    <section
      className="bg-white border border-slate-200 rounded-2xl p-4 mt-6"
      data-testid="infra-issues-section"
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-2"
        data-testid="infra-issues-toggle"
      >
        <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
          <AlertCircle size={18} className="text-rose-600" /> Issues Dashboard
        </h2>
        {open ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
      </button>

      {open && (
        <div className="mt-4 px-2 space-y-4">
          <div className="grid grid-cols-3 gap-3">
            {cards.map((c) => (
              <BucketCard
                key={c.label}
                label={c.label}
                value={c.count}
                tone={c.tone}
                testid={`issue-bucket-${c.label.toLowerCase()}`}
              />
            ))}
          </div>

          <div className="flex items-center justify-between">
            <p className="text-xs text-slate-500">
              {loading
                ? "Loading…"
                : (data.counts.total || 0) === 0
                ? "Everything looks healthy."
                : `${data.counts.total} inboxes need attention.`}
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate("/infrastructure/issues")}
              data-testid="issues-page-link"
            >
              Open Issues Dashboard →
            </Button>
          </div>

          {!loading && (data.counts.total || 0) > 0 && (
            <ul className="divide-y divide-slate-100 border border-slate-200 rounded-lg" data-testid="issues-preview-list">
              {[...data.paused, ...data.risky, ...data.errored].slice(0, 5).map((r) => (
                <li
                  key={`issue-${r.account_id}`}
                  className="px-3 py-2 text-sm flex items-center justify-between"
                  data-testid={`issue-preview-${r.account_id}`}
                >
                  <div>
                    <span className="font-medium text-slate-900">{r.email}</span>
                    <span className="text-slate-500 text-xs ml-2">
                      {r.domain} · {r.status} · {r.active_campaign_count} active
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}

