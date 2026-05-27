import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Download,
  Upload,
  Database,
  ShieldAlert,
  FileJson,
  FileText,
  Loader2,
  CheckCircle2,
  Archive,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Label } from "../components/ui/label";
import { Input } from "../components/ui/input";
import { Switch } from "../components/ui/switch";
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
import Sidebar from "../components/Sidebar";
import { api, API } from "../App";
import { toast } from "sonner";
import axios from "axios";

const MODULES = [
  {
    key: "campaigns",
    label: "Campaigns",
    icon: FileJson,
    formats: ["json"],
    importHint: "Upload a campaigns JSON file exported from RouteMail.",
  },
  {
    key: "drip-campaigns",
    label: "Drip Campaigns",
    icon: FileJson,
    formats: ["json"],
    importHint: "Upload a drip-campaigns JSON file.",
  },
  {
    key: "email-accounts",
    label: "Email Accounts",
    icon: FileJson,
    formats: ["json"],
    importHint: "Restored accounts are inactive until re-verified.",
  },
  {
    key: "email-lists",
    label: "Email Lists",
    icon: FileText,
    formats: ["json", "csv"],
    importHint: "JSON preserves columns; CSV imports rows into a named list.",
  },
  {
    key: "dne-lists",
    label: "Unsubscribe Lists",
    icon: FileText,
    formats: ["json", "csv"],
    importHint: "Imports unsubscribe/DNE entries.",
  },
];

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

export default function BackupRestore({ user, setUser }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState({});
  const [includeCreds, setIncludeCreds] = useState(false);
  const [conflictMode, setConflictMode] = useState("copy");

  // Per-module import dialog state
  const [importDialog, setImportDialog] = useState({ open: false, module: null });
  const [importFile, setImportFile] = useState(null);
  const [importListName, setImportListName] = useState("");
  const [importFormat, setImportFormat] = useState("json");
  const [importResult, setImportResult] = useState(null);

  // Full backup restore dialog state
  const [fullRestoreOpen, setFullRestoreOpen] = useState(false);
  const [restoreFile, setRestoreFile] = useState(null);
  const [restorePreview, setRestorePreview] = useState(null);
  const [restoreResult, setRestoreResult] = useState(null);
  const [warningAck, setWarningAck] = useState(false);

  const setBusyFor = (key, val) => setBusy((b) => ({ ...b, [key]: val }));

  const exportModule = async (mod, format = "json") => {
    const key = `export-${mod.key}-${format}`;
    setBusyFor(key, true);
    try {
      const params = new URLSearchParams();
      if (format) params.append("format", format);
      if (mod.key === "email-accounts") params.append("include_credentials", includeCreds);
      const url = `${API}/backup/export/${mod.key}?${params}`;
      const res = await axios.get(url, {
        withCredentials: true,
        responseType: "blob",
      });
      const ext = format === "csv" ? "csv" : "json";
      const fname = `routemail-${mod.key}-${new Date().toISOString().slice(0, 10)}.${ext}`;
      downloadBlob(res.data, fname);
      toast.success(`${mod.label} exported`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || `Failed to export ${mod.label}`);
    } finally {
      setBusyFor(key, false);
    }
  };

  const exportFullBackup = async () => {
    setBusyFor("export-full", true);
    try {
      const params = new URLSearchParams();
      params.append("include_credentials", includeCreds);
      const res = await axios.get(`${API}/backup/export/full?${params}`, {
        withCredentials: true,
        responseType: "blob",
      });
      const fname = `routemail-backup-${new Date().toISOString().replace(/[:T]/g, "-").slice(0, 19)}.zip`;
      downloadBlob(res.data, fname);
      toast.success("Full backup downloaded");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to export full backup");
    } finally {
      setBusyFor("export-full", false);
    }
  };

  const openImport = (mod) => {
    setImportDialog({ open: true, module: mod });
    setImportFile(null);
    setImportListName("");
    setImportFormat(mod.formats[0]);
    setImportResult(null);
  };

  const submitModuleImport = async () => {
    if (!importFile) {
      toast.error("Select a file to import");
      return;
    }
    const mod = importDialog.module;
    if (!mod) return;
    setBusyFor("import-module", true);
    try {
      if (importFormat === "csv") {
        if (!importListName.trim()) {
          toast.error("Please provide a list name for CSV import");
          setBusyFor("import-module", false);
          return;
        }
        const fd = new FormData();
        fd.append("file", importFile);
        const url = `${API}/backup/import/${mod.key}/csv?list_name=${encodeURIComponent(importListName)}&conflict=${conflictMode}`;
        const res = await axios.post(url, fd, { withCredentials: true });
        setImportResult(res.data);
      } else {
        // JSON
        const text = await importFile.text();
        let parsed;
        try {
          parsed = JSON.parse(text);
        } catch (e) {
          toast.error("Invalid JSON file");
          setBusyFor("import-module", false);
          return;
        }
        const items = Array.isArray(parsed) ? parsed : parsed.items || [];
        const res = await api.post(`/backup/import/${mod.key}`, {
          items,
          conflict: conflictMode,
        });
        setImportResult(res.data);
      }
      toast.success(`${mod.label} imported`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Import failed");
    } finally {
      setBusyFor("import-module", false);
    }
  };

  const previewFullRestore = async (file) => {
    setBusyFor("preview", true);
    setRestorePreview(null);
    setRestoreResult(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const res = await axios.post(`${API}/backup/import/full/preview`, fd, {
        withCredentials: true,
      });
      setRestorePreview(res.data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not read backup file");
    } finally {
      setBusyFor("preview", false);
    }
  };

  const submitFullRestore = async () => {
    if (!restoreFile) return;
    if (!warningAck) {
      toast.error("Please acknowledge the safety notice");
      return;
    }
    setBusyFor("full-restore", true);
    try {
      const fd = new FormData();
      fd.append("file", restoreFile);
      const res = await axios.post(
        `${API}/backup/import/full?conflict=${conflictMode}`,
        fd,
        { withCredentials: true }
      );
      setRestoreResult(res.data);
      toast.success("Backup restored");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Restore failed");
    } finally {
      setBusyFor("full-restore", false);
    }
  };

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar user={user} setUser={setUser} />

      <main className="flex-1 p-6 lg:p-8 overflow-y-auto">
        <div className="max-w-5xl mx-auto">
          {/* Header */}
          <div className="flex items-center gap-4 mb-6">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate("/dashboard")}
              data-testid="backup-back-btn"
            >
              <ArrowLeft size={20} />
            </Button>
            <div className="flex-1">
              <h1 className="font-heading font-extrabold text-2xl sm:text-3xl text-slate-900">
                Backup &amp; Restore
              </h1>
              <p className="text-slate-500 mt-1 text-sm">
                Export your RouteMail data and restore from a backup at any time.
              </p>
            </div>
          </div>

          {/* Warning */}
          <div className="mb-6 bg-amber-50 border border-amber-200 rounded-md p-4 flex items-start gap-3">
            <ShieldAlert size={20} className="text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm">
              <p className="text-amber-800 font-semibold">Store backups securely</p>
              <p className="text-amber-700 mt-0.5">
                This backup may contain sensitive configuration data — including encrypted credentials if you opt in. Treat the file like a password.
              </p>
            </div>
          </div>

          {/* Global Options */}
          <div className="mb-6 bg-white border border-slate-200 rounded-md p-5 space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div className="flex items-center gap-3">
                <Switch
                  checked={includeCreds}
                  onCheckedChange={setIncludeCreds}
                  data-testid="include-credentials-toggle"
                />
                <div>
                  <Label className="text-sm font-medium">Include encrypted credentials</Label>
                  <p className="text-xs text-slate-500">Never exports plain-text passwords. Off by default.</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Label className="text-sm font-medium">On conflict during import</Label>
                <Select value={conflictMode} onValueChange={setConflictMode}>
                  <SelectTrigger className="w-44 h-9" data-testid="conflict-mode">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="copy">Import as new copy</SelectItem>
                    <SelectItem value="skip">Skip duplicates</SelectItem>
                    <SelectItem value="replace">Replace existing</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          {/* Full Backup Section */}
          <div className="mb-6 bg-white border border-slate-200 rounded-md p-5" data-testid="full-backup-card">
            <div className="flex items-center gap-3 mb-3">
              <Archive size={20} className="text-violet-600" />
              <h2 className="font-heading font-semibold text-lg text-slate-900">Full Account Backup</h2>
            </div>
            <p className="text-sm text-slate-600 mb-4">
              Download a single ZIP containing all your campaigns, drip campaigns, email accounts, email lists,
              unsubscribe lists, and metadata. Re-import anytime to restore.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={exportFullBackup}
                disabled={busy["export-full"]}
                className="bg-violet-600 hover:bg-violet-700 text-white"
                data-testid="export-full-backup"
              >
                {busy["export-full"] ? (
                  <Loader2 size={16} className="animate-spin mr-2" />
                ) : (
                  <Download size={16} className="mr-2" />
                )}
                Export Full Account Backup
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setFullRestoreOpen(true);
                  setRestoreFile(null);
                  setRestorePreview(null);
                  setRestoreResult(null);
                  setWarningAck(false);
                }}
                data-testid="open-full-restore"
              >
                <Upload size={16} className="mr-2" />
                Import Backup (ZIP)
              </Button>
            </div>
          </div>

          {/* Individual Modules */}
          <div className="bg-white border border-slate-200 rounded-md p-5">
            <div className="flex items-center gap-3 mb-4">
              <Database size={20} className="text-blue-600" />
              <h2 className="font-heading font-semibold text-lg text-slate-900">
                Export &amp; Import Individual Modules
              </h2>
            </div>
            <div className="grid sm:grid-cols-2 gap-3">
              {MODULES.map((mod) => {
                const Icon = mod.icon;
                return (
                  <div
                    key={mod.key}
                    className="border border-slate-200 rounded-md p-4 flex flex-col gap-3"
                    data-testid={`module-card-${mod.key}`}
                  >
                    <div className="flex items-center gap-2">
                      <Icon size={16} className="text-slate-500" />
                      <p className="font-medium text-slate-900">{mod.label}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {mod.formats.map((fmt) => (
                        <Button
                          key={fmt}
                          variant="outline"
                          size="sm"
                          onClick={() => exportModule(mod, fmt)}
                          disabled={busy[`export-${mod.key}-${fmt}`]}
                          data-testid={`export-${mod.key}-${fmt}`}
                        >
                          {busy[`export-${mod.key}-${fmt}`] ? (
                            <Loader2 size={14} className="animate-spin mr-1" />
                          ) : (
                            <Download size={14} className="mr-1" />
                          )}
                          Export {fmt.toUpperCase()}
                        </Button>
                      ))}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => openImport(mod)}
                        data-testid={`open-import-${mod.key}`}
                        className="text-blue-700"
                      >
                        <Upload size={14} className="mr-1" />
                        Import
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </main>

      {/* Module Import Dialog */}
      <Dialog open={importDialog.open} onOpenChange={(o) => setImportDialog({ open: o, module: importDialog.module })}>
        <DialogContent className="sm:max-w-lg" data-testid="module-import-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Upload size={18} className="text-blue-600" />
              Import {importDialog.module?.label}
            </DialogTitle>
            <DialogDescription>{importDialog.module?.importHint}</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            {importDialog.module && importDialog.module.formats.length > 1 && (
              <div>
                <Label className="text-xs text-slate-500">Format</Label>
                <Select value={importFormat} onValueChange={setImportFormat}>
                  <SelectTrigger data-testid="module-import-format">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {importDialog.module.formats.map((f) => (
                      <SelectItem key={f} value={f}>
                        {f.toUpperCase()}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            {importFormat === "csv" && (
              <div>
                <Label className="text-xs text-slate-500">List name</Label>
                <Input
                  value={importListName}
                  onChange={(e) => setImportListName(e.target.value)}
                  placeholder="e.g. Leads – April"
                  data-testid="csv-import-list-name"
                />
              </div>
            )}
            <div>
              <Label className="text-xs text-slate-500">File ({importFormat.toUpperCase()})</Label>
              <Input
                type="file"
                accept={importFormat === "csv" ? ".csv" : ".json,application/json"}
                onChange={(e) => setImportFile(e.target.files?.[0] || null)}
                data-testid="module-import-file"
              />
            </div>
            <div className="text-xs text-slate-500">
              On conflict: <span className="font-semibold capitalize">{conflictMode}</span>
              {" — change at the top of the page."}
            </div>
            {importResult && (
              <div className="bg-emerald-50 border border-emerald-200 rounded p-3 text-sm" data-testid="module-import-result">
                <p className="font-semibold text-emerald-800 mb-1 flex items-center gap-1">
                  <CheckCircle2 size={14} /> Import complete
                </p>
                <p className="text-emerald-700">
                  imported: {importResult.imported ?? 0} · skipped: {importResult.skipped ?? 0} · replaced: {importResult.replaced ?? 0}
                </p>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setImportDialog({ open: false, module: null })} disabled={busy["import-module"]}>
              Close
            </Button>
            <Button
              onClick={submitModuleImport}
              disabled={busy["import-module"] || !importFile}
              className="bg-blue-600 hover:bg-blue-700 text-white"
              data-testid="module-import-submit"
            >
              {busy["import-module"] ? <Loader2 size={14} className="animate-spin mr-2" /> : null}
              Import
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Full Restore Dialog */}
      <Dialog open={fullRestoreOpen} onOpenChange={setFullRestoreOpen}>
        <DialogContent className="sm:max-w-lg" data-testid="full-restore-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Archive size={18} className="text-violet-600" />
              Restore Full Account Backup
            </DialogTitle>
            <DialogDescription>
              Upload a RouteMail backup ZIP. Restored campaigns &amp; drips become drafts; restored accounts stay inactive until verified.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div>
              <Label className="text-xs text-slate-500">Backup file (.zip)</Label>
              <Input
                type="file"
                accept=".zip,application/zip"
                onChange={(e) => {
                  const f = e.target.files?.[0] || null;
                  setRestoreFile(f);
                  if (f) previewFullRestore(f);
                }}
                data-testid="full-restore-file"
              />
            </div>
            {busy["preview"] && (
              <p className="text-sm text-slate-500 flex items-center gap-1">
                <Loader2 size={14} className="animate-spin" /> Reading backup…
              </p>
            )}
            {restorePreview && (
              <div className="bg-slate-50 border border-slate-200 rounded p-3 text-sm" data-testid="restore-preview">
                <p className="font-semibold text-slate-800 mb-2">Will be imported:</p>
                <ul className="grid grid-cols-2 gap-y-1 text-slate-700">
                  <li><span className="font-semibold">{restorePreview.summary.campaigns}</span> Campaigns</li>
                  <li><span className="font-semibold">{restorePreview.summary.drip_campaigns}</span> Drip Campaigns</li>
                  <li><span className="font-semibold">{restorePreview.summary.email_accounts}</span> Email Accounts</li>
                  <li><span className="font-semibold">{restorePreview.summary.email_lists}</span> Email Lists</li>
                  <li><span className="font-semibold">{restorePreview.summary.unsubscribe_lists}</span> Unsubscribe Lists</li>
                </ul>
                <p className="text-xs text-slate-500 mt-2">
                  Exported {restorePreview.metadata.exported_at?.slice(0, 19).replace("T", " ")} by{" "}
                  {restorePreview.metadata.user_email}
                </p>
              </div>
            )}
            {restorePreview && (
              <label className="flex items-start gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={warningAck}
                  onChange={(e) => setWarningAck(e.target.checked)}
                  className="mt-1"
                  data-testid="restore-ack"
                />
                <span>
                  I understand restored campaigns &amp; drips will be drafts, and restored email accounts will be inactive until I re-verify them. Conflict mode:{" "}
                  <span className="font-semibold capitalize">{conflictMode}</span>.
                </span>
              </label>
            )}
            {restoreResult && (
              <div className="bg-emerald-50 border border-emerald-200 rounded p-3 text-sm" data-testid="restore-result">
                <p className="font-semibold text-emerald-800 mb-1 flex items-center gap-1">
                  <CheckCircle2 size={14} /> Restore complete
                </p>
                <ul className="text-emerald-700 grid grid-cols-2 gap-y-0.5">
                  {Object.entries(restoreResult.results).map(([k, v]) => (
                    <li key={k}>
                      {k}: imported {v.imported}, skipped {v.skipped}, replaced {v.replaced}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFullRestoreOpen(false)} disabled={busy["full-restore"]}>
              Close
            </Button>
            <Button
              onClick={submitFullRestore}
              disabled={busy["full-restore"] || !restoreFile || !restorePreview || !warningAck}
              className="bg-violet-600 hover:bg-violet-700 text-white"
              data-testid="confirm-full-restore"
            >
              {busy["full-restore"] ? <Loader2 size={14} className="animate-spin mr-2" /> : null}
              Restore Backup
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
