import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  Mail,
  Search,
  ArrowLeft,
  Loader2,
  Filter,
  ChevronLeft,
  ChevronRight,
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
import SentEmailViewer from "../components/SentEmailViewer";
import { api } from "../App";
import { toast } from "sonner";

const PAGE_SIZES = [25, 50, 100, 250];

export default function SentEmails({ user, setUser }) {
  const [loading, setLoading] = useState(true);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [limit, setLimit] = useState(50);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sortBy, setSortBy] = useState("sent_at");
  const [sortDir, setSortDir] = useState("desc");
  const [viewerId, setViewerId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        limit: String(limit),
        skip: String(skip),
        sort_by: sortBy,
        sort_dir: sortDir,
      });
      if (search.trim()) params.set("q", search.trim());
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo);
      const res = await api.get(`/sent-emails?${params.toString()}`);
      setItems(res.data?.items || []);
      setTotal(res.data?.total || 0);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Failed to load sent emails");
    } finally {
      setLoading(false);
    }
  }, [search, skip, limit, sortBy, sortDir, dateFrom, dateTo]);

  useEffect(() => {
    load();
  }, [load]);

  const onSearch = (e) => {
    e.preventDefault();
    setSkip(0);
    setSearch(searchInput);
  };

  const reset = () => {
    setSearchInput("");
    setSearch("");
    setDateFrom("");
    setDateTo("");
    setSortBy("sent_at");
    setSortDir("desc");
    setSkip(0);
    setLimit(50);
  };

  return (
    <div className="flex bg-slate-50 min-h-screen">
      <Sidebar user={user} setUser={setUser} />
      <main className="flex-1 lg:ml-64 p-6 lg:p-10 max-w-[1400px]">
        <div className="mb-6">
          <Link
            to="/campaign"
            className="text-sm text-slate-500 hover:text-slate-900 inline-flex items-center gap-1 mb-2"
            data-testid="sent-back-link"
          >
            <ArrowLeft size={14} /> Back to Campaigns
          </Link>
          <h1 className="text-3xl font-bold text-slate-900 flex items-center gap-2">
            <Mail className="text-violet-600" size={26} strokeWidth={1.5} />
            Sent Emails
          </h1>
          <p className="text-sm text-slate-500 max-w-2xl mt-1">
            Every email that left your domain — searchable by recipient, subject, campaign or drip.
            Click <span className="font-medium">View</span> to see the rendered email exactly as the recipient received it.
          </p>
        </div>

        {/* Search bar */}
        <form
          onSubmit={onSearch}
          className="bg-white border border-slate-200 rounded-2xl p-3 mb-4 flex flex-wrap items-end gap-2"
          data-testid="sent-search-form"
        >
          <div className="flex-1 min-w-[260px]">
            <label className="text-[11px] uppercase tracking-wider text-slate-500 mb-1 flex items-center gap-1">
              <Search size={11} /> Search
            </label>
            <Input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Recipient, subject, campaign, drip, from name…"
              data-testid="sent-search-input"
            />
          </div>
          <div>
            <label className="text-[11px] uppercase tracking-wider text-slate-500 mb-1 block">
              From date
            </label>
            <Input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="w-40"
              data-testid="sent-date-from"
            />
          </div>
          <div>
            <label className="text-[11px] uppercase tracking-wider text-slate-500 mb-1 block">
              To date
            </label>
            <Input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="w-40"
              data-testid="sent-date-to"
            />
          </div>
          <Button type="submit" data-testid="sent-search-btn" className="bg-violet-600 hover:bg-violet-700 text-white">
            <Search size={14} className="mr-1.5" /> Search
          </Button>
          <Button type="button" variant="outline" onClick={reset} data-testid="sent-reset-btn">
            Reset
          </Button>
        </form>

        {/* Toolbar */}
        <div className="flex items-center justify-between mb-3 text-xs text-slate-500 flex-wrap gap-2">
          <span data-testid="sent-total-count">{total.toLocaleString()} email{total === 1 ? "" : "s"}</span>
          <div className="flex items-center gap-2">
            <span>Sort by:</span>
            <Select value={sortBy} onValueChange={(v) => { setSortBy(v); setSkip(0); }}>
              <SelectTrigger className="h-8 w-36" data-testid="sent-sort-by"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="sent_at">Sent date</SelectItem>
                <SelectItem value="recipient_email">Recipient</SelectItem>
                <SelectItem value="subject">Subject</SelectItem>
                <SelectItem value="campaign_name">Campaign</SelectItem>
              </SelectContent>
            </Select>
            <Select value={sortDir} onValueChange={(v) => { setSortDir(v); setSkip(0); }}>
              <SelectTrigger className="h-8 w-28" data-testid="sent-sort-dir"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="desc">Newest</SelectItem>
                <SelectItem value="asc">Oldest</SelectItem>
              </SelectContent>
            </Select>
            <span className="ml-3">Page size:</span>
            <Select value={String(limit)} onValueChange={(v) => { setLimit(Number(v)); setSkip(0); }}>
              <SelectTrigger className="h-8 w-20" data-testid="sent-page-size"><SelectValue /></SelectTrigger>
              <SelectContent>
                {PAGE_SIZES.map((n) => (
                  <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Table */}
        <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
          {loading ? (
            <div className="py-10 text-center text-sm text-slate-500" data-testid="sent-loading">
              <Loader2 className="inline-block animate-spin mr-2" size={14} /> Loading…
            </div>
          ) : items.length === 0 ? (
            <div className="py-10 text-center text-sm text-slate-500" data-testid="sent-empty">
              No sent emails match these filters yet. Send a campaign or drip to populate this list.
            </div>
          ) : (
            <table className="min-w-full text-sm" data-testid="sent-table">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="text-left px-3 py-2 font-medium">Recipient</th>
                  <th className="text-left px-3 py-2 font-medium">Subject</th>
                  <th className="text-left px-3 py-2 font-medium">From</th>
                  <th className="text-left px-3 py-2 font-medium">Campaign / Drip</th>
                  <th className="text-left px-3 py-2 font-medium">Sent</th>
                  <th className="text-right px-3 py-2 font-medium">View</th>
                </tr>
              </thead>
              <tbody>
                {items.map((it) => (
                  <tr key={it.sent_id} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`sent-row-${it.sent_id}`}>
                    <td className="px-3 py-2 font-medium text-slate-900">{it.recipient_email}</td>
                    <td className="px-3 py-2 text-slate-700 truncate max-w-[280px]">{it.subject}</td>
                    <td className="px-3 py-2 text-slate-500 text-xs">
                      {it.from_name && it.sender_email
                        ? `${it.from_name} <${it.sender_email}>`
                        : it.from_name || it.sender_email || "—"}
                    </td>
                    <td className="px-3 py-2 text-slate-600">
                      {it.campaign_name && <div>{it.campaign_name}</div>}
                      {it.drip_campaign_name && (
                        <div className="text-xs text-violet-700">
                          {it.drip_campaign_name} · step {it.drip_step_number || "?"}
                        </div>
                      )}
                    </td>
                    <td className="px-3 py-2 text-slate-500 text-xs whitespace-nowrap">
                      {it.sent_at ? new Date(it.sent_at).toLocaleString() : "—"}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setViewerId(it.sent_id)}
                        data-testid={`sent-view-btn-${it.sent_id}`}
                      >
                        <Mail size={12} className="mr-1" /> View
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* Pagination */}
        {total > limit && (
          <div className="mt-3 flex items-center justify-between text-xs text-slate-500" data-testid="sent-pagination">
            <span>
              Showing {skip + 1}–{Math.min(skip + limit, total)} of {total}
            </span>
            <div className="flex items-center gap-1">
              <Button
                size="sm"
                variant="outline"
                disabled={skip === 0}
                onClick={() => setSkip(Math.max(0, skip - limit))}
                data-testid="sent-prev-page"
              >
                <ChevronLeft size={14} /> Prev
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={skip + limit >= total}
                onClick={() => setSkip(skip + limit)}
                data-testid="sent-next-page"
              >
                Next <ChevronRight size={14} />
              </Button>
            </div>
          </div>
        )}
      </main>

      <SentEmailViewer
        open={!!viewerId}
        sentId={viewerId}
        onClose={() => setViewerId(null)}
      />
    </div>
  );
}
