import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Shield,
  Plus,
  Trash2,
  Upload,
  Search,
  Lock,
  FileText,
  Users,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "../components/ui/dialog";
import Sidebar from "../components/Sidebar";
import { api } from "../App";
import { toast } from "sonner";

export default function DoNotEmailDetail({ user, setUser }) {
  const { listId } = useParams();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  const [loading, setLoading] = useState(true);
  const [list, setList] = useState(null);
  const [search, setSearch] = useState("");
  const [skip, setSkip] = useState(0);
  const LIMIT = 100;

  const [addOpen, setAddOpen] = useState(false);
  const [bulkText, setBulkText] = useState("");
  const [adding, setAdding] = useState(false);
  const [uploading, setUploading] = useState(false);

  const fetchList = useCallback(async () => {
    try {
      const params = new URLSearchParams({ skip: String(skip), limit: String(LIMIT) });
      if (search.trim()) params.set("search", search.trim());
      const res = await api.get(`/dne-lists/${listId}?${params.toString()}`);
      setList(res.data);
    } catch (e) {
      console.error(e);
      toast.error("Failed to load list");
      navigate("/do-not-email");
    } finally {
      setLoading(false);
    }
  }, [listId, skip, search, navigate]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const handleAdd = async () => {
    const lines = bulkText
      .split(/[\s,;\n]+/)
      .map((x) => x.trim())
      .filter(Boolean);
    if (lines.length === 0) {
      toast.error("Enter at least one email");
      return;
    }
    setAdding(true);
    try {
      const res = await api.post(`/dne-lists/${listId}/emails`, { emails: lines });
      toast.success(
        `Added ${res.data.added}${
          res.data.invalid ? ` (${res.data.invalid} invalid skipped)` : ""
        }${res.data.skipped_duplicates ? `, ${res.data.skipped_duplicates} dupes` : ""}`
      );
      setBulkText("");
      setAddOpen(false);
      setSkip(0);
      fetchList();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to add");
    } finally {
      setAdding(false);
    }
  };

  const handleFileSelected = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    setUploading(true);
    try {
      const res = await api.post(`/dne-lists/${listId}/upload`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(
        `Imported ${res.data.added} emails${
          res.data.invalid ? ` (${res.data.invalid} invalid)` : ""
        }${res.data.skipped_duplicates ? `, ${res.data.skipped_duplicates} dupes` : ""}`
      );
      setSkip(0);
      fetchList();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleRemove = async (email) => {
    try {
      await api.delete(`/dne-lists/${listId}/emails`, { data: { email } });
      toast.success("Removed");
      fetchList();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Remove failed");
    }
  };

  if (loading || !list) {
    return (
      <div className="min-h-screen bg-slate-50 flex">
        <Sidebar user={user} setUser={setUser} />
        <main className="flex-1 flex items-center justify-center">
          <div className="animate-pulse text-slate-500">Loading…</div>
        </main>
      </div>
    );
  }

  const total = list.email_count || 0;
  const filtered = list.total_filtered || 0;
  const emails = list.emails || [];

  return (
    <div className="min-h-screen bg-slate-50 flex">
      <Sidebar user={user} setUser={setUser} />
      <main className="flex-1 p-6 lg:p-10 max-w-[1200px]">
        <Button
          variant="ghost"
          onClick={() => navigate("/do-not-email")}
          className="mb-4"
          data-testid="dne-back-btn"
        >
          <ArrowLeft size={16} className="mr-2" /> Back to Do Not Email
        </Button>

        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <Shield className="text-rose-600" size={26} strokeWidth={1.5} />
              <h1 className="text-3xl font-bold text-slate-900">{list.name}</h1>
              {list.is_global && (
                <span className="inline-flex items-center gap-1 text-xs bg-rose-100 text-rose-700 px-2 py-0.5 rounded-full">
                  <Lock size={12} /> Global · auto-applied
                </span>
              )}
            </div>
            <p className="text-sm text-slate-500 flex items-center gap-2">
              <Users size={14} /> {total} suppressed email{total === 1 ? "" : "s"} • created{" "}
              {new Date(list.created_at).toLocaleDateString()}
            </p>
          </div>
          <div className="flex gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={handleFileSelected}
              className="hidden"
              data-testid="dne-file-input"
            />
            <Button
              variant="outline"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              data-testid="dne-upload-btn"
            >
              <Upload size={16} className="mr-2" />
              {uploading ? "Uploading…" : "Upload CSV / Excel"}
            </Button>
            <Button
              onClick={() => setAddOpen(true)}
              className="bg-rose-600 hover:bg-rose-700 text-white"
              data-testid="dne-add-manual-btn"
            >
              <Plus size={16} className="mr-2" /> Add emails
            </Button>
          </div>
        </div>

        {/* Search */}
        <div className="bg-white border border-slate-200 rounded-2xl p-6">
          <div className="relative mb-4">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
            />
            <Input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value);
                setSkip(0);
              }}
              placeholder="Search emails…"
              className="pl-9"
              data-testid="dne-search-input"
            />
          </div>

          {emails.length === 0 ? (
            <div className="text-center py-12 text-slate-500">
              <FileText className="mx-auto mb-2 text-slate-400" size={40} strokeWidth={1.2} />
              {search ? "No matches found." : "This list is empty. Add emails to start suppressing."}
            </div>
          ) : (
            <>
              <div className="overflow-hidden border border-slate-200 rounded-lg">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50">
                    <tr className="text-left text-slate-500">
                      <th className="py-2 px-3">Email</th>
                      <th className="py-2 px-3">Source</th>
                      <th className="py-2 px-3">Added</th>
                      <th className="py-2 px-3 w-12"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {emails.map((e) => (
                      <tr
                        key={`${e.list_id}:${e.email}`}
                        className="border-t border-slate-100 hover:bg-slate-50"
                        data-testid={`dne-row-${e.email}`}
                      >
                        <td className="py-2 px-3 text-slate-900 font-mono text-xs">
                          {e.email}
                        </td>
                        <td className="py-2 px-3 text-slate-500 text-xs">
                          {e.source || "manual"}
                        </td>
                        <td className="py-2 px-3 text-slate-500 text-xs">
                          {e.added_at ? new Date(e.added_at).toLocaleString() : "—"}
                        </td>
                        <td className="py-2 px-3 text-right">
                          <button
                            onClick={() => handleRemove(e.email)}
                            className="text-slate-400 hover:text-red-600"
                            data-testid={`dne-remove-${e.email}`}
                            aria-label="Remove"
                          >
                            <Trash2 size={14} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {filtered > LIMIT && (
                <div className="flex items-center justify-between mt-4 text-sm text-slate-500">
                  <span>
                    Showing {skip + 1}–{Math.min(skip + emails.length, filtered)} of {filtered}
                  </span>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={skip === 0}
                      onClick={() => setSkip(Math.max(0, skip - LIMIT))}
                    >
                      Prev
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={skip + emails.length >= filtered}
                      onClick={() => setSkip(skip + LIMIT)}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Add emails dialog */}
        <Dialog open={addOpen} onOpenChange={setAddOpen}>
          <DialogContent data-testid="dne-add-dialog">
            <DialogHeader>
              <DialogTitle>Add emails to Do Not Email</DialogTitle>
              <DialogDescription>
                Paste one email per line, or comma-separated. Duplicates and invalid addresses
                are ignored automatically.
              </DialogDescription>
            </DialogHeader>
            <Textarea
              rows={8}
              placeholder={"someone@example.com\nanother@example.com"}
              value={bulkText}
              onChange={(e) => setBulkText(e.target.value)}
              data-testid="dne-bulk-textarea"
              className="font-mono text-sm"
            />
            <DialogFooter>
              <Button variant="outline" onClick={() => setAddOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleAdd}
                disabled={adding}
                className="bg-rose-600 hover:bg-rose-700 text-white"
                data-testid="dne-add-confirm-btn"
              >
                {adding ? "Adding…" : "Add to list"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
}
