import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Workflow,
  Plus,
  Play,
  Pause,
  Trash2,
  Eye,
  Users,
  Send,
  ArrowRight,
  Clock,
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

const STATUS_STYLES = {
  draft: "bg-slate-100 text-slate-700",
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
          <Button
            data-testid="drip-create-btn"
            onClick={() => setCreateOpen(true)}
            className="bg-violet-600 hover:bg-violet-700 text-white"
          >
            <Plus size={18} className="mr-2" /> New Drip
          </Button>
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
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
            {campaigns.map((camp) => (
              <motion.div
                key={camp.drip_id}
                data-testid={`drip-card-${camp.drip_id}`}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                className="bg-white border border-slate-200 rounded-2xl p-5 hover:shadow-md transition-shadow"
              >
                <div className="flex items-start justify-between mb-4">
                  <div
                    className="flex-1 min-w-0 cursor-pointer"
                    onClick={() => navigate(`/drip-campaigns/${camp.drip_id}`)}
                  >
                    <h3 className="font-semibold text-slate-900 truncate text-lg">
                      {camp.name}
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {new Date(camp.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <span
                    className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${
                      STATUS_STYLES[camp.status] || "bg-slate-100 text-slate-700"
                    }`}
                  >
                    {camp.status}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-3 mb-4">
                  <Stat label="Steps" value={(camp.steps || []).length} icon={ArrowRight} />
                  <Stat label="Contacts" value={camp.total_contacts || 0} icon={Users} />
                  <Stat label="Sent" value={camp.total_sent || 0} icon={Send} />
                </div>

                <div className="text-xs text-slate-500 flex items-center gap-1.5 mb-4">
                  <Clock size={12} /> {camp.schedule?.timezone || "UTC"} •{" "}
                  {camp.schedule?.start_time || "09:00"}–{camp.schedule?.end_time || "18:00"}
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={() => navigate(`/drip-campaigns/${camp.drip_id}`)}
                    data-testid={`drip-view-${camp.drip_id}`}
                  >
                    <Eye size={14} className="mr-1.5" /> Open
                  </Button>
                  {(camp.status === "running" || camp.status === "paused") && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleToggle(camp)}
                      data-testid={`drip-toggle-${camp.drip_id}`}
                    >
                      {camp.status === "running" ? (
                        <><Pause size={14} className="mr-1.5" /> Pause</>
                      ) : (
                        <><Play size={14} className="mr-1.5" /> Resume</>
                      )}
                    </Button>
                  )}
                  {camp.status !== "running" && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-500 hover:text-red-600 hover:bg-red-50"
                      onClick={() => setDeleteTarget(camp)}
                      data-testid={`drip-delete-${camp.drip_id}`}
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
      </main>
    </div>
  );
}

function Stat({ label, value, icon: Icon }) {
  return (
    <div className="bg-slate-50 rounded-lg p-2.5 text-center">
      <div className="flex items-center justify-center text-slate-500 mb-1">
        <Icon size={12} />
      </div>
      <div className="text-lg font-semibold text-slate-900">{value}</div>
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
    </div>
  );
}
