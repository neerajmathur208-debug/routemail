import { useState, useEffect, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Workflow,
  Plus,
  Play,
  Pause,
  Trash2,
  Eye,
  Copy,
  Edit2,
  Loader2,
  Download,
  Upload,
  Search,
  FileSpreadsheet,
  ArrowUpDown,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
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
import Sidebar from "../components/Sidebar";
import ExportReportDialog from "../components/ExportReportDialog";
import { api } from "../App";
import { toast } from "sonner";

const STATUS_STYLES = {
  draft: "bg-slate-100 text-slate-700",
  scheduled: "bg-violet-100 text-violet-700",
  running: "bg-emerald-100 text-emerald-700",
  paused: "bg-amber-100 text-amber-700",
  completed: "bg-blue-100 text-blue-700",
};

export default function DripCampaigns({ user, setUser }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [campaigns, setCampaigns] = useState([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [renameTarget, setRenameTarget] = useState(null);
  const [renameValue, setRenameValue] = useState("");
  const [renameBusy, setRenameBusy] = useState(false);
  const [duplicateBusy, setDuplicateBusy] = useState(null); // drip_id currently duplicating
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState("created_desc");
  const [exportOpen, setExportOpen] = useState(false);

  const filteredCampaigns = useMemo(() => {
    const q = search.trim().toLowerCase();
    let list = campaigns;
    if (q) {
      list = list.filter((c) => (c.name || "").toLowerCase().includes(q));
    }
    const sorted = [...list];
    const ts = (v) => {
      if (!v) return 0;
      const d = new Date(v);
      return Number.isNaN(d.getTime()) ? 0 : d.getTime();
    };
    switch (sortBy) {
      case "name_asc":
        sorted.sort((a, b) => (a.name || "").localeCompare(b.name || ""));
        break;
      case "name_desc":
        sorted.sort((a, b) => (b.name || "").localeCompare(a.name || ""));
        break;
      case "created_asc":
        sorted.sort((a, b) => ts(a.created_at) - ts(b.created_at));
        break;
      case "scheduled_asc":
        sorted.sort((a, b) => ts(a.schedule?.start_date) - ts(b.schedule?.start_date));
        break;
      case "status":
        sorted.sort((a, b) => (a.status || "").localeCompare(b.status || ""));
        break;
      case "created_desc":
      default:
        sorted.sort((a, b) => ts(b.created_at) - ts(a.created_at));
        break;
    }
    return sorted;
  }, [campaigns, search, sortBy]);

  const handleRename = async () => {
    if (!renameTarget) return;
    const name = renameValue.trim();
    if (!name) {
      toast.error("Name cannot be blank");
      return;
    }
    setRenameBusy(true);
    try {
      await api.post(`/drip-campaigns/${renameTarget.drip_id}/rename`, { name });
      toast.success("Drip campaign renamed");
      setRenameTarget(null);
      setRenameValue("");
      fetchCampaigns();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to rename");
    } finally {
      setRenameBusy(false);
    }
  };

  const handleDuplicate = async (camp) => {
    setDuplicateBusy(camp.drip_id);
    try {
      const res = await api.post(`/drip-campaigns/${camp.drip_id}/duplicate`);
      toast.success(`Duplicated as "${res.data.name}"`);
      fetchCampaigns();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to duplicate");
    } finally {
      setDuplicateBusy(null);
    }
  };

  const handleExport = async (camp) => {
    try {
      const res = await api.get(`/drip-campaigns/${camp.drip_id}/export`, {
        responseType: "blob",
      });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: "application/json" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `routemail-drip-${(camp.name || "export").replace(/\s+/g, "_").slice(0, 48)}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success("Drip campaign exported");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Export failed");
    }
  };

  const handleImportFile = async (file) => {
    if (!file) return;
    try {
      const text = await file.text();
      const payload = JSON.parse(text);
      const res = await api.post("/drip-campaigns/import", payload);
      toast.success(`Imported "${res.data.name}" (${res.data.steps_imported} step(s))`);
      fetchCampaigns();
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || "Import failed");
    }
  };

  const fetchCampaigns = useCallback(async () => {
    try {
      const res = await api.get("/drip-campaigns");
      setCampaigns(res.data || []);
    } catch (e) {
      console.error("Failed to load drip campaigns", e);
      toast.error("Failed to load drip campaigns");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCampaigns();
  }, [fetchCampaigns]);

  const handleCreate = async () => {
    if (!newName.trim()) {
      toast.error("Name is required");
      return;
    }
    setCreating(true);
    try {
      const res = await api.post("/drip-campaigns", {
        name: newName.trim(),
        steps: [],
        schedule: {
          timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
          sending_days: [0, 1, 2, 3, 4],
          start_time: "09:00",
          end_time: "18:00",
          randomize_time: false,
        },
        stop_on_reply: true,
        stop_on_bounce: true,
        account_ids: [],
      });
      toast.success("Drip campaign created");
      setCreateOpen(false);
      setNewName("");
      navigate(`/drip-campaigns/${res.data.drip_id}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to create");
    } finally {
      setCreating(false);
    }
  };

  const handleToggle = async (camp) => {
    try {
      if (camp.status === "running") {
        await api.post(`/drip-campaigns/${camp.drip_id}/pause`);
        toast.success("Campaign paused");
      } else if (camp.status === "paused") {
        await api.post(`/drip-campaigns/${camp.drip_id}/resume`);
        toast.success("Campaign resumed");
      } else {
        await api.post(`/drip-campaigns/${camp.drip_id}/start`);
        toast.success("Campaign started");
      }
      fetchCampaigns();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Action failed");
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await api.delete(`/drip-campaigns/${deleteTarget.drip_id}`);
      toast.success("Drip campaign deleted");
      setDeleteTarget(null);
      fetchCampaigns();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Delete failed");
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex">
      <Sidebar user={user} setUser={setUser} />
      <main className="flex-1 p-6 lg:p-10 max-w-[1400px]">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.3 }}
          className="flex items-center justify-between mb-8"
        >
          <div>
            <div className="flex items-center gap-3 mb-2">
              <Workflow className="text-violet-600" size={28} strokeWidth={1.5} />
              <h1 className="text-3xl font-bold text-slate-900">Drip Campaigns</h1>
            </div>
            <p className="text-slate-600">
              Build multi-step email sequences with smart timezone scheduling and randomization
            </p>
          </div>
          <div className="flex items-center gap-2">
            <input
              type="file"
              accept=".json,application/json"
              id="drip-import-file-input"
              className="hidden"
              data-testid="drip-import-file-input"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleImportFile(f);
                e.target.value = "";
              }}
            />
            <Button
              variant="outline"
              onClick={() => document.getElementById("drip-import-file-input").click()}
              data-testid="drip-import-btn"
            >
              <Upload size={16} className="mr-1.5" /> Import
            </Button>
            <Button
              variant="outline"
              onClick={() => setExportOpen(true)}
              data-testid="drip-export-report-btn"
              className="border-violet-300 text-violet-700 hover:bg-violet-50"
            >
              <FileSpreadsheet size={16} className="mr-1.5" /> Export Report
            </Button>
            <Button
              data-testid="drip-create-btn"
              onClick={() => setCreateOpen(true)}
              className="bg-violet-600 hover:bg-violet-700 text-white"
            >
              <Plus size={18} className="mr-2" /> New Drip
            </Button>
          </div>
        </motion.div>

        {loading ? (
          <div className="text-slate-500">Loading…</div>
        ) : campaigns.length === 0 ? (
          <div
            data-testid="drip-empty-state"
            className="bg-white border border-dashed border-slate-300 rounded-2xl p-16 text-center"
          >
            <Workflow className="mx-auto text-slate-400 mb-4" size={48} strokeWidth={1.2} />
            <h3 className="text-xl font-semibold text-slate-900 mb-2">
              No drip campaigns yet
            </h3>
            <p className="text-slate-500 mb-6 max-w-md mx-auto">
              Create sequenced emails that automatically go out over days or weeks, with sending
              windows, randomization and stop-on-reply rules.
            </p>
            <Button
              onClick={() => setCreateOpen(true)}
              className="bg-violet-600 hover:bg-violet-700 text-white"
              data-testid="drip-empty-create-btn"
            >
              <Plus size={18} className="mr-2" /> Create your first drip
            </Button>
          </div>
        ) : (
          <>
            {/* Filter + sort row */}
            <div
              className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-4"
              data-testid="drip-list-toolbar"
            >
              <div className="relative flex-1 max-w-md">
                <Search
                  size={16}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"
                />
                <Input
                  data-testid="drip-search-input"
                  placeholder="Search Drip Campaigns"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-9"
                />
              </div>
              <div className="flex items-center gap-2">
                <ArrowUpDown size={14} className="text-slate-500" />
                <Select value={sortBy} onValueChange={setSortBy}>
                  <SelectTrigger className="w-56" data-testid="drip-sort-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="created_desc">Newest first</SelectItem>
                    <SelectItem value="created_asc">Oldest first</SelectItem>
                    <SelectItem value="name_asc">Name A → Z</SelectItem>
                    <SelectItem value="name_desc">Name Z → A</SelectItem>
                    <SelectItem value="scheduled_asc">Scheduled start (earliest)</SelectItem>
                    <SelectItem value="status">Status</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* List view */}
            <div
              data-testid="drip-list-view"
              className="bg-white border border-slate-200 rounded-2xl overflow-hidden"
            >
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium">Name</th>
                      <th className="text-left px-3 py-3 font-medium">Status</th>
                      <th className="text-left px-3 py-3 font-medium">List</th>
                      <th className="text-right px-3 py-3 font-medium">Contacts</th>
                      <th className="text-right px-3 py-3 font-medium">Steps</th>
                      <th className="text-left px-3 py-3 font-medium">Scheduled Start</th>
                      <th className="text-left px-3 py-3 font-medium">Created</th>
                      <th className="text-left px-3 py-3 font-medium">Last Modified</th>
                      <th className="text-right px-4 py-3 font-medium">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCampaigns.length === 0 ? (
                      <tr>
                        <td colSpan={9} className="px-4 py-10 text-center text-slate-500" data-testid="drip-no-search-results">
                          No drip campaigns match &ldquo;{search}&rdquo;
                        </td>
                      </tr>
                    ) : (
                      filteredCampaigns.map((camp) => (
                        <DripRow
                          key={camp.drip_id}
                          camp={camp}
                          onOpen={() => navigate(`/drip-campaigns/${camp.drip_id}`)}
                          onRename={() => {
                            setRenameTarget(camp);
                            setRenameValue(camp.name || "");
                          }}
                          onDuplicate={() => handleDuplicate(camp)}
                          duplicateBusy={duplicateBusy === camp.drip_id}
                          onExport={() => handleExport(camp)}
                          onToggle={() => handleToggle(camp)}
                          onDelete={() => setDeleteTarget(camp)}
                        />
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* Create dialog */}
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogContent data-testid="drip-create-dialog">
            <DialogHeader>
              <DialogTitle>New Drip Campaign</DialogTitle>
              <DialogDescription>
                Give your sequence a name. You can add steps, contacts, and scheduling on the next
                screen.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-2">
              <Label htmlFor="drip-name">Campaign name</Label>
              <Input
                id="drip-name"
                data-testid="drip-name-input"
                placeholder="e.g. Q1 Outreach Sequence"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              />
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setCreateOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleCreate}
                disabled={creating}
                className="bg-violet-600 hover:bg-violet-700 text-white"
                data-testid="drip-create-confirm-btn"
              >
                {creating ? "Creating…" : "Create & continue"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Delete confirm */}
        <AlertDialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
          <AlertDialogContent data-testid="drip-delete-dialog">
            <AlertDialogHeader>
              <AlertDialogTitle>Delete this drip campaign?</AlertDialogTitle>
              <AlertDialogDescription>
                “{deleteTarget?.name}” and all of its enrolled contacts & logs will be permanently
                removed. This cannot be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleDelete}
                className="bg-red-600 hover:bg-red-700"
                data-testid="drip-delete-confirm-btn"
              >
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
        {/* Rename dialog */}
        <Dialog open={!!renameTarget} onOpenChange={(o) => !o && setRenameTarget(null)}>
          <DialogContent data-testid="drip-rename-dialog">
            <DialogHeader>
              <DialogTitle>Rename drip campaign</DialogTitle>
              <DialogDescription>
                Only the campaign name changes. Schedule, steps, contacts, logs, and analytics stay
                exactly as they are.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-2">
              <Label htmlFor="rename-input">Campaign name</Label>
              <Input
                id="rename-input"
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleRename()}
                data-testid="drip-rename-input"
                autoFocus
              />
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setRenameTarget(null)} disabled={renameBusy}>
                Cancel
              </Button>
              <Button onClick={handleRename} disabled={renameBusy || !renameValue.trim()} data-testid="drip-rename-confirm">
                {renameBusy ? <Loader2 size={14} className="animate-spin mr-2" /> : null}
                Save
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Export Report dialog */}
        <ExportReportDialog
          open={exportOpen}
          onOpenChange={setExportOpen}
          lockType="drip"
          title="Export Drip Campaign Report"
        />

      </main>
    </div>
  );
}

function DripRow({
  camp,
  onOpen,
  onRename,
  onDuplicate,
  duplicateBusy,
  onExport,
  onToggle,
  onDelete,
}) {
  const tz = camp.schedule?.timezone || "UTC";
  const startDate = camp.schedule?.start_date;
  const startTime = camp.schedule?.start_time || "";
  const created = camp.created_at ? new Date(camp.created_at).toLocaleDateString() : "—";
  const modified = camp.updated_at ? new Date(camp.updated_at).toLocaleDateString() : "—";
  const stepCount = (camp.steps || []).length;
  const scheduledStartDisplay = startDate
    ? `${new Date(`${startDate}T${startTime || "00:00"}:00`).toLocaleDateString(undefined, {
        day: "2-digit",
        month: "short",
        year: "numeric",
      })}${startTime ? ` ${startTime}` : ""} (${tz})`
    : "—";

  return (
    <motion.tr
      data-testid={`drip-row-${camp.drip_id}`}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="border-t border-slate-100 hover:bg-slate-50 align-middle"
    >
      <td className="px-4 py-3">
        <button
          onClick={onOpen}
          className="font-medium text-slate-900 hover:text-violet-700 text-left"
          data-testid={`drip-name-link-${camp.drip_id}`}
        >
          {camp.name || "Untitled"}
        </button>
      </td>
      <td className="px-3 py-3">
        <span
          data-testid={`drip-status-badge-${camp.drip_id}`}
          className={`px-2.5 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${
            STATUS_STYLES[camp.status] || "bg-slate-100 text-slate-700"
          }`}
        >
          {camp.status || "draft"}
        </span>
      </td>
      <td className="px-3 py-3 text-slate-600 truncate max-w-[160px]">
        {camp.list_name || "—"}
      </td>
      <td className="px-3 py-3 text-right tabular-nums text-slate-900">
        {camp.total_contacts || 0}
      </td>
      <td className="px-3 py-3 text-right tabular-nums text-slate-900">{stepCount}</td>
      <td className="px-3 py-3 text-slate-600 whitespace-nowrap">{scheduledStartDisplay}</td>
      <td className="px-3 py-3 text-slate-600 whitespace-nowrap">{created}</td>
      <td className="px-3 py-3 text-slate-600 whitespace-nowrap">{modified}</td>
      <td className="px-4 py-3 text-right">
        <div className="flex items-center justify-end gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={onOpen}
            data-testid={`drip-view-${camp.drip_id}`}
            title="Open / Edit"
          >
            <Eye size={15} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={onRename}
            data-testid={`drip-rename-${camp.drip_id}`}
            title="Rename"
          >
            <Edit2 size={15} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={onDuplicate}
            disabled={duplicateBusy}
            data-testid={`drip-duplicate-${camp.drip_id}`}
            title="Duplicate"
          >
            {duplicateBusy ? <Loader2 size={15} className="animate-spin" /> : <Copy size={15} />}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={onExport}
            data-testid={`drip-export-${camp.drip_id}`}
            title="Export as JSON"
          >
            <Download size={15} />
          </Button>
          {(camp.status === "running" || camp.status === "paused") && (
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={onToggle}
              data-testid={`drip-toggle-${camp.drip_id}`}
              title={camp.status === "running" ? "Pause" : "Resume"}
            >
              {camp.status === "running" ? <Pause size={15} /> : <Play size={15} />}
            </Button>
          )}
          {camp.status !== "running" && (
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-red-500 hover:text-red-600 hover:bg-red-50"
              onClick={onDelete}
              data-testid={`drip-delete-${camp.drip_id}`}
              title="Delete"
            >
              <Trash2 size={15} />
            </Button>
          )}
        </div>
      </td>
    </motion.tr>
  );
}
