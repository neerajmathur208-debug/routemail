import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  ArrowLeft,
  Inbox as InboxIcon,
  Search,
  Loader2,
  FileSpreadsheet,
  FileText,
  ChevronLeft,
  ChevronRight,
  CalendarDays,
  CheckCircle2,
  AlertTriangle,
  Pause,
} from "lucide-react";
import Sidebar from "../components/Sidebar";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { api, API } from "../App";
import { toast } from "sonner";
import axios from "axios";

const PAGE_SIZES = [25, 50, 100, 250];

const STATUS_PILL = {
  "Available": "bg-emerald-50 text-emerald-700 border border-emerald-200",
  "Partially Available": "bg-sky-50 text-sky-700 border border-sky-200",
  "In Use": "bg-amber-50 text-amber-700 border border-amber-200",
  "Fully Reserved": "bg-amber-50 text-amber-700 border border-amber-200",
  "Warming Up": "bg-violet-50 text-violet-700 border border-violet-200",
  "Paused": "bg-slate-100 text-slate-700 border border-slate-200",
  "Risky": "bg-rose-50 text-rose-700 border border-rose-200",
};

const STATUS_ICONS = {
  "Available": CheckCircle2,
  "Partially Available": CheckCircle2,
  "In Use": CalendarDays,
  "Fully Reserved": CalendarDays,
  "Warming Up": CalendarDays,
  "Paused": Pause,
  "Risky": AlertTriangle,
};

export default function InfrastructureInboxes({ user, setUser }) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState({ inboxes: [], filter_options: {}, total: 0 });
  const [filters, setFilters] = useState({
    ownership: "",
    domain: "",
    status: "",
    warmup_status: "",
    min_remaining: "",
    search: "",
  });
  const [searchInput, setSearchInput] = useState("");
  const [sortBy, setSortBy] = useState("email");
  const [sortDir, setSortDir] = useState("asc");
  const [limit, setLimit] = useState(50);
  const [skip, setSkip] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const p = new URLSearchParams();
      if (filters.ownership) p.set("ownership", filters.ownership);
      if (filters.domain) p.set("domain", filters.domain);
      if (filters.status) p.set("status", filters.status);
      if (filters.warmup_status) p.set("warmup_status", filters.warmup_status);
      if (filters.min_remaining) p.set("min_remaining", filters.min_remaining);
      if (filters.search) p.set("search", filters.search);
      p.set("sort_by", sortBy);
      p.set("sort_dir", sortDir);
      p.set("limit", String(limit));
      p.set("skip", String(skip));
      const res = await api.get(`/infrastructure/inboxes?${p}`);
      setData(res.data);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to load inboxes");
    } finally {
      setLoading(false);
    }
  }, [filters, sortBy, sortDir, limit, skip]);

  useEffect(() => {
    load();
  }, [load]);

  const onSearch = (e) => {
    e.preventDefault();
    setSkip(0);
    setFilters({ ...filters, search: searchInput });
  };

  const reset = () => {
    setFilters({ ownership: "", domain: "", status: "", warmup_status: "", min_remaining: "", search: "" });
    setSearchInput("");
    setSortBy("email");
    setSortDir("asc");
    setLimit(50);
    setSkip(0);
  };

  const exportFile = async (fmt) => {
    try {
      const res = await axios.get(
        `${API}/infrastructure/accounts/export?format=${fmt}`,
        { withCredentials: true, responseType: "blob" }
      );
      const cd = res.headers["content-disposition"] || "";
      const m = cd.match(/filename="([^"]+)"/);
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = m ? m[1] : `inboxes.${fmt}`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      toast.error("Export failed");
    }
  };

  const opts = data.filter_options || {};
  const rows = data.inboxes || [];

  return (
    <div className="flex bg-slate-50 min-h-screen">
      <Sidebar user={user} setUser={setUser} />
      <main className="flex-1 lg:ml-64 p-4 sm:p-6 lg:p-8 max-w-[1500px]">
        <div className="mb-4">
          <Link
            to="/infrastructure"
            className="text-sm text-slate-500 hover:text-slate-900 inline-flex items-center gap-1 mb-2"
            data-testid="inbox-back-link"
          >
            <ArrowLeft size={14} /> Back to Infrastructure
          </Link>
          <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 flex items-center gap-2">
            <InboxIcon className="text-indigo-600" size={24} strokeWidth={1.5} />
            Inbox Availability
          </h1>
          <p className="text-sm text-slate-500 max-w-2xl mt-1">
            Every email account in your workspace with today's remaining capacity and 120-day projected reserve.
            Filter, sort, and export for capacity audits.
          </p>
        </div>

        {/* Search + filter bar */}
        <form
          onSubmit={onSearch}
          className="bg-white border border-slate-200 rounded-2xl p-3 mb-3 flex flex-wrap items-end gap-2"
          data-testid="inbox-filter-bar"
        >
          <div className="relative flex-1 min-w-[220px]">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <Input
              placeholder="Search email, domain, ownership…"
              className="pl-9"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              data-testid="inbox-search-input"
            />
          </div>
          <Button type="submit" size="sm" data-testid="inbox-search-btn">Search</Button>
          <Button type="button" size="sm" variant="outline" onClick={reset} data-testid="inbox-reset-btn">Reset</Button>
          <Button type="button" size="sm" variant="outline" onClick={() => exportFile("xlsx")} data-testid="inbox-export-xlsx">
            <FileSpreadsheet size={13} className="mr-1.5" /> XLSX
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={() => exportFile("csv")} data-testid="inbox-export-csv">
            <FileText size={13} className="mr-1.5" /> CSV
          </Button>
        </form>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2 mb-3" data-testid="inbox-filters">
          <Select value={filters.ownership || "_all"} onValueChange={(v) => { setFilters({ ...filters, ownership: v === "_all" ? "" : v }); setSkip(0); }}>
            <SelectTrigger className="h-9 w-40" data-testid="filter-ownership"><SelectValue placeholder="All ownership" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="_all">All ownership</SelectItem>
              {(opts.ownership || []).map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filters.domain || "_all"} onValueChange={(v) => { setFilters({ ...filters, domain: v === "_all" ? "" : v }); setSkip(0); }}>
            <SelectTrigger className="h-9 w-40" data-testid="filter-domain"><SelectValue placeholder="All domains" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="_all">All domains</SelectItem>
              {(opts.domain || []).map((d) => <SelectItem key={d} value={d}>{d}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filters.status || "_all"} onValueChange={(v) => { setFilters({ ...filters, status: v === "_all" ? "" : v }); setSkip(0); }}>
            <SelectTrigger className="h-9 w-44" data-testid="filter-status"><SelectValue placeholder="All statuses" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="_all">All statuses</SelectItem>
              {Object.keys(STATUS_PILL).map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={filters.warmup_status || "_all"} onValueChange={(v) => { setFilters({ ...filters, warmup_status: v === "_all" ? "" : v }); setSkip(0); }}>
            <SelectTrigger className="h-9 w-40" data-testid="filter-warmup"><SelectValue placeholder="All warmup" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="_all">All warmup</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="warming">Warming</SelectItem>
              <SelectItem value="complete">Complete</SelectItem>
              <SelectItem value="off">Off</SelectItem>
            </SelectContent>
          </Select>
          <Input
            type="number"
            placeholder="Min remaining"
            value={filters.min_remaining}
            onChange={(e) => { setFilters({ ...filters, min_remaining: e.target.value }); setSkip(0); }}
            className="h-9 w-32"
            data-testid="filter-min-remaining"
            min={0}
          />
        </div>

        {/* Sort + paging */}
        <div className="flex items-center gap-2 text-xs text-slate-500 mb-2 flex-wrap">
          <span data-testid="inbox-total-count">{data.total.toLocaleString()} inbox{data.total === 1 ? "" : "es"}</span>
          <span className="ml-auto">Sort:</span>
          <Select value={sortBy} onValueChange={(v) => { setSortBy(v); setSkip(0); }}>
            <SelectTrigger className="h-7 w-36" data-testid="inbox-sort-by"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="email">Email</SelectItem>
              <SelectItem value="domain">Domain</SelectItem>
              <SelectItem value="status">Status</SelectItem>
              <SelectItem value="ownership">Ownership</SelectItem>
              <SelectItem value="remaining_capacity">Remaining capacity</SelectItem>
              <SelectItem value="daily_limit">Daily limit</SelectItem>
            </SelectContent>
          </Select>
          <Select value={sortDir} onValueChange={(v) => { setSortDir(v); setSkip(0); }}>
            <SelectTrigger className="h-7 w-24" data-testid="inbox-sort-dir"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="asc">A → Z</SelectItem>
              <SelectItem value="desc">Z → A</SelectItem>
            </SelectContent>
          </Select>
          <span className="ml-3">Show:</span>
          <Select value={String(limit)} onValueChange={(v) => { setLimit(Number(v)); setSkip(0); }}>
            <SelectTrigger className="h-7 w-20" data-testid="inbox-page-size"><SelectValue /></SelectTrigger>
            <SelectContent>
              {PAGE_SIZES.map((n) => <SelectItem key={n} value={String(n)}>{n}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>

        {/* Table */}
        <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
          {loading ? (
            <div className="py-10 text-center text-sm text-slate-500" data-testid="inbox-loading">
              <Loader2 className="inline-block animate-spin mr-2" size={14} /> Loading…
            </div>
          ) : rows.length === 0 ? (
            <div className="py-10 text-center text-sm text-slate-500" data-testid="inbox-empty">
              No inboxes match these filters.
            </div>
          ) : (
            <div className="overflow-x-auto" data-testid="inbox-table">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="text-left px-3 py-2 font-medium">Email</th>
                    <th className="text-left px-3 py-2 font-medium">Domain</th>
                    <th className="text-left px-3 py-2 font-medium">Ownership</th>
                    <th className="text-left px-3 py-2 font-medium">Status</th>
                    <th className="text-right px-3 py-2 font-medium">Daily Limit</th>
                    <th className="text-right px-3 py-2 font-medium">Today Remaining</th>
                    <th className="text-right px-3 py-2 font-medium">120-day Reserve</th>
                    <th className="text-left px-3 py-2 font-medium">Warmup</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => {
                    const Icon = STATUS_ICONS[r.status] || CheckCircle2;
                    return (
                      <tr
                        key={r.account_id}
                        className="border-t border-slate-100 hover:bg-slate-50"
                        data-testid={`inbox-row-${r.account_id}`}
                      >
                        <td className="px-3 py-2 font-medium text-slate-900">{r.email}</td>
                        <td className="px-3 py-2 text-slate-600">{r.domain}</td>
                        <td className="px-3 py-2 text-slate-600 text-xs">{r.ownership || "—"}</td>
                        <td className="px-3 py-2">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_PILL[r.status] || "bg-slate-100 text-slate-700"}`}>
                            <Icon size={11} /> {r.status}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums text-slate-700">{r.daily_limit}</td>
                        <td className="px-3 py-2 text-right tabular-nums text-slate-900 font-medium">{r.remaining_capacity}</td>
                        <td className="px-3 py-2 text-right tabular-nums text-slate-600 text-xs">{r.projected_window_total ?? 0}</td>
                        <td className="px-3 py-2 text-xs text-slate-600">{r.warmup_status || "off"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Pagination */}
        {data.total > limit && (
          <div className="mt-3 flex items-center justify-between text-xs text-slate-500" data-testid="inbox-pagination">
            <span>Showing {skip + 1}–{Math.min(skip + limit, data.total)} of {data.total}</span>
            <div className="flex items-center gap-1">
              <Button size="sm" variant="outline" disabled={skip === 0} onClick={() => setSkip(Math.max(0, skip - limit))} data-testid="inbox-prev-page">
                <ChevronLeft size={14} /> Prev
              </Button>
              <Button size="sm" variant="outline" disabled={skip + limit >= data.total} onClick={() => setSkip(skip + limit)} data-testid="inbox-next-page">
                Next <ChevronRight size={14} />
              </Button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
