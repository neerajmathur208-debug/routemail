import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Folder,
  FolderPlus,
  Trash2,
  Edit2,
  Star,
  Mail,
  Calendar,
  ChevronRight,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
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
import Sidebar from "../components/Sidebar";
import { api } from "../App";
import { toast } from "sonner";

function fmtDate(ts) {
  if (!ts) return "";
  return new Date(ts).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export default function Leads({ user, setUser }) {
  const [folders, setFolders] = useState([]);
  const [activeFolder, setActiveFolder] = useState(null);
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(false);

  // Create folder
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);

  // Rename folder
  const [renameOpen, setRenameOpen] = useState(false);
  const [renameValue, setRenameValue] = useState("");
  const [renameTarget, setRenameTarget] = useState(null);

  // Delete folder
  const [deleteTarget, setDeleteTarget] = useState(null);

  // Detail dialog
  const [selectedLead, setSelectedLead] = useState(null);

  const fetchFolders = useCallback(async () => {
    try {
      const res = await api.get("/leads/folders");
      const list = res.data.folders || [];
      setFolders(list);
      // Sync activeFolder with the freshly fetched version (without re-running on activeFolder change)
      setActiveFolder((prev) => {
        if (!prev) return list[0] || null;
        const updated = list.find((f) => f.folder_id === prev.folder_id);
        return updated || list[0] || null;
      });
    } catch (err) {
      toast.error("Failed to load folders");
    }
  }, []);

  const fetchLeads = useCallback(async () => {
    if (!activeFolder) return;
    setLoading(true);
    try {
      const res = await api.get(`/leads?folder_id=${activeFolder.folder_id}`);
      setLeads(res.data.items || []);
    } catch (err) {
      toast.error("Failed to load leads");
    } finally {
      setLoading(false);
    }
  }, [activeFolder]);

  useEffect(() => {
    fetchFolders();
  }, [fetchFolders]);

  useEffect(() => {
    fetchLeads();
  }, [fetchLeads]);

  const createFolder = async () => {
    const name = newName.trim();
    if (!name) return;
    setCreating(true);
    try {
      const res = await api.post("/leads/folders", { name });
      toast.success("Folder created");
      setCreateOpen(false);
      setNewName("");
      await fetchFolders();
      setActiveFolder(res.data);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to create folder");
    } finally {
      setCreating(false);
    }
  };

  const renameFolder = async () => {
    if (!renameTarget) return;
    try {
      await api.put(`/leads/folders/${renameTarget.folder_id}`, { name: renameValue });
      toast.success("Folder renamed");
      setRenameOpen(false);
      await fetchFolders();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to rename folder");
    }
  };

  const deleteFolder = async () => {
    if (!deleteTarget) return;
    try {
      await api.delete(`/leads/folders/${deleteTarget.folder_id}`);
      toast.success("Folder deleted");
      setDeleteTarget(null);
      if (activeFolder?.folder_id === deleteTarget.folder_id) {
        setActiveFolder(null);
      }
      await fetchFolders();
    } catch (err) {
      toast.error("Failed to delete folder");
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
                <Star size={28} className="text-amber-500" />
                Responses / Leads
              </h1>
              <p className="text-sm text-slate-500 mt-1">
                Organise important replies into folders. Save anything from the Unibox.
              </p>
            </div>
            <Button onClick={() => setCreateOpen(true)} data-testid="new-folder-btn">
              <FolderPlus size={14} className="mr-2" />
              New Folder
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-12 gap-6">
            {/* Folder list */}
            <aside className="md:col-span-4 space-y-1" data-testid="folder-list">
              {folders.length === 0 ? (
                <div className="bg-white border border-dashed border-slate-200 rounded-md p-6 text-center">
                  <Folder className="mx-auto text-slate-300" size={32} />
                  <p className="text-sm text-slate-500 mt-2">
                    No folders yet. Create one to start saving leads.
                  </p>
                </div>
              ) : (
                folders.map((f) => (
                  <button
                    key={f.folder_id}
                    onClick={() => setActiveFolder(f)}
                    data-testid={`folder-${f.folder_id}`}
                    className={`w-full text-left px-3 py-2.5 rounded-md flex items-center gap-2 transition-colors ${
                      activeFolder?.folder_id === f.folder_id
                        ? "bg-white border border-slate-300 shadow-sm"
                        : "hover:bg-white border border-transparent"
                    }`}
                  >
                    <Folder
                      size={16}
                      className={activeFolder?.folder_id === f.folder_id ? "text-amber-500" : "text-slate-400"}
                    />
                    <span className="flex-1 truncate text-sm font-medium text-slate-700">{f.name}</span>
                    <span className="text-xs text-slate-400">{f.lead_count}</span>
                    {activeFolder?.folder_id === f.folder_id && (
                      <ChevronRight size={14} className="text-slate-400" />
                    )}
                  </button>
                ))
              )}
            </aside>

            {/* Lead list */}
            <section className="md:col-span-8" data-testid="lead-detail-section">
              {activeFolder ? (
                <>
                  <div className="flex items-center justify-between mb-3">
                    <h2 className="font-heading font-semibold text-lg text-slate-900 flex items-center gap-2">
                      <Folder size={18} className="text-amber-500" />
                      {activeFolder.name}
                      <span className="text-slate-400 text-sm">({activeFolder.lead_count})</span>
                    </h2>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setRenameTarget(activeFolder);
                          setRenameValue(activeFolder.name);
                          setRenameOpen(true);
                        }}
                        data-testid="rename-folder-btn"
                      >
                        <Edit2 size={14} />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setDeleteTarget(activeFolder)}
                        className="text-red-600 hover:bg-red-50"
                        data-testid="delete-folder-btn"
                      >
                        <Trash2 size={14} />
                      </Button>
                    </div>
                  </div>

                  {loading ? (
                    <p className="text-sm text-slate-500">Loading…</p>
                  ) : leads.length === 0 ? (
                    <div className="bg-white border border-dashed border-slate-200 rounded-md p-10 text-center" data-testid="leads-empty">
                      <Mail className="mx-auto text-slate-300" size={28} />
                      <p className="text-sm text-slate-500 mt-2">
                        No leads in this folder yet. Open the Unibox to save replies here.
                      </p>
                    </div>
                  ) : (
                    <div className="space-y-2" data-testid="leads-list">
                      {leads.map((l) => (
                        <motion.button
                          key={l.lead_id}
                          initial={{ opacity: 0, y: 5 }}
                          animate={{ opacity: 1, y: 0 }}
                          onClick={() => setSelectedLead(l)}
                          className="w-full text-left bg-white border border-slate-200 rounded-md p-4 hover:border-slate-300 transition-colors"
                          data-testid={`lead-${l.lead_id}`}
                        >
                          <div className="flex items-center justify-between gap-3">
                            <span className="font-semibold text-slate-900 truncate">
                              {l.contact_name || l.contact_email}
                            </span>
                            <span className="text-xs text-slate-500 flex-shrink-0 flex items-center gap-1">
                              <Calendar size={11} />
                              {fmtDate(l.received_at || l.saved_at)}
                            </span>
                          </div>
                          <p className="text-sm text-slate-700 truncate mt-0.5">{l.subject}</p>
                          <p className="text-xs text-slate-500 truncate mt-1">{(l.body || "").slice(0, 140)}</p>
                          {l.campaign_name && (
                            <p className="text-xs text-violet-600 mt-1">{l.campaign_name}</p>
                          )}
                        </motion.button>
                      ))}
                    </div>
                  )}
                </>
              ) : (
                <div className="bg-white border border-dashed border-slate-200 rounded-md p-12 text-center">
                  <Folder className="mx-auto text-slate-300" size={36} />
                  <p className="font-medium text-slate-700 mt-2">Select a folder</p>
                  <p className="text-sm text-slate-500 mt-1">Pick one from the left or create a new one.</p>
                </div>
              )}
            </section>
          </div>
        </div>
      </main>

      {/* Create folder */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent data-testid="create-folder-dialog">
          <DialogHeader>
            <DialogTitle>New folder</DialogTitle>
            <DialogDescription>Organise saved responses by category, customer, or pipeline stage.</DialogDescription>
          </DialogHeader>
          <Label className="text-xs text-slate-500">Folder name</Label>
          <Input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="e.g. Hot Leads"
            data-testid="create-folder-input"
            onKeyDown={(e) => e.key === "Enter" && createFolder()}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={creating}>Cancel</Button>
            <Button onClick={createFolder} disabled={creating || !newName.trim()} data-testid="create-folder-confirm">
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Rename folder */}
      <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename folder</DialogTitle>
          </DialogHeader>
          <Input value={renameValue} onChange={(e) => setRenameValue(e.target.value)} data-testid="rename-folder-input" />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenameOpen(false)}>Cancel</Button>
            <Button onClick={renameFolder} data-testid="rename-folder-confirm">Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete folder */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete folder?</AlertDialogTitle>
            <AlertDialogDescription>
              "{deleteTarget?.name}" and all {deleteTarget?.lead_count} lead{deleteTarget?.lead_count === 1 ? "" : "s"} inside will be permanently removed.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={deleteFolder} className="bg-red-600 hover:bg-red-700" data-testid="delete-folder-confirm">
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Lead detail */}
      <Dialog open={!!selectedLead} onOpenChange={(o) => !o && setSelectedLead(null)}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{selectedLead?.subject}</DialogTitle>
            <DialogDescription>
              From <span className="font-medium">{selectedLead?.contact_email}</span> · received on{" "}
              {selectedLead?.received_on_email} · {fmtDate(selectedLead?.received_at)}
              {selectedLead?.campaign_name && <> · {selectedLead.campaign_name}</>}
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-[60vh] overflow-y-auto whitespace-pre-wrap text-sm text-slate-800 bg-slate-50 rounded p-3">
            {selectedLead?.body || "(empty)"}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
