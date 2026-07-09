import { useState, useEffect, useMemo } from "react";
import axios from "axios";
import { Download, FileSpreadsheet, Loader2, RefreshCw, Search, ChevronRight } from "lucide-react";
import Sidebar from "../components/Sidebar";
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
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "../components/ui/card";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * Reports — central reporting page.
 *
 * Currently ships:
 *   • Campaign Reports (Campaigns + Drip Campaigns unified)
 *
 * The layout uses an expandable "report tile" pattern so future reports
 * (Infrastructure, Warmup, Unibox, Reply, Domain Health) can be added as
 * additional tiles without redesigning the page — each tile owns its own
 * filters and export.
 */
export default function Reports({ user, setUser }) {
  const [activeReport, setActiveReport] = useState("campaign"); // future reports switch this

  return (
    <div className="flex min-h-screen bg-slate-50" data-testid="reports-page">
      <Sidebar user={user} setUser={setUser} />

      <main className="flex-1 min-w-0 lg:pl-0 pt-20 lg:pt-0">
        <div className="max-w-7xl mx-auto p-6 lg:p-10">
          <header className="mb-8">
            <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-violet-600 font-semibold">
              <FileSpreadsheet size={14} /> Reports
            </div>
            <h1
              className="mt-1 text-4xl sm:text-5xl lg:text-5xl font-bold text-slate-900 tracking-tight"
              data-testid="reports-title"
            >
              Reporting Centre
            </h1>
            <p className="mt-2 text-sm text-slate-600 max-w-2xl">
              A single home for every export in RouteMail. Pick a report on the left,
              tune the filters, then download the CSV.
            </p>
          </header>

          <div className="grid grid-cols-1 lg:grid-cols-[240px_1fr] gap-6">
            <ReportsTileList active={activeReport} onSelect={setActiveReport} />

            <div className="min-w-0">
              {activeReport === "campaign" && <CampaignReportCard />}
              {/* Future reports mount here — each is a self-contained card. */}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

/* ---------- report tile navigation ---------------------------------------- */

const REPORT_TILES = [
  {
    id: "campaign",
    label: "Campaign Reports",
    description: "Campaigns + Drip Campaigns",
    enabled: true,
  },
  { id: "infrastructure", label: "Infrastructure Reports", description: "Coming soon", enabled: false },
  { id: "warmup", label: "Warmup Reports", description: "Coming soon", enabled: false },
  { id: "unibox", label: "Unibox Reports", description: "Coming soon", enabled: false },
  { id: "reply", label: "Reply Reports", description: "Coming soon", enabled: false },
  { id: "domain", label: "Domain Health Reports", description: "Coming soon", enabled: false },
];

function ReportsTileList({ active, onSelect }) {
  return (
    <nav
      className="rounded-2xl border border-slate-200 bg-white p-2 shadow-sm h-fit"
      data-testid="reports-tile-list"
    >
      {REPORT_TILES.map((t) => {
        const isActive = t.id === active;
        return (
          <button
            key={t.id}
            data-testid={`report-tile-${t.id}`}
            disabled={!t.enabled}
            onClick={() => t.enabled && onSelect(t.id)}
            className={`w-full text-left flex items-center gap-3 px-3 py-2.5 rounded-xl transition ${
              isActive
                ? "bg-violet-50 text-violet-800"
                : t.enabled
                  ? "text-slate-700 hover:bg-slate-50"
                  : "text-slate-400 cursor-not-allowed"
            }`}
          >
            <div className="flex-1 min-w-0">
              <div className="text-sm font-semibold truncate">{t.label}</div>
              <div className="text-[11px] text-slate-500 truncate">{t.description}</div>
            </div>
            {isActive && <ChevronRight size={14} className="text-violet-600" />}
          </button>
        );
      })}
    </nav>
  );
}

/* ---------- Campaign Report card ----------------------------------------- */

function CampaignReportCard() {
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [campaignType, setCampaignType] = useState("both");
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);

  const fetchRows = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (startDate) params.append("start_date", startDate);
      if (endDate) params.append("end_date", endDate);
      params.append("campaign_type", campaignType);
      if (search.trim()) params.append("search", search.trim());

      const res = await axios.get(`${API}/reports/campaigns?${params.toString()}`, {
        withCredentials: true,
      });
      setRows(res.data.rows || []);
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || "Failed to load report";
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRows();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const totals = useMemo(() => {
    return rows.reduce(
      (acc, r) => ({
        prospects: acc.prospects + (r.total_prospects || 0),
        sent: acc.sent + (r.emails_sent || 0),
      }),
      { prospects: 0, sent: 0 }
    );
  }, [rows]);

  const handleExport = async () => {
    if (startDate && endDate && startDate > endDate) {
      toast.error("Start date must be on or before End date");
      return;
    }
    setExporting(true);
    try {
      const params = new URLSearchParams();
      if (startDate) params.append("start_date", startDate);
      if (endDate) params.append("end_date", endDate);
      params.append("campaign_type", campaignType);
      if (search.trim()) params.append("search", search.trim());

      const res = await axios.get(
        `${API}/reports/campaigns/export.csv?${params.toString()}`,
        { withCredentials: true, responseType: "blob" }
      );

      const cd = res.headers["content-disposition"] || "";
      const m = cd.match(/filename="([^"]+)"/);
      const fname =
        m ? m[1] : `RouteMail_Campaign_Report_${new Date().toISOString().slice(0, 10)}.csv`;
      const url = window.URL.createObjectURL(new Blob([res.data], { type: "text/csv" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = fname;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Report downloaded");
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || "Export failed";
      toast.error(msg);
    } finally {
      setExporting(false);
    }
  };

  return (
    <Card className="border-slate-200 shadow-sm" data-testid="campaign-report-card">
      <CardHeader>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <CardTitle className="text-xl">Campaign Reports</CardTitle>
            <CardDescription>
              Combined view of standard Campaigns and Drip Campaigns. Filter and export as CSV.
            </CardDescription>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={fetchRows}
              disabled={loading}
              data-testid="campaign-report-refresh-btn"
            >
              {loading ? (
                <Loader2 size={16} className="mr-2 animate-spin" />
              ) : (
                <RefreshCw size={16} className="mr-2" />
              )}
              Refresh
            </Button>
            <Button
              onClick={handleExport}
              disabled={exporting || loading}
              className="bg-violet-600 hover:bg-violet-700 text-white"
              data-testid="campaign-report-export-csv-btn"
            >
              {exporting ? (
                <Loader2 size={16} className="mr-2 animate-spin" />
              ) : (
                <Download size={16} className="mr-2" />
              )}
              Export CSV
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* filters */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <div>
            <Label htmlFor="report-start-date">Start Date</Label>
            <Input
              id="report-start-date"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="mt-1.5"
              data-testid="campaign-report-start-date"
            />
          </div>
          <div>
            <Label htmlFor="report-end-date">End Date</Label>
            <Input
              id="report-end-date"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="mt-1.5"
              data-testid="campaign-report-end-date"
            />
          </div>
          <div>
            <Label>Campaign Type</Label>
            <Select value={campaignType} onValueChange={setCampaignType}>
              <SelectTrigger className="mt-1.5" data-testid="campaign-report-type-select">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="both">Both</SelectItem>
                <SelectItem value="campaign">Campaign</SelectItem>
                <SelectItem value="drip">Drip Campaign</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div>
            <Label htmlFor="report-search">Campaign Name Search</Label>
            <div className="relative mt-1.5">
              <Search
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
              />
              <Input
                id="report-search"
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Q1 outreach"
                className="pl-9"
                data-testid="campaign-report-search-input"
              />
            </div>
          </div>
        </div>

        <div className="flex justify-end">
          <Button
            variant="secondary"
            onClick={fetchRows}
            disabled={loading}
            data-testid="campaign-report-apply-btn"
          >
            Apply Filters
          </Button>
        </div>

        {/* totals strip */}
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <StatTile label="Rows" value={rows.length} testid="stat-rows" />
          <StatTile label="Total Prospects" value={totals.prospects.toLocaleString()} testid="stat-prospects" />
          <StatTile label="Emails Sent" value={totals.sent.toLocaleString()} testid="stat-emails-sent" />
        </div>

        {/* table */}
        <div className="border border-slate-200 rounded-xl overflow-hidden">
          <div className="max-h-[600px] overflow-auto">
            <table className="w-full text-sm" data-testid="campaign-report-table">
              <thead className="bg-slate-50 sticky top-0 z-10">
                <tr className="text-slate-600">
                  <th className="text-left px-4 py-2.5 font-semibold">Campaign / Drip Campaign Name</th>
                  <th className="text-left px-4 py-2.5 font-semibold">Type</th>
                  <th className="text-right px-4 py-2.5 font-semibold">Total Prospects</th>
                  <th className="text-right px-4 py-2.5 font-semibold">Emails Sent</th>
                  <th className="text-left px-4 py-2.5 font-semibold">Date Sent</th>
                  <th className="text-left px-4 py-2.5 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody>
                {loading && (
                  <tr>
                    <td colSpan={6} className="text-center py-10 text-slate-400" data-testid="report-loading">
                      <Loader2 className="inline animate-spin mr-2" size={16} /> Loading…
                    </td>
                  </tr>
                )}
                {!loading && rows.length === 0 && (
                  <tr>
                    <td colSpan={6} className="text-center py-10 text-slate-400" data-testid="report-empty">
                      No rows match the current filters.
                    </td>
                  </tr>
                )}
                {!loading &&
                  rows.map((r) => (
                    <tr
                      key={`${r.type}-${r.id}`}
                      className="border-t border-slate-100 hover:bg-slate-50"
                      data-testid={`report-row-${r.id}`}
                    >
                      <td className="px-4 py-2.5 font-medium text-slate-800">{r.name}</td>
                      <td className="px-4 py-2.5">
                        <span
                          className={`inline-flex px-2 py-0.5 rounded-full text-[11px] font-medium ${
                            r.type === "Drip Campaign"
                              ? "bg-indigo-50 text-indigo-700"
                              : "bg-emerald-50 text-emerald-700"
                          }`}
                        >
                          {r.type}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums">
                        {(r.total_prospects || 0).toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums">
                        {(r.emails_sent || 0).toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 text-slate-600">{r.date_sent || "—"}</td>
                      <td className="px-4 py-2.5 text-slate-500 capitalize">{r.status || "—"}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function StatTile({ label, value, testid }) {
  return (
    <div
      className="rounded-xl border border-slate-200 bg-white p-4"
      data-testid={testid}
    >
      <div className="text-[11px] uppercase tracking-widest text-slate-500 font-semibold">
        {label}
      </div>
      <div className="mt-1 text-2xl font-semibold text-slate-900 tabular-nums">
        {value}
      </div>
    </div>
  );
}
