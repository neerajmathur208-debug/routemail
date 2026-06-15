import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Inbox,
  Mail,
  Search,
  ShieldOff,
  FolderPlus,
  Folder,
  RefreshCw,
  CheckSquare,
  Square,
  Sparkles,
  AlertCircle,
  CheckCircle2,
  Clock,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "../components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../components/ui/alert-dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "../components/ui/tooltip";
import Sidebar from "../components/Sidebar";
import { api } from "../App";
import { toast } from "sonner";

function formatTime(ts) {
  if (!ts) return "";
  const d = new Date(ts);
  const now = new Date();
  const diff = (now - d) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

// Classify a single email account into a status bucket.
// Returns { healthy: boolean, label: string, detail: string, severity: "healthy"|"warning"|"error" }
function classifyAccountStatus(a) {
  if (!a.receiving_configured) {
    return {
      healthy: false,
      label: "Not Receiving",
      detail: "IMAP receiving settings not configured for this account.",
      severity: "error",
    };
  }
  const err = (a.imap_last_error || "").toString();
  if (err) {
    const lower = err.toLowerCase();
    if (
      lower.includes("auth") ||
      lower.includes("535") ||
      lower.includes("invalid credentials") ||
      lower.includes("password")
    ) {
      return {
        healthy: false,
        label: "IMAP Authentication Failed",
        detail: err.slice(0, 220),
        severity: "error",
      };
    }
    if (
      lower.includes("timeout") ||
      lower.includes("timed out") ||
      lower.includes("connection refused") ||
      lower.includes("network is unreachable")
    ) {
      return {
        healthy: false,
        label: "Connection Timeout",
        detail: err.slice(0, 220),
        severity: "error",
      };
    }
    return {
      healthy: false,
      label: "Error",
      detail: err.slice(0, 220),
      severity: "error",
    };
  }
  if (a.imap_last_sync_at) {
    const last = new Date(a.imap_last_sync_at).getTime();
    const ageHrs = (Date.now() - last) / (1000 * 60 * 60);
    if (ageHrs > 24) {
      return {
        healthy: false,
        label: "Delayed Sync",
        detail: `Last successful sync: ${formatTime(a.imap_last_sync_at)}.`,
        severity: "warning",
      };
    }
  }
  return {
    healthy: true,
    label: "Receiving",
    detail: a.imap_last_sync_at ? `Synced ${formatTime(a.imap_last_sync_at)}` : "Healthy",
    severity: "healthy",
  };
}

export default function Unibox({ user, setUser }) {
  const [replies, setReplies] = useState([]);
  const [total, setTotal] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({
    unread_only: false,
    account_id: "",
    folder_id: "",
    campaign_id: "",
    drip_id: "",
    domain: "",
    date_preset: "",
    date_from: "",
    date_to: "",
    archived: false,
  });
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("received_at");
  const [sortDir, setSortDir] = useState("desc");
  const [limit, setLimit] = useState(50);
  const [skip, setSkip] = useState(0);
  const [selectedReply, setSelectedReply] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [statusAccounts, setStatusAccounts] = useState([]);
  const [folders, setFolders] = useState([]);
  const [campaignsList, setCampaignsList] = useState([]);
  const [dripList, setDripList] = useState([]);
  const [saveDialog, setSaveDialog] = useState(false);
  const [saveFolderId, setSaveFolderId] = useState("");
  const [newFolderName, setNewFolderName] = useState("");
  const [saveBusy, setSaveBusy] = useState(false);
  const [moveDialog, setMoveDialog] = useState(false);
  const [moveFolderId, setMoveFolderId] = useState("");
  const [moveBusy, setMoveBusy] = useState(false);
  const [dneDialogOpen, setDneDialogOpen] = useState(false);
  const [dneScope, setDneScope] = useState("email"); // "email" | "domain"
  const [dneDomainTarget, setDneDomainTarget] = useState(""); // single-row domain DNE
  const [dneDomainPreview, setDneDomainPreview] = useState(null);
  const [dneBusy, setDneBusy] = useState(false);
  const [issuesOpen, setIssuesOpen] = useState(false);

  const fetchReplies = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filter.unread_only) params.set("unread_only", "true");
      if (filter.archived) params.set("archived", "true");
      if (filter.account_id) params.set("account_id", filter.account_id);
      if (filter.folder_id) params.set("folder_id", filter.folder_id);
      if (filter.campaign_id) params.set("campaign_id", filter.campaign_id);
      if (filter.drip_id) params.set("drip_id", filter.drip_id);
      if (filter.domain) params.set("domain", filter.domain);
      if (filter.date_preset) params.set("date_preset", filter.date_preset);
      else {
        if (filter.date_from) params.set("date_from", filter.date_from);
        if (filter.date_to) params.set("date_to", filter.date_to);
      }
      if (search.trim()) params.set("q", search.trim());
      params.set("sort_by", sortBy);
      params.set("sort_dir", sortDir);
      params.set("limit", String(limit));
      params.set("skip", String(skip));

      const res = await api.get(`/unibox/replies?${params}`);
      setReplies(res.data.items || []);
      setTotal(res.data.total || 0);
      setUnreadCount(res.data.unread_count || 0);
    } catch (err) {
      toast.error("Failed to load replies");
    } finally {
      setLoading(false);
    }
  }, [filter, search, sortBy, sortDir, limit, skip]);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await api.get("/unibox/status");
      setStatusAccounts(res.data.accounts || []);
    } catch (err) {
      // silent
    }
  }, []);

  const fetchFolders = useCallback(async () => {
    try {
      const res = await api.get("/leads/folders");
      setFolders(res.data.folders || []);
    } catch (err) {
      // silent
    }
  }, []);

  const fetchCampaignsAndDrips = useCallback(async () => {
    try {
      const [c, d] = await Promise.all([
        api.get("/campaigns").catch(() => ({ data: [] })),
        api.get("/drip-campaigns").catch(() => ({ data: [] })),
      ]);
      setCampaignsList(c.data || []);
      setDripList(d.data || []);
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    Promise.all([fetchReplies(), fetchStatus(), fetchFolders(), fetchCampaignsAndDrips()]);
  }, [fetchReplies, fetchStatus, fetchFolders, fetchCampaignsAndDrips]);

  const toggleSel = (id) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };
  const clearSel = () => setSelectedIds([]);
  const allSelected = selectedIds.length > 0 && selectedIds.length === replies.length;

  const markRead = async (read) => {
    if (selectedIds.length === 0) return;
    try {
      await api.post("/unibox/replies/mark", { reply_ids: selectedIds, read });
      toast.success(`Marked ${selectedIds.length} as ${read ? "read" : "unread"}`);
      clearSel();
      fetchReplies();
    } catch (err) {
      toast.error("Failed to mark replies");
    }
  };

  const bulkArchive = async (archived) => {
    if (selectedIds.length === 0) return;
    try {
      await api.post("/unibox/replies/archive", { reply_ids: selectedIds, archived });
      toast.success(`${archived ? "Archived" : "Unarchived"} ${selectedIds.length} repl${selectedIds.length === 1 ? "y" : "ies"}`);
      clearSel();
      fetchReplies();
    } catch (err) {
      toast.error("Failed to archive");
    }
  };

  const bulkDelete = async () => {
    if (selectedIds.length === 0) return;
    if (!window.confirm(`Permanently delete ${selectedIds.length} repl${selectedIds.length === 1 ? "y" : "ies"}? This cannot be undone.`)) return;
    try {
      const res = await api.post("/unibox/replies/delete", { reply_ids: selectedIds });
      toast.success(`Deleted ${res.data.deleted} repl${res.data.deleted === 1 ? "y" : "ies"}`);
      clearSel();
      fetchReplies();
    } catch (err) {
      toast.error("Failed to delete");
    }
  };

  const submitMove = async () => {
    if (selectedIds.length === 0 || !moveFolderId) return;
    setMoveBusy(true);
    try {
      const folder_id = moveFolderId === "__unassigned__" ? null : moveFolderId;
      await api.post("/unibox/replies/move", { reply_ids: selectedIds, folder_id });
      toast.success(`Moved ${selectedIds.length} repl${selectedIds.length === 1 ? "y" : "ies"}`);
      setMoveDialog(false);
      setMoveFolderId("");
      clearSel();
      fetchReplies();
      fetchFolders();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Move failed");
    } finally {
      setMoveBusy(false);
    }
  };

  const openSingleDomainDne = async (domain) => {
    if (!domain) return;
    setDneDomainTarget(domain);
    setDneDomainPreview(null);
    try {
      const res = await api.post("/unibox/dne/domain/preview", { domain });
      setDneDomainPreview(res.data);
    } catch {
      // ignore — dialog still opens
    }
  };

  const confirmSingleDomainDne = async () => {
    if (!dneDomainTarget) return;
    setDneBusy(true);
    try {
      const res = await api.post("/unibox/dne/domain", { domain: dneDomainTarget });
      if (res.data?.added) {
        toast.success(`Suppressed entire domain ${dneDomainTarget}`);
      } else {
        toast.message(`${dneDomainTarget} was already suppressed`);
      }
      setDneDomainTarget("");
      setDneDomainPreview(null);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to suppress domain");
    } finally {
      setDneBusy(false);
    }
  };

  const bulkAddToDne = async () => {
    if (selectedIds.length === 0) return;
    setDneBusy(true);
    try {
      if (dneScope === "domain") {
        // Resolve from_email per reply -> unique domains -> add directly to Global DNE
        const selectedReplies = replies.filter((r) => selectedIds.includes(r.reply_id));
        const domains = Array.from(
          new Set(
            selectedReplies
              .map((r) => (r.from_email || "").split("@")[1])
              .filter(Boolean)
              .map((d) => d.toLowerCase())
          )
        );
        if (domains.length === 0) {
          toast.error("Could not derive any domain from selected replies");
          setDneBusy(false);
          return;
        }
        // Find global list
        const listsRes = await api.get("/dne-lists");
        const globalList = (listsRes.data || []).find((l) => l.is_global);
        if (!globalList) {
          toast.error("Global Do Not Email list not found");
          setDneBusy(false);
          return;
        }
        const entries = domains.map((d) => ({ type: "domain", value: d }));
        const res = await api.post(`/dne-lists/${globalList.list_id}/emails`, { entries });
        toast.success(
          `Blocked ${res.data.added} domain${res.data.added === 1 ? "" : "s"} (${domains.length} unique)`
        );
      } else {
        const res = await api.post("/unibox/replies/add-to-dne", { reply_ids: selectedIds });
        toast.success(`Added ${res.data.added} email${res.data.added === 1 ? "" : "s"} to Global Do Not Email`);
      }
      clearSel();
      setDneDialogOpen(false);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to add to DNE");
    } finally {
      setDneBusy(false);
    }
  };

  const submitSave = async () => {
    if (selectedIds.length === 0 || !saveFolderId) return;
    setSaveBusy(true);
    try {
      const payload = {
        reply_ids: selectedIds,
        folder_id: saveFolderId,
        new_folder_name: saveFolderId === "__new__" ? newFolderName : undefined,
      };
      const res = await api.post("/leads/save", payload);
      toast.success(`Saved ${res.data.saved} response${res.data.saved === 1 ? "" : "s"} to folder`);
      setSaveDialog(false);
      setNewFolderName("");
      setSaveFolderId("");
      clearSel();
      fetchFolders();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to save");
    } finally {
      setSaveBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar user={user} setUser={setUser} />
      <main className="flex-1 p-6 lg:p-8 overflow-y-auto">
        <div className="max-w-6xl mx-auto">
          <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
            <div>
              <h1 className="font-heading font-extrabold text-2xl sm:text-3xl text-slate-900 flex items-center gap-2">
                <Inbox size={28} className="text-blue-600" />
                Unibox
                {unreadCount > 0 && (
                  <Badge className="bg-blue-600 text-white hover:bg-blue-600" data-testid="unread-badge">
                    {unreadCount} unread
                  </Badge>
                )}
              </h1>
              <p className="text-sm text-slate-500 mt-1">
                Centralised view of replies across all your connected inboxes.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                onClick={() => { fetchReplies(); fetchStatus(); }}
                disabled={loading}
                data-testid="refresh-unibox"
              >
                <RefreshCw size={14} className={`mr-2 ${loading ? "animate-spin" : ""}`} />
                Refresh
              </Button>
            </div>
          </div>

          {/* Compact account-health summary (replaces the per-account grid) */}
          {statusAccounts.length > 0 && (() => {
            const classified = statusAccounts.map((a) => ({
              ...a,
              _status: classifyAccountStatus(a),
            }));
            const healthy = classified.filter((a) => a._status.healthy);
            const issues = classified.filter((a) => !a._status.healthy);
            const total = classified.length;
            const allHealthy = issues.length === 0;
            return (
              <div
                className={`mb-4 rounded-xl border p-3 sm:p-4 flex flex-wrap items-center gap-3 ${
                  allHealthy
                    ? "border-emerald-200 bg-emerald-50/40"
                    : "border-amber-200 bg-amber-50/40"
                }`}
                data-testid="unibox-status-card"
              >
                <div className="flex items-center gap-2 min-w-0">
                  {allHealthy ? (
                    <span className="inline-flex w-8 h-8 rounded-full bg-emerald-100 text-emerald-700 items-center justify-center shrink-0">
                      <CheckCircle2 size={16} />
                    </span>
                  ) : (
                    <span className="inline-flex w-8 h-8 rounded-full bg-amber-100 text-amber-700 items-center justify-center shrink-0">
                      <AlertCircle size={16} />
                    </span>
                  )}
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-slate-900" data-testid="receiving-count">
                      Receiving Accounts: {healthy.length} / {total}
                    </div>
                    <div className="text-xs text-slate-600 truncate">
                      {allHealthy ? (
                        <>All connected inboxes are receiving successfully.</>
                      ) : (
                        <span data-testid="issues-summary">
                          {issues.length} account{issues.length === 1 ? "" : "s"} require{issues.length === 1 ? "s" : ""} attention.
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                {!allHealthy && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="ml-auto"
                    onClick={() => setIssuesOpen(true)}
                    data-testid="view-issues-btn"
                  >
                    <AlertCircle size={14} className="mr-1.5 text-amber-600" />
                    View Issues
                  </Button>
                )}
              </div>
            );
          })()}

          {/* Filters + search */}
          <div className="mb-4 space-y-2" data-testid="unibox-filters">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setSkip(0);
                setSearch(searchInput);
              }}
              className="flex flex-wrap items-center gap-2"
            >
              <div className="relative flex-1 min-w-[240px] max-w-md">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  placeholder="Search email, company, campaign, folder, domain…"
                  className="pl-9"
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  data-testid="unibox-search"
                />
              </div>
              <Button type="submit" size="sm" data-testid="unibox-search-btn">Search</Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                onClick={() => {
                  setSearchInput("");
                  setSearch("");
                  setFilter({
                    unread_only: false, account_id: "", folder_id: "", campaign_id: "",
                    drip_id: "", domain: "", date_preset: "", date_from: "", date_to: "",
                    archived: false,
                  });
                  setSkip(0);
                }}
                data-testid="unibox-reset-btn"
              >
                Reset
              </Button>
            </form>

            <div className="flex flex-wrap items-center gap-2">
              <Select
                value={filter.folder_id || "_all"}
                onValueChange={(v) => { setFilter({ ...filter, folder_id: v === "_all" ? "" : v }); setSkip(0); }}
              >
                <SelectTrigger className="w-44" data-testid="filter-folder"><SelectValue placeholder="All brands" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="_all">All brands</SelectItem>
                  <SelectItem value="__unassigned__">Unassigned</SelectItem>
                  {folders.map((f) => (
                    <SelectItem key={f.folder_id} value={f.folder_id}>
                      {f.name} ({f.reply_count || 0})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value={filter.campaign_id || "_all"}
                onValueChange={(v) => { setFilter({ ...filter, campaign_id: v === "_all" ? "" : v }); setSkip(0); }}
              >
                <SelectTrigger className="w-44" data-testid="filter-campaign"><SelectValue placeholder="All campaigns" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="_all">All campaigns</SelectItem>
                  {campaignsList.map((c) => (
                    <SelectItem key={c.campaign_id} value={c.campaign_id}>{c.name || c.campaign_id}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value={filter.drip_id || "_all"}
                onValueChange={(v) => { setFilter({ ...filter, drip_id: v === "_all" ? "" : v }); setSkip(0); }}
              >
                <SelectTrigger className="w-44" data-testid="filter-drip"><SelectValue placeholder="All drips" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="_all">All drips</SelectItem>
                  {dripList.map((d) => (
                    <SelectItem key={d.drip_id} value={d.drip_id}>{d.name || d.drip_id}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value={filter.account_id || "_all"}
                onValueChange={(v) => { setFilter({ ...filter, account_id: v === "_all" ? "" : v }); setSkip(0); }}
              >
                <SelectTrigger className="w-44" data-testid="filter-account"><SelectValue placeholder="All accounts" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="_all">All accounts</SelectItem>
                  {statusAccounts.map((a) => (
                    <SelectItem key={a.account_id} value={a.account_id}>{a.email}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Input
                placeholder="Domain (e.g. company.com)"
                value={filter.domain}
                onChange={(e) => { setFilter({ ...filter, domain: e.target.value }); }}
                onBlur={() => setSkip(0)}
                className="w-44"
                data-testid="filter-domain"
              />
              <Select
                value={filter.date_preset || "_all"}
                onValueChange={(v) => {
                  setFilter({
                    ...filter,
                    date_preset: v === "_all" ? "" : v === "custom" ? "" : v,
                    date_from: v === "custom" ? filter.date_from : "",
                    date_to: v === "custom" ? filter.date_to : "",
                  });
                  setSkip(0);
                }}
              >
                <SelectTrigger className="w-40" data-testid="filter-date-preset"><SelectValue placeholder="Any date" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="_all">Any date</SelectItem>
                  <SelectItem value="today">Today</SelectItem>
                  <SelectItem value="yesterday">Yesterday</SelectItem>
                  <SelectItem value="last_7">Last 7 days</SelectItem>
                  <SelectItem value="last_30">Last 30 days</SelectItem>
                  <SelectItem value="last_90">Last 90 days</SelectItem>
                  <SelectItem value="custom">Custom…</SelectItem>
                </SelectContent>
              </Select>
              {!filter.date_preset && (filter.date_from || filter.date_to) && (
                <>
                  <Input
                    type="date"
                    value={filter.date_from}
                    onChange={(e) => { setFilter({ ...filter, date_from: e.target.value }); setSkip(0); }}
                    className="w-36"
                    data-testid="filter-date-from"
                  />
                  <Input
                    type="date"
                    value={filter.date_to}
                    onChange={(e) => { setFilter({ ...filter, date_to: e.target.value }); setSkip(0); }}
                    className="w-36"
                    data-testid="filter-date-to"
                  />
                </>
              )}
              <Select
                value={filter.unread_only ? "unread" : (filter.archived ? "archived" : "all")}
                onValueChange={(v) => {
                  setFilter({
                    ...filter,
                    unread_only: v === "unread",
                    archived: v === "archived",
                  });
                  setSkip(0);
                }}
              >
                <SelectTrigger className="w-40" data-testid="filter-status"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All replies</SelectItem>
                  <SelectItem value="unread">Unread only</SelectItem>
                  <SelectItem value="archived">Archived</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Sort + page size */}
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span data-testid="unibox-total">{total.toLocaleString()} repl{total === 1 ? "y" : "ies"}</span>
              <span className="ml-auto">Sort:</span>
              <Select value={sortBy} onValueChange={(v) => { setSortBy(v); setSkip(0); }}>
                <SelectTrigger className="h-8 w-36" data-testid="unibox-sort-by"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="received_at">Reply date</SelectItem>
                  <SelectItem value="campaign_name">Campaign</SelectItem>
                  <SelectItem value="folder_id">Folder</SelectItem>
                  <SelectItem value="from_email">From email</SelectItem>
                  <SelectItem value="account_id">Account</SelectItem>
                </SelectContent>
              </Select>
              <Select value={sortDir} onValueChange={(v) => { setSortDir(v); setSkip(0); }}>
                <SelectTrigger className="h-8 w-24" data-testid="unibox-sort-dir"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="desc">Newest</SelectItem>
                  <SelectItem value="asc">Oldest</SelectItem>
                </SelectContent>
              </Select>
              <span className="ml-3">Show:</span>
              <Select value={String(limit)} onValueChange={(v) => { setLimit(Number(v)); setSkip(0); }}>
                <SelectTrigger className="h-8 w-20" data-testid="unibox-page-size"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {[25, 50, 100, 250].map((n) => (
                    <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Bulk action bar */}
          {selectedIds.length > 0 && (
            <div className="bg-white border border-blue-200 rounded-md p-3 mb-4 flex flex-wrap items-center gap-2" data-testid="bulk-bar">
              <span className="text-sm font-medium text-slate-700">
                {selectedIds.length} selected
              </span>
              <Button size="sm" variant="outline" onClick={() => markRead(true)} data-testid="bulk-mark-read">
                Mark read
              </Button>
              <Button size="sm" variant="outline" onClick={() => markRead(false)} data-testid="bulk-mark-unread">
                Mark unread
              </Button>
              <Button size="sm" variant="outline" onClick={() => setMoveDialog(true)} data-testid="bulk-move">
                <FolderPlus size={14} className="mr-1" /> Move to folder
              </Button>
              <Button size="sm" variant="outline" onClick={() => bulkArchive(!filter.archived)} data-testid="bulk-archive">
                {filter.archived ? "Unarchive" : "Archive"}
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="text-rose-600 border-rose-200 hover:bg-rose-50"
                onClick={bulkDelete}
                data-testid="bulk-delete"
              >
                Delete
              </Button>
              <Button size="sm" variant="outline" onClick={() => setSaveDialog(true)} data-testid="bulk-save-lead">
                <FolderPlus size={14} className="mr-1" />
                Save to Responses/Leads
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="text-red-600 border-red-200 hover:bg-red-50"
                onClick={() => setDneDialogOpen(true)}
                data-testid="bulk-add-dne"
              >
                <ShieldOff size={14} className="mr-1" />
                Add to Global Do Not Email
              </Button>
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span>
                      <Button size="sm" variant="ghost" disabled data-testid="ai-categorise-btn">
                        <Sparkles size={14} className="mr-1" />
                        Categorise with AI
                      </Button>
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>AI categorisation coming soon.</TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <Button size="sm" variant="ghost" onClick={clearSel} className="ml-auto text-slate-500" data-testid="clear-sel">
                Clear
              </Button>
            </div>
          )}

          {/* Replies table — Phase 2 Batch B columns */}
          {loading ? (
            <p className="text-sm text-slate-500" data-testid="unibox-loading">Loading…</p>
          ) : replies.length === 0 ? (
            <div className="bg-white border border-dashed border-slate-200 rounded-md p-12 text-center" data-testid="unibox-empty">
              <Inbox className="mx-auto text-slate-300" size={36} />
              <p className="font-medium text-slate-700 mt-2">No replies match these filters</p>
              <p className="text-sm text-slate-500 mt-1">Try resetting filters or wait for IMAP sync.</p>
            </div>
          ) : (
            <div className="bg-white border border-slate-200 rounded-md overflow-x-auto" data-testid="reply-list">
              <table className="min-w-full text-sm" data-testid="unibox-table">
                <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                  <tr>
                    <th className="px-3 py-2 text-left w-8">
                      <button
                        onClick={() => allSelected ? clearSel() : setSelectedIds(replies.map((r) => r.reply_id))}
                        data-testid="unibox-select-all"
                      >
                        {allSelected ? <CheckSquare size={14} className="text-blue-600" /> : <Square size={14} />}
                      </button>
                    </th>
                    <th className="px-3 py-2 text-left font-medium">From</th>
                    <th className="px-3 py-2 text-left font-medium">Brand / Folder</th>
                    <th className="px-3 py-2 text-left font-medium">Subject</th>
                    <th className="px-3 py-2 text-left font-medium">Campaign</th>
                    <th className="px-3 py-2 text-left font-medium">Drip</th>
                    <th className="px-3 py-2 text-left font-medium">Account</th>
                    <th className="px-3 py-2 text-left font-medium">Domain</th>
                    <th className="px-3 py-2 text-left font-medium">Reply Date</th>
                    <th className="px-3 py-2 text-right font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {replies.map((r) => {
                    const sel = selectedIds.includes(r.reply_id);
                    return (
                      <tr
                        key={r.reply_id}
                        className={`border-t border-slate-100 ${sel ? "bg-blue-50/40" : "hover:bg-slate-50"} ${!r.read ? "font-semibold" : ""}`}
                        data-testid={`reply-row-${r.reply_id}`}
                      >
                        <td className="px-3 py-2">
                          <button
                            onClick={(e) => { e.stopPropagation(); toggleSel(r.reply_id); }}
                            data-testid={`reply-select-${r.reply_id}`}
                          >
                            {sel ? <CheckSquare size={14} className="text-blue-600" /> : <Square size={14} className="text-slate-400" />}
                          </button>
                        </td>
                        <td className="px-3 py-2 cursor-pointer max-w-[180px] truncate" onClick={() => setSelectedReply(r)}>
                          <span className="text-slate-900">{r.from_email}</span>
                        </td>
                        <td className="px-3 py-2">
                          {r.folder_name ? (
                            <span className="px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 text-[11px]" data-testid={`reply-folder-${r.reply_id}`}>
                              📁 {r.folder_name}
                            </span>
                          ) : (
                            <span className="text-slate-400 italic text-xs">unassigned</span>
                          )}
                        </td>
                        <td className="px-3 py-2 cursor-pointer max-w-[260px] truncate text-slate-700" onClick={() => setSelectedReply(r)}>
                          {r.subject || "(no subject)"}
                        </td>
                        <td className="px-3 py-2 text-slate-600 max-w-[140px] truncate" data-testid={`reply-campaign-${r.reply_id}`}>
                          {r.campaign_name || "—"}
                        </td>
                        <td className="px-3 py-2 text-slate-600 max-w-[140px] truncate" data-testid={`reply-drip-${r.reply_id}`}>
                          {r.drip_campaign_name ? `${r.drip_campaign_name}${r.drip_step_number != null ? " · step " + (r.drip_step_number + 1) : ""}` : "—"}
                        </td>
                        <td className="px-3 py-2 text-slate-600 max-w-[160px] truncate" data-testid={`reply-account-${r.reply_id}`}>
                          {r.sending_account_email || r.received_on_email || "—"}
                        </td>
                        <td className="px-3 py-2 text-slate-600 text-xs" data-testid={`reply-domain-${r.reply_id}`}>
                          {r.domain || "—"}
                        </td>
                        <td className="px-3 py-2 text-slate-500 text-xs whitespace-nowrap" data-testid={`reply-date-${r.reply_id}`}>
                          {formatTime(r.received_at)}
                        </td>
                        <td className="px-3 py-2 text-right">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 text-rose-600 hover:text-rose-700"
                            onClick={(e) => { e.stopPropagation(); openSingleDomainDne(r.domain); }}
                            disabled={!r.domain}
                            data-testid={`reply-domain-dne-${r.reply_id}`}
                            title={`Suppress @${r.domain}`}
                          >
                            <ShieldOff size={12} />
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {total > limit && (
            <div className="mt-3 flex items-center justify-between text-xs text-slate-500" data-testid="unibox-pagination">
              <span>Showing {skip + 1}–{Math.min(skip + limit, total)} of {total}</span>
              <div className="flex items-center gap-1">
                <Button size="sm" variant="outline" disabled={skip === 0} onClick={() => setSkip(Math.max(0, skip - limit))} data-testid="unibox-prev-page">
                  Prev
                </Button>
                <Button size="sm" variant="outline" disabled={skip + limit >= total} onClick={() => setSkip(skip + limit)} data-testid="unibox-next-page">
                  Next
                </Button>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Reply Detail */}
      <Dialog open={!!selectedReply} onOpenChange={(o) => !o && setSelectedReply(null)}>
        <DialogContent className="sm:max-w-2xl" data-testid="reply-detail-dialog">
          <DialogHeader>
            <DialogTitle>{selectedReply?.subject || "(no subject)"}</DialogTitle>
            <DialogDescription>
              From <span className="font-medium text-slate-700">{selectedReply?.from_email}</span> to{" "}
              <span className="font-medium text-slate-700">{selectedReply?.received_on_email}</span>{" "}
              · {formatTime(selectedReply?.received_at)}
              {(selectedReply?.campaign_name || selectedReply?.drip_campaign_name) && (
                <>
                  {" · "}
                  <Badge className="bg-violet-100 text-violet-700 border border-violet-200">
                    {selectedReply.campaign_name || selectedReply.drip_campaign_name}
                  </Badge>
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-[60vh] overflow-y-auto whitespace-pre-wrap text-sm text-slate-800 bg-slate-50 rounded p-3" data-testid="reply-body">
            {selectedReply?.body || "(empty body)"}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                if (selectedReply) {
                  setSelectedIds([selectedReply.reply_id]);
                  setSaveDialog(true);
                  setSelectedReply(null);
                }
              }}
              data-testid="single-save-lead"
            >
              <FolderPlus size={14} className="mr-1" />
              Save to Responses/Leads
            </Button>
            <Button
              variant="outline"
              className="text-red-600 border-red-200 hover:bg-red-50"
              onClick={() => {
                if (selectedReply) {
                  setSelectedIds([selectedReply.reply_id]);
                  setDneDialogOpen(true);
                  setSelectedReply(null);
                }
              }}
              data-testid="single-add-dne"
            >
              <ShieldOff size={14} className="mr-1" />
              Add to Global DNE
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Save to Folder Dialog */}
      <Dialog open={saveDialog} onOpenChange={setSaveDialog}>
        <DialogContent data-testid="save-lead-dialog">
          <DialogHeader>
            <DialogTitle>Save to Responses/Leads</DialogTitle>
            <DialogDescription>
              Saving {selectedIds.length} response{selectedIds.length === 1 ? "" : "s"} to a folder.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <Label className="text-xs text-slate-500">Folder</Label>
              <Select value={saveFolderId} onValueChange={setSaveFolderId}>
                <SelectTrigger data-testid="save-folder-select">
                  <SelectValue placeholder="Choose a folder…" />
                </SelectTrigger>
                <SelectContent>
                  {folders.map((f) => (
                    <SelectItem key={f.folder_id} value={f.folder_id}>
                      <Folder size={12} className="inline mr-1.5" />
                      {f.name} <span className="text-slate-400">({f.lead_count})</span>
                    </SelectItem>
                  ))}
                  <SelectItem value="__new__">+ Create new folder</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {saveFolderId === "__new__" && (
              <div>
                <Label className="text-xs text-slate-500">New folder name</Label>
                <Input
                  value={newFolderName}
                  onChange={(e) => setNewFolderName(e.target.value)}
                  placeholder="e.g. Hot Leads"
                  data-testid="new-folder-input"
                />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSaveDialog(false)} disabled={saveBusy}>Cancel</Button>
            <Button
              onClick={submitSave}
              disabled={saveBusy || !saveFolderId || (saveFolderId === "__new__" && !newFolderName.trim())}
              data-testid="save-lead-confirm"
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* DNE Confirm */}
      <Dialog open={dneDialogOpen} onOpenChange={setDneDialogOpen}>
        <DialogContent data-testid="dne-bulk-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ShieldOff className="text-red-500" /> Add to Global Do Not Email List
            </DialogTitle>
            <DialogDescription>
              Choose whether to block only the sender&apos;s email address or every recipient on that
              sender&apos;s domain.
            </DialogDescription>
          </DialogHeader>

          <div className="flex gap-2 mt-2" data-testid="dne-scope-selector">
            <button
              type="button"
              onClick={() => setDneScope("email")}
              className={`flex-1 py-3 px-3 rounded-lg border text-sm font-medium transition text-left ${
                dneScope === "email"
                  ? "border-sky-500 bg-sky-50 text-sky-700 ring-2 ring-sky-200"
                  : "border-slate-200 text-slate-500 hover:bg-slate-50"
              }`}
              data-testid="dne-scope-email-btn"
            >
              <div>Email Only</div>
              <div className="text-[11px] font-normal text-slate-500 mt-0.5">
                Block this specific email address
              </div>
            </button>
            <button
              type="button"
              onClick={() => setDneScope("domain")}
              className={`flex-1 py-3 px-3 rounded-lg border text-sm font-medium transition text-left ${
                dneScope === "domain"
                  ? "border-violet-500 bg-violet-50 text-violet-700 ring-2 ring-violet-200"
                  : "border-slate-200 text-slate-500 hover:bg-slate-50"
              }`}
              data-testid="dne-scope-domain-btn"
            >
              <div>Entire Domain</div>
              <div className="text-[11px] font-normal text-slate-500 mt-0.5">
                Block every recipient on this domain
              </div>
            </button>
          </div>

          <DialogFooter className="mt-3">
            <Button variant="outline" onClick={() => setDneDialogOpen(false)} disabled={dneBusy}>
              Cancel
            </Button>
            <Button
              onClick={bulkAddToDne}
              disabled={dneBusy}
              className="bg-red-600 hover:bg-red-700 text-white"
              data-testid="confirm-add-dne"
            >
              {dneBusy ? "Adding…" : `Block ${dneScope === "domain" ? "domain(s)" : "email(s)"}`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Issues dialog — only opens when user clicks "View Issues" */}
      <Dialog open={issuesOpen} onOpenChange={setIssuesOpen}>
        <DialogContent className="sm:max-w-[640px]" data-testid="issues-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <AlertCircle className="text-amber-600" /> Accounts requiring attention
            </DialogTitle>
            <DialogDescription>
              Only the inboxes below have a sync issue. Healthy accounts are not listed here —
              see the green count in the header instead.
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-[460px] overflow-y-auto -mx-2 px-2 space-y-2" data-testid="issues-list">
            {statusAccounts
              .map((a) => ({ ...a, _status: classifyAccountStatus(a) }))
              .filter((a) => !a._status.healthy)
              .map((a) => {
                const isErr = a._status.severity === "error";
                return (
                  <div
                    key={a.account_id}
                    className={`rounded-lg border p-3 ${
                      isErr
                        ? "border-rose-200 bg-rose-50/40"
                        : "border-amber-200 bg-amber-50/40"
                    }`}
                    data-testid={`issue-account-${a.account_id}`}
                  >
                    <div className="flex items-start justify-between gap-3 flex-wrap">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 min-w-0">
                          <Mail size={14} className="text-slate-500 shrink-0" />
                          <span className="text-sm font-semibold text-slate-900 truncate">
                            {a.email}
                          </span>
                        </div>
                        <div
                          className={`text-xs mt-1 inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-medium ${
                            isErr
                              ? "bg-rose-100 text-rose-700"
                              : "bg-amber-100 text-amber-700"
                          }`}
                        >
                          {a._status.label}
                        </div>
                        <div className="text-xs text-slate-600 mt-1.5">
                          {a._status.detail}
                        </div>
                        {a.imap_last_sync_at && a._status.label !== "Receiving" && (
                          <div className="text-[11px] text-slate-400 mt-1 inline-flex items-center gap-1">
                            <Clock size={10} />
                            Last successful sync: {formatTime(a.imap_last_sync_at)}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIssuesOpen(false)} data-testid="issues-close">
              Close
            </Button>
            <Button
              onClick={() => {
                setIssuesOpen(false);
                fetchStatus();
                fetchReplies();
              }}
              className="bg-amber-600 hover:bg-amber-700 text-white"
              data-testid="issues-refresh"
            >
              <RefreshCw size={14} className="mr-1.5" /> Re-check
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Phase 2 Batch B — Move-to-folder dialog */}
      <Dialog open={moveDialog} onOpenChange={(o) => !o && setMoveDialog(false)}>
        <DialogContent data-testid="move-dialog">
          <DialogHeader>
            <DialogTitle>Move {selectedIds.length} repl{selectedIds.length === 1 ? "y" : "ies"} to…</DialogTitle>
            <DialogDescription>
              Pick the brand / folder where these replies should land. This only re-files the selected
              replies — future replies will still auto-route to whatever folder is set on their campaign.
            </DialogDescription>
          </DialogHeader>
          <Select value={moveFolderId} onValueChange={setMoveFolderId}>
            <SelectTrigger data-testid="move-folder-select"><SelectValue placeholder="Select a brand / folder" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__unassigned__">Unassigned</SelectItem>
              {folders.map((f) => (
                <SelectItem key={f.folder_id} value={f.folder_id} data-testid={`move-folder-option-${f.folder_id}`}>
                  {f.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <DialogFooter>
            <Button variant="outline" onClick={() => setMoveDialog(false)} data-testid="move-cancel">Cancel</Button>
            <Button onClick={submitMove} disabled={moveBusy || !moveFolderId} data-testid="move-confirm">
              {moveBusy ? "Moving…" : "Move"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Phase 2 Batch B — Single-row domain DNE confirmation */}
      <Dialog open={!!dneDomainTarget} onOpenChange={(o) => !o && setDneDomainTarget("")}>
        <DialogContent data-testid="domain-dne-dialog">
          <DialogHeader>
            <DialogTitle className="text-rose-600">
              Suppress entire domain @{dneDomainTarget}?
            </DialogTitle>
            <DialogDescription>
              No email from <b>RouteMail</b> will be sent to any address on this domain after you confirm.
            </DialogDescription>
          </DialogHeader>
          {dneDomainPreview ? (
            <div className="text-sm space-y-1" data-testid="domain-dne-preview">
              <div className="text-slate-700">This will suppress approximately:</div>
              <ul className="ml-4 list-disc text-slate-600 text-xs space-y-0.5">
                <li><b>{dneDomainPreview.lead_count}</b> lead(s)</li>
                <li><b>{dneDomainPreview.list_contact_count}</b> contact(s) on email lists</li>
                <li><b>{dneDomainPreview.drip_contact_count}</b> drip contact(s)</li>
                <li><b>{dneDomainPreview.reply_count}</b> existing repl(y/ies) tracked</li>
              </ul>
            </div>
          ) : (
            <div className="text-sm text-slate-500">Calculating…</div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDneDomainTarget("")} data-testid="domain-dne-cancel">Cancel</Button>
            <Button
              onClick={confirmSingleDomainDne}
              disabled={dneBusy}
              className="bg-rose-600 hover:bg-rose-700 text-white"
              data-testid="domain-dne-confirm"
            >
              {dneBusy ? "Suppressing…" : "Suppress domain"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
