import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Shield,
  Plus,
  Trash2,
  Eye,
  Users,
  Lock,
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
import Sidebar from "../components/Sidebar";
import { api } from "../App";
import { toast } from "sonner";

export default function DoNotEmail({ user, setUser }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [lists, setLists] = useState([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [creating, setCreating] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);

  const fetchLists = useCallback(async () => {
    try {
      const res = await api.get("/dne-lists");
      setLists(res.data || []);
    } catch (e) {
      console.error(e);
      toast.error("Failed to load Do Not Email lists");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLists();
  }, [fetchLists]);

  const handleCreate = async () => {
    if (!newName.trim()) {
      toast.error("Name is required");
      return;
    }
    setCreating(true);
    try {
      const res = await api.post("/dne-lists", { name: newName.trim() });
      toast.success("Do Not Email list created");
      setCreateOpen(false);
      setNewName("");
      navigate(`/do-not-email/${res.data.list_id}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to create");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await api.delete(`/dne-lists/${deleteTarget.list_id}`);
      toast.success("List deleted");
      setDeleteTarget(null);
      fetchLists();
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
          className="flex items-center justify-between mb-8"
        >
          <div>
            <div className="flex items-center gap-3 mb-2">
              <Shield className="text-rose-600" size={28} strokeWidth={1.5} />
              <h1 className="text-3xl font-bold text-slate-900">Do Not Email</h1>
            </div>
            <p className="text-slate-600 max-w-2xl">
              Maintain suppression lists to guarantee contacts are never emailed — applied
              in real-time across standard campaigns and drip sequences.
            </p>
          </div>
          <Button
            data-testid="dne-create-btn"
            onClick={() => setCreateOpen(true)}
            className="bg-rose-600 hover:bg-rose-700 text-white"
          >
            <Plus size={18} className="mr-2" /> New list
          </Button>
        </motion.div>

        {loading ? (
          <div className="text-slate-500">Loading…</div>
        ) : lists.length === 0 ? (
          <div className="bg-white border border-dashed border-slate-300 rounded-2xl p-16 text-center">
            <Shield className="mx-auto text-slate-400 mb-4" size={48} strokeWidth={1.2} />
            <h3 className="text-xl font-semibold text-slate-900 mb-2">
              No suppression lists yet
            </h3>
            <Button
              onClick={() => setCreateOpen(true)}
              className="bg-rose-600 hover:bg-rose-700 text-white"
            >
              <Plus size={18} className="mr-2" /> Create your first list
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
            {lists.map((list) => (
              <motion.div
                key={list.list_id}
                data-testid={`dne-card-${list.list_id}`}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className={`bg-white border rounded-2xl p-5 hover:shadow-md transition-shadow ${
                  list.is_global ? "border-rose-200 bg-rose-50/30" : "border-slate-200"
                }`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div
                    className="flex-1 min-w-0 cursor-pointer"
                    onClick={() => navigate(`/do-not-email/${list.list_id}`)}
                  >
                    <h3 className="font-semibold text-slate-900 truncate text-lg flex items-center gap-2">
                      {list.name}
                      {list.is_global && (
                        <span
                          className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wide bg-rose-100 text-rose-700 px-2 py-0.5 rounded-full"
                          title="Applied to every campaign automatically"
                        >
                          <Lock size={10} /> Global
                        </span>
                      )}
                    </h3>
                    <p className="text-xs text-slate-500 mt-1">
                      Created {new Date(list.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 text-slate-600 mb-4">
                  <Users size={14} strokeWidth={1.5} />
                  <span className="text-sm">
                    <span className="font-semibold text-slate-900">
                      {list.email_count || 0}
                    </span>{" "}
                    suppressed email{list.email_count === 1 ? "" : "s"}
                  </span>
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={() => navigate(`/do-not-email/${list.list_id}`)}
                    data-testid={`dne-view-${list.list_id}`}
                  >
                    <Eye size={14} className="mr-1.5" /> Open
                  </Button>
                  {!list.is_global && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-500 hover:text-red-600 hover:bg-red-50"
                      onClick={() => setDeleteTarget(list)}
                      data-testid={`dne-delete-${list.list_id}`}
                    >
                      <Trash2 size={14} />
                    </Button>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        )}

        {/* Create dialog */}
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogContent data-testid="dne-create-dialog">
            <DialogHeader>
              <DialogTitle>New Do Not Email list</DialogTitle>
              <DialogDescription>
                Give it a name. You'll add emails (manual or CSV/Excel upload) on the next screen.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-2">
              <Label htmlFor="dne-name">List name</Label>
              <Input
                id="dne-name"
                data-testid="dne-name-input"
                placeholder="e.g. Competitors / Partners / VIP exclusions"
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
                className="bg-rose-600 hover:bg-rose-700 text-white"
                data-testid="dne-create-confirm-btn"
              >
                {creating ? "Creating…" : "Create & continue"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Delete confirm */}
        <AlertDialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
          <AlertDialogContent data-testid="dne-delete-dialog">
            <AlertDialogHeader>
              <AlertDialogTitle>Delete this Do Not Email list?</AlertDialogTitle>
              <AlertDialogDescription>
                “{deleteTarget?.name}” and all of its {deleteTarget?.email_count || 0}{" "}
                suppressed emails will be removed and unlinked from any campaigns. This cannot
                be undone.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>Cancel</AlertDialogCancel>
              <AlertDialogAction
                onClick={handleDelete}
                className="bg-red-600 hover:bg-red-700"
                data-testid="dne-delete-confirm-btn"
              >
                Delete
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </main>
    </div>
  );
}
