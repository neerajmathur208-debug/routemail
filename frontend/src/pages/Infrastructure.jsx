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
      <main className="flex-1 lg:ml-64 p-6 lg:p-10 max-w-[1500px]">
        {/* Header */}
        <div className="flex items-start justify-between flex-wrap gap-4 mb-8">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Network className="text-sky-600" size={28} strokeWidth={1.5} />
              <h1 className="text-3xl font-bold text-slate-900">Infrastructure</h1>
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
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => downloadExport("inboxes", "xlsx")}
              data-testid="infra-export-inboxes-xlsx"
            >
              <FileSpreadsheet size={16} className="mr-1.5" /> Inbox Inventory (xlsx)
            </Button>
            <Button
              variant="outline"
              onClick={() => downloadExport("inboxes", "csv")}
              data-testid="infra-export-inboxes-csv"
            >
              <FileText size={16} className="mr-1.5" /> CSV
            </Button>
            <Button
              variant="outline"
              onClick={() => downloadExport("domains", "xlsx")}
              data-testid="infra-export-domains-xlsx"
            >
              <FileSpreadsheet size={16} className="mr-1.5" /> Domain Inventory
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

        {/* Inbox table + filters */}
        <section
          className="bg-white border border-slate-200 rounded-2xl p-4"
          data-testid="infra-inbox-section"
        >
          <div className="flex items-center justify-between mb-3 px-2 flex-wrap gap-3">
            <h2 className="text-lg font-semibold text-slate-900 flex items-center gap-2">
              <Inbox size={18} className="text-sky-600" /> Inbox Availability
            </h2>
            <div className="text-xs text-slate-500">{inboxes.length} inboxes shown</div>
          </div>

          {/* Filter row */}
          <div
            className="flex flex-wrap items-end gap-2 mb-4 px-2"
            data-testid="infra-filter-row"
          >
            <div className="relative">
              <Search
                size={14}
                className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"
              />
              <Input
                placeholder="Search email"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8 w-56"
                data-testid="infra-search-input"
              />
            </div>
            <FilterSelect
              label="Ownership"
              value={ownership}
              onChange={setOwnership}
              options={filterOptions.ownership}
              testid="infra-filter-ownership"
            />
            <FilterSelect
              label="Domain"
              value={domain}
              onChange={setDomain}
              options={filterOptions.domain}
              testid="infra-filter-domain"
            />
            <FilterSelect
              label="Status"
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                "Available",
                "Partially Available",
                "Fully Reserved",
                "Warming Up",
                "Paused",
                "Risky",
              ]}
              testid="infra-filter-status"
            />
            <FilterSelect
              label="Warmup"
              value={warmupFilter}
              onChange={setWarmupFilter}
              options={["Active", "Warming", "—"]}
              testid="infra-filter-warmup"
            />
            <div className="flex flex-col">
              <Label className="text-[11px] uppercase tracking-wider text-slate-500 mb-1">
                Min remaining
              </Label>
              <Select value={minRemaining} onValueChange={setMinRemaining}>
                <SelectTrigger className="w-28" data-testid="infra-filter-min-remaining">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="0">Any</SelectItem>
                  <SelectItem value="10">≥ 10</SelectItem>
                  <SelectItem value="25">≥ 25</SelectItem>
                  <SelectItem value="50">≥ 50</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={resetFilters}
              data-testid="infra-reset-filters"
              className="mb-0.5"
            >
              <Filter size={14} className="mr-1" /> Reset
            </Button>
          </div>

          {loading ? (
            <div className="py-12 text-center text-slate-500" data-testid="infra-loading">
              <Loader2 className="inline animate-spin mr-2" size={16} /> Loading…
            </div>
          ) : inboxes.length === 0 ? (
            <div className="py-12 text-center text-slate-500" data-testid="infra-empty">
              No inboxes match the current filters.
            </div>
          ) : (
            <div className="overflow-x-auto" data-testid="infra-inbox-table">
              <table className="w-full text-sm">
                <thead className="text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium">Email</th>
                    <th className="text-left px-3 py-2 font-medium">Domain</th>
                    <th className="text-left px-3 py-2 font-medium">Ownership</th>
                    <th className="text-left px-3 py-2 font-medium">Workspace</th>
                    <th className="text-left px-3 py-2 font-medium">Status</th>
                    <th className="text-right px-3 py-2 font-medium">Sent / Limit</th>
                    <th className="text-right px-3 py-2 font-medium">Remaining</th>
                    <th className="text-right px-3 py-2 font-medium">Projected (120d)</th>
                    <th className="text-right px-3 py-2 font-medium">Campaigns</th>
                    <th className="text-left px-3 py-2 font-medium">Warmup</th>
                    <th className="text-left px-3 py-2 font-medium">Last Activity</th>
                    <th className="text-right px-3 py-2 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {inboxes.map((r) => (
                    <tr
                      key={r.account_id}
                      className="border-t border-slate-100 hover:bg-slate-50"
                      data-testid={`inbox-row-${r.account_id}`}
                    >
                      <td className="px-3 py-2 font-medium text-slate-900">
                        <button
                          onClick={() => setCalendarFor(r)}
                          className="hover:text-sky-700 hover:underline text-left"
                          data-testid={`inbox-open-calendar-${r.account_id}`}
                        >
                          {r.email}
                        </button>
                      </td>
                      <td className="px-3 py-2 text-slate-600">{r.domain}</td>
                      <td className="px-3 py-2 text-slate-700">
                        {r.ownership || (
                          <span className="text-slate-400 italic">none</span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-slate-600 truncate max-w-[180px]">
                        {r.workspace}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          data-testid={`inbox-status-${r.account_id}`}
                          className={`px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${
                            STATUS_COLOR[r.status] || "bg-slate-100 text-slate-700"
                          }`}
                        >
                          {r.status}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-slate-700">
                        {r.emails_sent_today}/{r.daily_limit}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums font-semibold">
                        {r.remaining_capacity}
                      </td>
                      <td
                        className="px-3 py-2 text-right tabular-nums text-slate-700"
                        data-testid={`inbox-projected-${r.account_id}`}
                      >
                        {(r.projected_window_total || 0).toLocaleString()}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {r.active_campaign_count}
                      </td>
                      <td className="px-3 py-2 text-slate-600">{r.warmup_status}</td>
                      <td className="px-3 py-2 text-xs text-slate-500 whitespace-nowrap">
                        {r.last_activity_at ? r.last_activity_at.slice(0, 10) : "—"}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            title="View 120-day calendar"
                            data-testid={`inbox-calendar-btn-${r.account_id}`}
                            onClick={() => setCalendarFor(r)}
                          >
                            <CalendarDays size={14} />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            title="Edit ownership"
                            data-testid={`inbox-edit-ownership-${r.account_id}`}
                            onClick={() =>
                              setOwnerEdit({
                                account_id: r.account_id,
                                email: r.email,
                                ownership: r.ownership || "",
                              })
                            }
                          >
                            <Edit2 size={14} />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
  const [leads, setLeads] = useState(10000);
  const [steps, setSteps] = useState(3);
  const [days, setDays] = useState(30);
  const [sdpw, setSdpw] = useState(5);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const run = async () => {
    setLoading(true);
    setResult(null);
    try {
      const res = await api.post("/infrastructure/planner", {
        leads: Number(leads) || 1,
        steps: Number(steps) || 1,
        duration_days: Number(days) || 1,
        sending_days_per_week: Number(sdpw) || 5,
      });
      setResult(res.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail?.[0]?.msg || e?.response?.data?.detail || "Planner failed");
    } finally {
      setLoading(false);
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

          <div className="flex flex-wrap items-end gap-3">
            <PlannerInput label="Leads" value={leads} onChange={setLeads} testid="planner-leads" min={1} />
            <PlannerInput label="Steps" value={steps} onChange={setSteps} testid="planner-steps" min={1} max={20} />
            <PlannerInput label="Duration (days)" value={days} onChange={setDays} testid="planner-days" min={1} max={365} />
            <PlannerInput label="Sending days / week" value={sdpw} onChange={setSdpw} testid="planner-sdpw" min={1} max={7} />
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
                <PlannerStat label="Available Inboxes" value={o?.available_inboxes} />
                <PlannerStat label="Additional Needed" value={o?.additional_inboxes_required} testid="planner-additional-needed" />
                <PlannerStat label="Median Daily Limit" value={o?.median_daily_limit} />
                <PlannerStat label="Capacity Today" value={o?.available_capacity_today} />
                <PlannerStat label="Capacity Window (120d)" value={o?.available_capacity_window} />
              </div>
            </div>
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
