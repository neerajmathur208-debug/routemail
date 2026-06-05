import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Database,
  Download,
  Upload,
  ShieldAlert,
  Loader2,
  CheckCircle2,
  History,
  Users,
  Server,
  FileArchive,
} from "lucide-react";
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
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "../components/ui/dialog";
import { Checkbox } from "../components/ui/checkbox";
import Sidebar from "../components/Sidebar";
import { api, API } from "../App";
import { toast } from "sonner";
import axios from "axios";

function downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

function formatBytes(n) {
  if (!n) return "0 B";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(2)} MB`;
}

export default function SystemBackupRestore({ user, setUser }) {
  const navigate = useNavigate();
  const isAdmin = user?.role === "super_admin";

  const [busy, setBusy] = useState({});
  const [users, setUsers] = useState([]);
  const [selectedUsers, setSelectedUsers] = useState([]);
  const [history, setHistory] = useState([]);
  const [importDialog, setImportDialog] = useState(false);
  const [importFile, setImportFile] = useState(null);
  const [importPreview, setImportPreview] = useState(null);
  const [importResult, setImportResult] = useState(null);
  const [importConflict, setImportConflict] = useState("merge");

  const setBusyFor = (key, val) => setBusy((b) => ({ ...b, [key]: val }));

  const fetchUsers = useCallback(async () => {
    try {
      const res = await api.get("/admin/users", { params: { limit: 1000 } });
      setUsers(res.data?.users || res.data || []);
    } catch (err) {
      console.error(err);
    }
  }, []);

  const fetchHistory = useCallback(async () => {
    try {
      const res = await api.get("/admin/backup/history");
      setHistory(res.data?.items || []);
    } catch (err) {
      console.error(err);
    }
  }, []);

  useEffect(() => {
    if (!isAdmin) {
      navigate("/dashboard");
      return;
    }
    fetchUsers();
    fetchHistory();
  }, [isAdmin, navigate, fetchUsers, fetchHistory]);

  const exportFull = async () => {
    setBusyFor("export-full", true);
    try {
      const res = await axios.get(`${API}/admin/backup/export/full`, {
        withCredentials: true,
        responseType: "blob",
      });
      const fname = `routemail-platform-${new Date().toISOString().replace(/[:T]/g, "-").slice(0, 19)}.zip`;
      downloadBlob(res.data, fname);
      toast.success("Platform backup downloaded");
      fetchHistory();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to export platform");
    } finally {
      setBusyFor("export-full", false);
    }
  };

  const exportSelected = async () => {
    if (selectedUsers.length === 0) {
      toast.error("Select at least one user");
      return;
    }
    setBusyFor("export-users", true);
    try {
      const res = await axios.post(
        `${API}/admin/backup/export/users`,
        { user_ids: selectedUsers, include_credentials: true },
        { withCredentials: true, responseType: "blob" }
      );
      const fname = `routemail-users-${new Date().toISOString().replace(/[:T]/g, "-").slice(0, 19)}.zip`;
      downloadBlob(res.data, fname);
      toast.success(`Exported ${selectedUsers.length} user(s)`);
      setSelectedUsers([]);
      fetchHistory();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to export users");
    } finally {
      setBusyFor("export-users", false);
    }
  };

  const handleImportFile = async (file) => {
    setImportFile(file);
    setImportResult(null);
    if (!file) {
      setImportPreview(null);
      return;
    }
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await axios.post(`${API}/admin/backup/import/preview`, fd, {
        withCredentials: true,
      });
      setImportPreview(res.data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Invalid backup file");
      setImportPreview(null);
    }
  };

  const submitImport = async () => {
    if (!importFile) return;
    setBusyFor("import", true);
    try {
      const fd = new FormData();
      fd.append("file", importFile);
      const res = await axios.post(
        `${API}/admin/backup/import?conflict=${importConflict}`,
        fd,
        { withCredentials: true }
      );
      setImportResult(res.data);
      toast.success("Platform backup restored");
      fetchUsers();
      fetchHistory();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Restore failed");
    } finally {
      setBusyFor("import", false);
    }
  };

  if (!isAdmin) return null;

  return (
    <div className="min-h-screen bg-slate-50 flex">
      <Sidebar user={user} setUser={setUser} />
      <main className="flex-1 p-6 lg:p-10 max-w-[1400px]">
        <Button
          variant="ghost"
          onClick={() => navigate("/admin")}
          className="mb-4"
          data-testid="sys-backup-back-btn"
        >
          <ArrowLeft size={16} className="mr-2" /> Back to Admin
        </Button>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <div className="flex items-center gap-3 mb-2">
            <Server className="text-violet-600" size={28} strokeWidth={1.5} />
            <h1 className="text-3xl font-bold text-slate-900">
              System Backup & Restore
            </h1>
          </div>
          <p className="text-slate-600 max-w-3xl">
            Platform-wide backup & restore for disaster recovery. Sensitive credentials,
            session tokens and API secrets are NEVER exported — only Fernet-encrypted SMTP/IMAP
            password blobs are preserved.
          </p>
        </motion.div>

        {/* Export Full Platform */}
        <section
          className="bg-white border border-slate-200 rounded-2xl p-6 mb-6"
          data-testid="sys-backup-export-full-section"
        >
          <div className="flex items-start justify-between gap-6">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Database className="text-violet-600" size={20} />
                <h2 className="text-xl font-semibold text-slate-900">
                  Export Entire Platform
                </h2>
              </div>
              <p className="text-sm text-slate-500 max-w-2xl">
                Includes all users, campaigns, drip campaigns, email accounts, lists, Do Not
                Email lists (incl. domain suppressions), responses / leads, subscriptions,
                blogs, plans and system settings.
              </p>
            </div>
            <Button
              onClick={exportFull}
              disabled={busy["export-full"]}
              className="bg-violet-600 hover:bg-violet-700 text-white whitespace-nowrap"
              data-testid="sys-backup-export-full-btn"
            >
              {busy["export-full"] ? (
                <Loader2 size={16} className="mr-2 animate-spin" />
              ) : (
                <Download size={16} className="mr-2" />
              )}
              Export Entire Platform
            </Button>
          </div>
        </section>

        {/* Export Selected Users */}
        <section
          className="bg-white border border-slate-200 rounded-2xl p-6 mb-6"
          data-testid="sys-backup-export-users-section"
        >
          <div className="flex items-start justify-between gap-6 mb-4">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Users className="text-emerald-600" size={20} />
                <h2 className="text-xl font-semibold text-slate-900">
                  Export Selected Users
                </h2>
              </div>
              <p className="text-sm text-slate-500">
                Pick specific users to export. Their campaigns, lists, accounts, DNE lists and
                leads are bundled.
              </p>
            </div>
            <Button
              onClick={exportSelected}
              disabled={busy["export-users"] || selectedUsers.length === 0}
              className="bg-emerald-600 hover:bg-emerald-700 text-white whitespace-nowrap"
              data-testid="sys-backup-export-users-btn"
            >
              {busy["export-users"] ? (
                <Loader2 size={16} className="mr-2 animate-spin" />
              ) : (
                <Download size={16} className="mr-2" />
              )}
              Export {selectedUsers.length || ""} User(s)
            </Button>
          </div>

          <div
            className="border border-slate-200 rounded-lg max-h-80 overflow-y-auto"
            data-testid="sys-backup-user-list"
          >
            {users.length === 0 ? (
              <div className="p-6 text-center text-slate-500 text-sm">Loading users…</div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-slate-50 sticky top-0">
                  <tr className="text-left text-slate-500">
                    <th className="py-2 px-3 w-12">
                      <Checkbox
                        data-testid="sys-backup-user-select-all"
                        checked={selectedUsers.length === users.length && users.length > 0}
                        onCheckedChange={(v) =>
                          setSelectedUsers(v ? users.map((u) => u.user_id) : [])
                        }
                      />
                    </th>
                    <th className="py-2 px-3">Email</th>
                    <th className="py-2 px-3">Role</th>
                    <th className="py-2 px-3">Plan</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr
                      key={u.user_id}
                      className="border-t border-slate-100 hover:bg-slate-50"
                      data-testid={`sys-backup-user-row-${u.user_id}`}
                    >
                      <td className="py-2 px-3">
                        <Checkbox
                          checked={selectedUsers.includes(u.user_id)}
                          onCheckedChange={(v) => {
                            setSelectedUsers((prev) =>
                              v
                                ? [...new Set([...prev, u.user_id])]
                                : prev.filter((id) => id !== u.user_id)
                            );
                          }}
                          data-testid={`sys-backup-user-checkbox-${u.user_id}`}
                        />
                      </td>
                      <td className="py-2 px-3 font-mono text-xs text-slate-900">
                        {u.email}
                      </td>
                      <td className="py-2 px-3 text-xs">
                        <span
                          className={`px-2 py-0.5 rounded-full ${
                            u.role === "super_admin"
                              ? "bg-violet-100 text-violet-700"
                              : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {u.role || "user"}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-xs text-slate-500">
                        {u.plan_type || "free"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>

        {/* Import Platform Backup */}
        <section
          className="bg-white border border-amber-200 bg-amber-50/30 rounded-2xl p-6 mb-6"
          data-testid="sys-backup-import-section"
        >
          <div className="flex items-start justify-between gap-6">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Upload className="text-amber-600" size={20} />
                <h2 className="text-xl font-semibold text-slate-900">
                  Import Platform Backup
                </h2>
              </div>
              <p className="text-sm text-slate-600">
                Supports full platform or selected-users ZIPs. Choose how to resolve conflicts
                when restored users already exist.
              </p>
            </div>
            <Button
              onClick={() => {
                setImportFile(null);
                setImportPreview(null);
                setImportResult(null);
                setImportDialog(true);
              }}
              className="bg-amber-600 hover:bg-amber-700 text-white whitespace-nowrap"
              data-testid="sys-backup-open-import-btn"
            >
              <Upload size={16} className="mr-2" /> Import Platform Backup
            </Button>
          </div>
        </section>

        {/* Backup History */}
        <section
          className="bg-white border border-slate-200 rounded-2xl p-6"
          data-testid="sys-backup-history-section"
        >
          <div className="flex items-center gap-2 mb-4">
            <History className="text-slate-600" size={20} />
            <h2 className="text-xl font-semibold text-slate-900">Backup History</h2>
          </div>
          {history.length === 0 ? (
            <div className="text-center py-8 text-slate-500 text-sm">
              No platform backups have been recorded yet.
            </div>
          ) : (
            <div className="overflow-hidden border border-slate-200 rounded-lg">
              <table className="w-full text-sm">
                <thead className="bg-slate-50">
                  <tr className="text-left text-slate-500">
                    <th className="py-2 px-3">Date</th>
                    <th className="py-2 px-3">Type</th>
                    <th className="py-2 px-3">Size</th>
                    <th className="py-2 px-3">Users</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((h) => (
                    <tr
                      key={h.backup_id}
                      className="border-t border-slate-100"
                      data-testid={`sys-backup-history-row-${h.backup_id}`}
                    >
                      <td className="py-2 px-3 text-slate-700 text-xs">
                        {new Date(h.created_at).toLocaleString()}
                      </td>
                      <td className="py-2 px-3 text-xs">
                        <span
                          className={`px-2 py-0.5 rounded-full ${
                            h.backup_type === "platform_full"
                              ? "bg-violet-100 text-violet-700"
                              : "bg-emerald-100 text-emerald-700"
                          }`}
                        >
                          {h.backup_type === "platform_full"
                            ? "Full platform"
                            : "Selected users"}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-slate-700 text-xs font-mono">
                        {formatBytes(h.file_size)}
                      </td>
                      <td className="py-2 px-3 text-slate-700 text-xs">
                        {h.user_count}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {/* Import dialog */}
        <Dialog open={importDialog} onOpenChange={setImportDialog}>
          <DialogContent
            className="sm:max-w-[640px]"
            data-testid="sys-backup-import-dialog"
          >
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <FileArchive className="text-amber-600" /> Import Platform Backup
              </DialogTitle>
              <DialogDescription>
                Restore a previously exported platform or selected-users ZIP.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-4">
              <div className="flex items-start gap-3 bg-amber-50 border border-amber-200 rounded-lg p-3 text-xs text-amber-900">
                <ShieldAlert size={18} className="text-amber-600 shrink-0 mt-0.5" />
                <span>
                  Existing user passwords will NEVER be overwritten by this import. Newly
                  imported users that don't already exist will require a password reset.
                </span>
              </div>

              <div>
                <Label className="mb-1 block">Backup file (.zip)</Label>
                <Input
                  type="file"
                  accept=".zip"
                  data-testid="sys-backup-import-file"
                  onChange={(e) => handleImportFile(e.target.files?.[0] || null)}
                />
              </div>

              {importPreview && (
                <div
                  className="border border-slate-200 rounded-lg p-3 bg-slate-50 text-xs"
                  data-testid="sys-backup-import-preview"
                >
                  <div className="font-semibold text-slate-700 mb-1">Preview</div>
                  <div>Backup type: {importPreview.metadata?.backup_type}</div>
                  <div>Exported at: {importPreview.metadata?.exported_at}</div>
                  <div className="mt-1 grid grid-cols-2 gap-x-4">
                    {Object.entries(importPreview.summary || {}).map(([k, v]) => (
                      <div key={k}>
                        <span className="text-slate-500">{k}:</span>{" "}
                        <span className="font-mono">{v}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <Label className="mb-1 block">Conflict handling (existing users)</Label>
                <Select value={importConflict} onValueChange={setImportConflict}>
                  <SelectTrigger data-testid="sys-backup-conflict-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="skip">Skip Existing</SelectItem>
                    <SelectItem value="merge">Merge Existing (default)</SelectItem>
                    <SelectItem value="replace">Replace Existing</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-slate-500 mt-1">
                  Merge keeps existing data and adds the imported items as new records. Replace
                  wipes per-user data first. Skip leaves the user untouched.
                </p>
              </div>

              {importResult && (
                <div
                  className="border border-emerald-200 bg-emerald-50 rounded-lg p-3 text-xs text-emerald-800"
                  data-testid="sys-backup-import-result"
                >
                  <div className="flex items-center gap-2 mb-1 font-semibold">
                    <CheckCircle2 size={14} /> Restore complete
                  </div>
                  <div>
                    Users imported/merged/replaced/skipped:&nbsp;
                    {importResult.user_results?.length || 0}
                  </div>
                </div>
              )}
            </div>

            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setImportDialog(false)}
                data-testid="sys-backup-import-cancel"
              >
                Close
              </Button>
              <Button
                onClick={submitImport}
                disabled={!importFile || busy["import"]}
                className="bg-amber-600 hover:bg-amber-700 text-white"
                data-testid="sys-backup-import-confirm-btn"
              >
                {busy["import"] ? (
                  <Loader2 size={16} className="mr-2 animate-spin" />
                ) : (
                  <Upload size={16} className="mr-2" />
                )}
                Restore Platform
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
}
