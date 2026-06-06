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
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ unread_only: false, account_id: "" });
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedReply, setSelectedReply] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [statusAccounts, setStatusAccounts] = useState([]);
  const [folders, setFolders] = useState([]);
  const [saveDialog, setSaveDialog] = useState(false);
  const [saveFolderId, setSaveFolderId] = useState("");
  const [newFolderName, setNewFolderName] = useState("");
  const [saveBusy, setSaveBusy] = useState(false);
  const [dneDialogOpen, setDneDialogOpen] = useState(false);
  const [dneScope, setDneScope] = useState("email"); // "email" | "domain"
  const [dneBusy, setDneBusy] = useState(false);
  const [issuesOpen, setIssuesOpen] = useState(false);

  const fetchReplies = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filter.unread_only) params.set("unread_only", "true");
      if (filter.account_id) params.set("account_id", filter.account_id);
      const res = await api.get(`/unibox/replies?${params}`);
      setReplies(res.data.items || []);
      setUnreadCount(res.data.unread_count || 0);
    } catch (err) {
      toast.error("Failed to load replies");
    } finally {
      setLoading(false);
    }
  }, [filter]);

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

  useEffect(() => {
    Promise.all([fetchReplies(), fetchStatus(), fetchFolders()]);
  }, [fetchReplies, fetchStatus, fetchFolders]);

  const toggleSel = (id) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };
  const clearSel = () => setSelectedIds([]);
  const allSelected = selectedIds.length > 0 && selectedIds.length === filteredReplies().length;

  function filteredReplies() {
    const term = searchTerm.trim().toLowerCase();
    if (!term) return replies;
    return replies.filter(
      (r) =>
        (r.from_email || "").toLowerCase().includes(term) ||
        (r.subject || "").toLowerCase().includes(term) ||
        (r.body || "").toLowerCase().includes(term)
    );
  }

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

  const renderReplyRow = (r) => {
    const sel = selectedIds.includes(r.reply_id);
    return (
      <motion.div
        key={r.reply_id}
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        className={`border rounded-md p-4 mb-2 cursor-pointer transition-colors ${
          sel ? "border-blue-300 bg-blue-50/40" : "border-slate-200 bg-white hover:border-slate-300"
        } ${!r.read ? "ring-1 ring-blue-200" : ""}`}
        onClick={() => setSelectedReply(r)}
        data-testid={`reply-row-${r.reply_id}`}
      >
        <div className="flex items-start gap-3">
          <button
            onClick={(e) => {
              e.stopPropagation();
              toggleSel(r.reply_id);
            }}
            className="mt-1"
            data-testid={`reply-select-${r.reply_id}`}
            aria-label={sel ? "Deselect" : "Select"}
          >
            {sel ? <CheckSquare size={16} className="text-blue-600" /> : <Square size={16} className="text-slate-400" />}
          </button>
          <div className="flex-1 min-w-0">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 min-w-0">
                {!r.read && <span className="w-2 h-2 rounded-full bg-blue-500 flex-shrink-0" />}
                <span className="font-semibold text-slate-900 truncate">{r.from_email}</span>
                {(r.campaign_name || r.drip_campaign_name) && (
                  <Badge className="bg-violet-100 text-violet-700 border border-violet-200 hover:bg-violet-100 text-xs">
                    {r.campaign_name || r.drip_campaign_name}
                    {r.drip_step_number != null && ` · step ${r.drip_step_number + 1}`}
                  </Badge>
                )}
              </div>
              <span className="text-xs text-slate-500 flex-shrink-0">{formatTime(r.received_at)}</span>
            </div>
            <p className="text-sm text-slate-700 truncate mt-0.5">{r.subject || "(no subject)"}</p>
            <p className="text-xs text-slate-500 truncate mt-1">{(r.body || "").slice(0, 160)}</p>
            <p className="text-xs text-slate-400 mt-1">received on {r.received_on_email}</p>
          </div>
        </div>
      </motion.div>
    );
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
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-[200px] max-w-md">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <Input
                placeholder="Search replies…"
                className="pl-9"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                data-testid="unibox-search"
              />
            </div>
            <Select
              value={filter.unread_only ? "unread" : "all"}
              onValueChange={(v) => setFilter({ ...filter, unread_only: v === "unread" })}
            >
              <SelectTrigger className="w-40" data-testid="filter-status">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All replies</SelectItem>
                <SelectItem value="unread">Unread only</SelectItem>
              </SelectContent>
            </Select>
            <Select
              value={filter.account_id || "_all"}
              onValueChange={(v) => setFilter({ ...filter, account_id: v === "_all" ? "" : v })}
            >
              <SelectTrigger className="w-56" data-testid="filter-account">
                <SelectValue placeholder="Filter by account" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="_all">All accounts</SelectItem>
                {statusAccounts.map((a) => (
                  <SelectItem key={a.account_id} value={a.account_id}>
                    {a.email}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
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

          {/* Replies list */}
          {loading ? (
            <p className="text-sm text-slate-500" data-testid="unibox-loading">Loading…</p>
          ) : filteredReplies().length === 0 ? (
            <div className="bg-white border border-dashed border-slate-200 rounded-md p-12 text-center" data-testid="unibox-empty">
              <Inbox className="mx-auto text-slate-300" size={36} />
              <p className="font-medium text-slate-700 mt-2">No replies yet</p>
              <p className="text-sm text-slate-500 mt-1">
                Replies will appear here as soon as IMAP sync picks them up. Make sure your accounts have IMAP receiving settings configured.
              </p>
            </div>
          ) : (
            <div data-testid="reply-list">
              {filteredReplies().length > 0 && (
                <button
                  className="text-xs text-slate-500 hover:text-slate-700 mb-2 flex items-center gap-1"
                  onClick={() => (allSelected ? clearSel() : setSelectedIds(filteredReplies().map((r) => r.reply_id)))}
                  data-testid="unibox-select-all"
                >
                  {allSelected ? <CheckSquare size={14} className="text-blue-600" /> : <Square size={14} />}
                  {allSelected ? "Deselect all" : "Select all visible"}
                </button>
              )}
              {filteredReplies().map(renderReplyRow)}
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
    </div>
  );
}
