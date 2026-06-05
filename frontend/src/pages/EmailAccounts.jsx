import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Mail,
  Plus,
  Trash2,
  CheckCircle2,
  XCircle,
  Info,
  Server,
  Lock,
  Eye,
  EyeOff,
  Loader2,
  ArrowLeft,
  Save,
  Flame,
  Play,
  Pause,
  Settings,
  TrendingUp,
  BarChart3,
  Upload,
  Download,
  Edit3,
  FileText,
  CheckSquare,
  Square,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { Checkbox } from "../components/ui/checkbox";
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
import { Progress } from "../components/ui/progress";
import Sidebar from "../components/Sidebar";
import { api, API } from "../App";
import { toast } from "sonner";

const SMTP_PRESETS = {
  gmail: { host: "smtp.gmail.com", port: 587, encryption: "tls", note: "Use App Password (not your regular password). Enable 2FA first." },
  outlook: { host: "smtp.office365.com", port: 587, encryption: "tls", note: "Use your Microsoft account password or app password." },
  yahoo: { host: "smtp.mail.yahoo.com", port: 587, encryption: "tls", note: "Generate an app password from Yahoo account security." },
  custom: { host: "", port: 587, encryption: "tls", note: "Enter your custom SMTP server details." }
};

export default function EmailAccounts({ user, setUser }) {
  const navigate = useNavigate();
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState(null);
  const [showPassword, setShowPassword] = useState(false);
  const [testing, setTesting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [editingLimit, setEditingLimit] = useState({});
  const [editingDelay, setEditingDelay] = useState({});
  const [savingLimit, setSavingLimit] = useState({});
  const [savingDelay, setSavingDelay] = useState({});
  
  // Warmup states
  const [warmupModalOpen, setWarmupModalOpen] = useState(false);
  const [warmupAccount, setWarmupAccount] = useState(null);
  const [warmupLoading, setWarmupLoading] = useState({});
  const [warmupSettings, setWarmupSettings] = useState({
    starting_emails_per_day: 5,
    max_emails_per_day: 50,
    daily_increment: 5,
    reply_rate: 40
  });
  const [warmupStatsModal, setWarmupStatsModal] = useState(false);
  const [warmupStats, setWarmupStats] = useState(null);

  // Bulk selection + bulk warmup state
  const [selectedIds, setSelectedIds] = useState([]);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkSettingsOpen, setBulkSettingsOpen] = useState(false);
  const [bulkSettings, setBulkSettings] = useState({
    starting_emails_per_day: 5,
    max_emails_per_day: 50,
    daily_increment: 5,
    reply_rate: 40,
  });
  const [bulkSettingsMode, setBulkSettingsMode] = useState("start"); // "start" | "update"

  const [formData, setFormData] = useState({
    preset: "custom",
    email: "",
    display_name: "",
    from_name: "",
    smtp_host: "",
    smtp_port: 587,
    smtp_username: "",
    smtp_password: "",
    smtp_encryption: "tls",
    imap_host: "",
    imap_port: 993,
    imap_username: "",
    imap_password: "",
    imap_encryption: "ssl",
    daily_limit: 50,
    send_delay: 30,
  });

  // View / Edit account state
  const [viewAccount, setViewAccount] = useState(null);
  const [editingAccount, setEditingAccount] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [savingEdit, setSavingEdit] = useState(false);
  const [showEditPassword, setShowEditPassword] = useState(false);

  // Bulk import state
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [importFile, setImportFile] = useState(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);

  const fetchAccounts = async () => {
    try {
      const response = await api.get("/accounts");
      // Handle accounts response - API returns { accounts: [], limit_info: {} }
      const accountsData = response.data?.accounts || response.data || [];
      const accounts = Array.isArray(accountsData) ? accountsData : [];
      setAccounts(accounts);
      // Initialize editing limits and delays
      const limits = {};
      const delays = {};
      accounts.forEach(acc => {
        limits[acc.account_id] = acc.daily_limit || 50;
        delays[acc.account_id] = acc.send_delay || 30;
      });
      setEditingLimit(limits);
      setEditingDelay(delays);
    } catch (error) {
      console.error("Failed to fetch accounts:", error);
      toast.error("Failed to load accounts");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAccounts();
  }, []);

  const handlePresetChange = (preset) => {
    const presetData = SMTP_PRESETS[preset];
    setFormData({
      ...formData,
      preset,
      smtp_host: presetData.host,
      smtp_port: presetData.port,
      smtp_encryption: presetData.encryption,
    });
  };

  const handleTestConnection = async () => {
    if (!formData.smtp_host || !formData.smtp_username || !formData.smtp_password) {
      toast.error("Please fill in all SMTP fields");
      return;
    }

    setTesting(true);
    try {
      const response = await api.post("/accounts/test-smtp", {
        smtp_host: formData.smtp_host,
        smtp_port: formData.smtp_port,
        smtp_username: formData.smtp_username,
        smtp_password: formData.smtp_password,
        smtp_encryption: formData.smtp_encryption,
      });

      if (response.data.success) {
        toast.success("Connection successful!");
      } else {
        toast.error(response.data.error || "Connection failed");
      }
    } catch (error) {
      const message = error.response?.data?.detail || "Connection test failed";
      toast.error(message);
    } finally {
      setTesting(false);
    }
  };

  const handleAddAccount = async () => {
    if (!formData.email || !formData.display_name) {
      toast.error("Please fill in email and display name");
      return;
    }

    if (!formData.smtp_host || !formData.smtp_username || !formData.smtp_password) {
      toast.error("Please fill in all SMTP fields");
      return;
    }

    setSubmitting(true);
    try {
      await api.post("/accounts/smtp", {
        email: formData.email,
        display_name: formData.display_name,
        from_name: formData.from_name || formData.display_name,
        smtp_host: formData.smtp_host,
        smtp_port: formData.smtp_port,
        smtp_username: formData.smtp_username,
        smtp_password: formData.smtp_password,
        smtp_encryption: formData.smtp_encryption,
        imap_host: formData.imap_host || null,
        imap_port: formData.imap_host ? formData.imap_port : null,
        imap_username: formData.imap_host ? (formData.imap_username || formData.email) : null,
        imap_password: formData.imap_host ? (formData.imap_password || formData.smtp_password) : null,
        imap_encryption: formData.imap_host ? formData.imap_encryption : null,
        daily_limit: formData.daily_limit,
        send_delay: formData.send_delay,
      });
      toast.success("Email account added successfully");
      setAddDialogOpen(false);
      resetForm();
      fetchAccounts();
    } catch (error) {
      const message = error.response?.data?.detail || "Failed to add account";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdateLimit = async (accountId) => {
    const newLimit = parseInt(editingLimit[accountId]);
    if (!Number.isFinite(newLimit) || newLimit < 1) {
      toast.error("Daily limit must be at least 1");
      return;
    }

    setSavingLimit({ ...savingLimit, [accountId]: true });
    try {
      await api.put(`/accounts/${accountId}/limit`, { daily_limit: newLimit });
      toast.success("Daily limit updated");
      fetchAccounts();
    } catch (error) {
      toast.error("Failed to update limit");
    } finally {
      setSavingLimit({ ...savingLimit, [accountId]: false });
    }
  };

  const handleUpdateDelay = async (accountId) => {
    const newDelay = editingDelay[accountId];
    if (newDelay < 10 || newDelay > 300) {
      toast.error("Send delay must be between 10 and 300 seconds");
      return;
    }

    setSavingDelay({ ...savingDelay, [accountId]: true });
    try {
      await api.put(`/accounts/${accountId}/delay`, { send_delay: newDelay });
      toast.success("Send delay updated");
      fetchAccounts();
    } catch (error) {
      toast.error("Failed to update delay");
    } finally {
      setSavingDelay({ ...savingDelay, [accountId]: false });
    }
  };

  const handleDeleteAccount = async () => {
    if (!selectedAccount) return;

    try {
      await api.delete(`/accounts/${selectedAccount.account_id}`);
      toast.success("Account removed successfully");
      setDeleteDialogOpen(false);
      setSelectedAccount(null);
      fetchAccounts();
    } catch (error) {
      toast.error("Failed to remove account");
    }
  };

  // View / Edit
  const handleOpenView = (account) => {
    setViewAccount(account);
  };

  const handleOpenEdit = async (account) => {
    setEditingAccount(account);
    setEditForm({
      email: account.email || "",
      display_name: account.display_name || "",
      smtp_host: account.smtp_host || "",
      smtp_port: account.smtp_port || 587,
      smtp_username: account.smtp_username || account.email || "",
      smtp_encryption: account.smtp_encryption || "tls",
      daily_limit: account.daily_limit || 50,
      send_delay: account.send_delay || 30,
      smtp_password: "", // populated below from secure endpoint
    });
    setShowEditPassword(false);
    // Fetch current credential so the owner can review/edit it
    try {
      const r = await api.get(`/accounts/${account.account_id}/credential`);
      setEditForm((prev) => ({ ...prev, smtp_password: r.data?.smtp_password || "" }));
    } catch (e) {
      // Non-fatal — user can still rotate the password
      console.warn("Could not load saved password", e);
    }
  };

  const handleSaveEdit = async () => {
    if (!editingAccount) return;
    if (!editForm.email || !editForm.smtp_host || !editForm.smtp_port) {
      toast.error("Email, SMTP host and port are required");
      return;
    }
    setSavingEdit(true);
    try {
      const payload = { ...editForm };
      if (!payload.smtp_password) delete payload.smtp_password; // only send if user entered one
      await api.put(`/accounts/${editingAccount.account_id}`, payload);
      toast.success("Account updated");
      setEditingAccount(null);
      fetchAccounts();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to update account");
    } finally {
      setSavingEdit(false);
    }
  };

  // Bulk import
  const handleDownloadSample = () => {
    window.open(`${API}/accounts/smtp/sample-csv`, "_blank");
  };

  const handleImportSubmit = async () => {
    if (!importFile) {
      toast.error("Please choose a CSV file first");
      return;
    }
    setImporting(true);
    setImportResult(null);
    try {
      const form = new FormData();
      form.append("file", importFile);
      const res = await api.post("/accounts/smtp/bulk-import", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setImportResult(res.data);
      toast.success(
        `Imported ${res.data.imported}${res.data.skipped ? `, ${res.data.skipped} skipped` : ""}${res.data.failed ? `, ${res.data.failed} failed` : ""}`
      );
      fetchAccounts();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Import failed");
    } finally {
      setImporting(false);
    }
  };

  // Warmup Functions
  const handleEnableWarmup = async (account) => {
    setWarmupLoading(prev => ({ ...prev, [account.account_id]: true }));
    try {
      await api.post(`/accounts/${account.account_id}/warmup/enable`, warmupSettings);
      toast.success("Warmup enabled successfully");
      fetchAccounts();
      setWarmupModalOpen(false);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to enable warmup");
    } finally {
      setWarmupLoading(prev => ({ ...prev, [account.account_id]: false }));
    }
  };

  const handleDisableWarmup = async (accountId) => {
    setWarmupLoading(prev => ({ ...prev, [accountId]: true }));
    try {
      await api.post(`/accounts/${accountId}/warmup/disable`);
      toast.success("Warmup disabled");
      fetchAccounts();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to disable warmup");
    } finally {
      setWarmupLoading(prev => ({ ...prev, [accountId]: false }));
    }
  };

  const handlePauseWarmup = async (accountId) => {
    setWarmupLoading(prev => ({ ...prev, [accountId]: true }));
    try {
      await api.post(`/accounts/${accountId}/warmup/pause`);
      toast.success("Warmup paused");
      fetchAccounts();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to pause warmup");
    } finally {
      setWarmupLoading(prev => ({ ...prev, [accountId]: false }));
    }
  };

  const handleResumeWarmup = async (accountId) => {
    setWarmupLoading(prev => ({ ...prev, [accountId]: true }));
    try {
      await api.post(`/accounts/${accountId}/warmup/resume`);
      toast.success("Warmup resumed");
      fetchAccounts();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to resume warmup");
    } finally {
      setWarmupLoading(prev => ({ ...prev, [accountId]: false }));
    }
  };

  const openWarmupSettings = (account) => {
    setWarmupAccount(account);
    setWarmupSettings(account.warmup_settings || {
      starting_emails_per_day: 5,
      max_emails_per_day: 50,
      daily_increment: 5,
      reply_rate: 40
    });
    setWarmupModalOpen(true);
  };

  const fetchWarmupStats = async (accountId) => {
    try {
      const response = await api.get(`/accounts/${accountId}/warmup/stats`);
      setWarmupStats(response.data);
      setWarmupStatsModal(true);
    } catch (error) {
      toast.error("Failed to load warmup stats");
    }
  };

  // ===== Bulk warmup handlers =====
  const toggleSelect = (accountId) => {
    setSelectedIds((prev) =>
      prev.includes(accountId) ? prev.filter((x) => x !== accountId) : [...prev, accountId]
    );
  };

  const toggleSelectAll = () => {
    if (selectedIds.length === accounts.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(accounts.map((a) => a.account_id));
    }
  };

  const clearSelection = () => setSelectedIds([]);

  const openBulkStart = () => {
    // Pre-fill from first selected account that already has settings, else defaults
    const first = accounts.find((a) => selectedIds.includes(a.account_id) && a.warmup_settings);
    setBulkSettings(
      first?.warmup_settings || {
        starting_emails_per_day: 5,
        max_emails_per_day: 50,
        daily_increment: 5,
        reply_rate: 40,
      }
    );
    setBulkSettingsMode("start");
    setBulkSettingsOpen(true);
  };

  const openBulkUpdateSettings = () => {
    const first = accounts.find((a) => selectedIds.includes(a.account_id) && a.warmup_settings);
    setBulkSettings(
      first?.warmup_settings || {
        starting_emails_per_day: 5,
        max_emails_per_day: 50,
        daily_increment: 5,
        reply_rate: 40,
      }
    );
    setBulkSettingsMode("update");
    setBulkSettingsOpen(true);
  };

  const submitBulkSettings = async () => {
    if (selectedIds.length === 0) return;
    setBulkBusy(true);
    try {
      const url =
        bulkSettingsMode === "start"
          ? "/accounts/warmup/bulk-enable"
          : "/accounts/warmup/bulk-settings";
      const method = bulkSettingsMode === "start" ? "post" : "put";
      const res = await api[method](url, {
        account_ids: selectedIds,
        ...bulkSettings,
      });
      toast.success(
        bulkSettingsMode === "start"
          ? `Started warmup on ${res.data.modified} account${res.data.modified === 1 ? "" : "s"}`
          : `Updated settings on ${res.data.modified} account${res.data.modified === 1 ? "" : "s"}`
      );
      setBulkSettingsOpen(false);
      await fetchAccounts();
      if (bulkSettingsMode === "start") clearSelection();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Bulk action failed");
    } finally {
      setBulkBusy(false);
    }
  };

  const handleBulkPause = async () => {
    if (selectedIds.length === 0) return;
    setBulkBusy(true);
    try {
      const res = await api.post("/accounts/warmup/bulk-pause", { account_ids: selectedIds });
      toast.success(`Paused warmup on ${res.data.modified} account${res.data.modified === 1 ? "" : "s"}`);
      await fetchAccounts();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to pause warmup");
    } finally {
      setBulkBusy(false);
    }
  };

  const handleBulkResume = async () => {
    if (selectedIds.length === 0) return;
    setBulkBusy(true);
    try {
      const res = await api.post("/accounts/warmup/bulk-resume", { account_ids: selectedIds });
      toast.success(`Resumed warmup on ${res.data.modified} account${res.data.modified === 1 ? "" : "s"}`);
      await fetchAccounts();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to resume warmup");
    } finally {
      setBulkBusy(false);
    }
  };

  const handleBulkDisable = async () => {
    if (selectedIds.length === 0) return;
    setBulkBusy(true);
    try {
      const res = await api.post("/accounts/warmup/bulk-disable", { account_ids: selectedIds });
      toast.success(`Disabled warmup on ${res.data.modified} account${res.data.modified === 1 ? "" : "s"}`);
      await fetchAccounts();
      clearSelection();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to disable warmup");
    } finally {
      setBulkBusy(false);
    }
  };

  // Bulk delete state + handlers
  const [bulkDeleteOpen, setBulkDeleteOpen] = useState(false);
  const [bulkDeleteBlocked, setBulkDeleteBlocked] = useState(null);
  const [bulkDeleteBusy, setBulkDeleteBusy] = useState(false);

  const handleBulkDeleteRequest = () => {
    if (selectedIds.length === 0) return;
    setBulkDeleteBlocked(null);
    setBulkDeleteOpen(true);
  };

  const submitBulkDelete = async (force = false) => {
    if (selectedIds.length === 0) return;
    setBulkDeleteBusy(true);
    try {
      const res = await api.post("/accounts/bulk-delete", {
        account_ids: selectedIds,
        force,
      });
      if (res.data.requires_force) {
        // Block path — show details to user, let them confirm-force
        setBulkDeleteBlocked(res.data);
      } else {
        toast.success(`Deleted ${res.data.deleted} account${res.data.deleted === 1 ? "" : "s"}`);
        setBulkDeleteOpen(false);
        setBulkDeleteBlocked(null);
        clearSelection();
        await fetchAccounts();
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to delete accounts");
    } finally {
      setBulkDeleteBusy(false);
    }
  };

  // Aggregated stats for selected accounts
  const selectedAccounts = accounts.filter((a) => selectedIds.includes(a.account_id));
  const selectedActiveCount = selectedAccounts.filter(
    (a) => a.warmup_enabled && a.warmup_status === "active"
  ).length;
  const selectedSentToday = selectedAccounts.reduce(
    (sum, a) => sum + (a.warmup_emails_sent_today || 0),
    0
  );

  const resetForm = () => {
    setFormData({
      preset: "custom",
      email: "",
      display_name: "",
      smtp_host: "",
      smtp_port: 587,
      smtp_username: "",
      smtp_password: "",
      smtp_encryption: "tls",
      daily_limit: 50,
      send_delay: 30,
    });
    setShowPassword(false);
  };

  if (loading) {
    return (
      <div className="flex min-h-screen bg-slate-50">
        <Sidebar user={user} setUser={setUser} />
        <main className="flex-1 p-8">
          <div className="animate-pulse">Loading...</div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar user={user} setUser={setUser} />

      <main className="flex-1 p-6 lg:p-8 overflow-y-auto">
        <div className="max-w-4xl mx-auto">
          {/* Header with Back Button */}
          <div className="flex items-center gap-4 mb-8">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate("/dashboard")}
              data-testid="back-btn"
            >
              <ArrowLeft size={20} />
            </Button>
            <div className="flex-1">
              <h1 className="font-heading font-extrabold text-2xl sm:text-3xl text-slate-900">
                Email Accounts
              </h1>
              <p className="text-slate-500 mt-1">
                Connect your SMTP email accounts for sending
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                onClick={handleDownloadSample}
                data-testid="download-sample-csv-btn"
              >
                <Download size={16} className="mr-2" />
                Sample CSV
              </Button>
              <Button
                variant="outline"
                onClick={() => { setImportDialogOpen(true); setImportFile(null); setImportResult(null); }}
                data-testid="import-accounts-btn"
              >
                <Upload size={16} className="mr-2" />
                Import CSV
              </Button>
              <Button
                onClick={() => { resetForm(); setAddDialogOpen(true); }}
                className="bg-electric-blue hover:bg-blue-700"
                data-testid="add-account-btn"
              >
                <Plus size={18} className="mr-2" />
                Add Account
              </Button>
            </div>
          </div>

          {/* Info Box */}
          <div className="mb-6 bg-blue-50 border border-blue-200 rounded-md p-4 flex items-start gap-3">
            <Info size={20} className="text-blue-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-blue-800 font-medium">SMTP Connection</p>
              <p className="text-blue-700 text-sm mt-1">
                Connect via SMTP. For Gmail, use an App Password. Set custom daily limits (10-200) for each account.
              </p>
            </div>
          </div>

          {/* Accounts List — independent scroll */}
          {/* Bulk Actions Toolbar */}
          {accounts.length > 0 && (
            <div className="mb-4 flex flex-wrap items-center gap-3 bg-white border border-slate-200 rounded-md p-3" data-testid="bulk-toolbar">
              <Button
                variant="ghost"
                size="sm"
                onClick={toggleSelectAll}
                className="text-slate-600"
                data-testid="select-all-btn"
              >
                {selectedIds.length === accounts.length && accounts.length > 0 ? (
                  <CheckSquare size={16} className="mr-2 text-blue-600" />
                ) : (
                  <Square size={16} className="mr-2" />
                )}
                {selectedIds.length === accounts.length && accounts.length > 0 ? "Deselect all" : "Select all"}
              </Button>
              <span className="text-sm text-slate-500" data-testid="selected-count">
                {selectedIds.length} of {accounts.length} selected
              </span>
              {selectedIds.length > 0 && (
                <>
                  <span className="hidden sm:inline-block text-slate-300">•</span>
                  <span className="text-xs text-slate-600" data-testid="combined-stats">
                    <span className="font-semibold text-emerald-600">{selectedActiveCount}</span> active
                    <span className="mx-1.5 text-slate-300">|</span>
                    <span className="font-semibold text-blue-600">{selectedSentToday}</span> warmup emails sent today
                  </span>
                  <div className="flex flex-wrap items-center gap-2 ml-auto">
                    <Button
                      size="sm"
                      onClick={openBulkStart}
                      disabled={bulkBusy}
                      className="bg-emerald-600 hover:bg-emerald-700 text-white"
                      data-testid="bulk-start-warmup"
                    >
                      <Play size={14} className="mr-1" />
                      Start Warmup
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={handleBulkPause}
                      disabled={bulkBusy}
                      className="text-amber-700 border-amber-200 hover:bg-amber-50"
                      data-testid="bulk-pause-warmup"
                    >
                      <Pause size={14} className="mr-1" />
                      Pause
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={handleBulkResume}
                      disabled={bulkBusy}
                      className="text-emerald-700 border-emerald-200 hover:bg-emerald-50"
                      data-testid="bulk-resume-warmup"
                    >
                      <Play size={14} className="mr-1" />
                      Resume
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={openBulkUpdateSettings}
                      disabled={bulkBusy}
                      data-testid="bulk-update-settings"
                    >
                      <Settings size={14} className="mr-1" />
                      Update Settings
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={handleBulkDisable}
                      disabled={bulkBusy}
                      className="text-red-600 hover:bg-red-50"
                      data-testid="bulk-disable-warmup"
                    >
                      Disable Warmup
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={handleBulkDeleteRequest}
                      disabled={bulkBusy || bulkDeleteBusy}
                      className="text-red-700 hover:bg-red-50 border border-red-200"
                      data-testid="bulk-delete-accounts"
                    >
                      <Trash2 size={14} className="mr-1" />
                      Delete Selected
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={clearSelection}
                      disabled={bulkBusy}
                      className="text-slate-500"
                      data-testid="bulk-clear-selection"
                    >
                      Clear
                    </Button>
                  </div>
                </>
              )}
            </div>
          )}

          {/* Accounts List — independent scroll */}
          {accounts.length > 0 ? (
            <div
              className="email-accounts-list-container space-y-4 pr-2"
              style={{ maxHeight: "calc(100vh - 320px)", overflowY: "auto" }}
              data-testid="email-accounts-list"
            >
              {accounts.map((account, index) => (
                <motion.div
                  key={account.account_id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(index, 6) * 0.05 }}
                  className={`bg-white border rounded-md p-6 transition-colors ${
                    selectedIds.includes(account.account_id)
                      ? "border-blue-300 ring-1 ring-blue-200"
                      : "border-slate-200"
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-4">
                      <Checkbox
                        checked={selectedIds.includes(account.account_id)}
                        onCheckedChange={() => toggleSelect(account.account_id)}
                        data-testid={`select-account-${account.account_id}`}
                        aria-label={`Select ${account.email}`}
                      />
                      <div className="w-12 h-12 bg-slate-100 rounded-full flex items-center justify-center">
                        <Mail size={24} className="text-slate-500" />
                      </div>
                      <div>
                        <p className="font-semibold text-slate-900">{account.display_name}</p>
                        <p className="font-mono text-sm text-slate-500">{account.email}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <Server size={12} className="text-slate-400" />
                          <span className="text-xs text-slate-400">
                            {account.account_type?.toUpperCase() || "SMTP"}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <div className="flex items-center gap-2 mr-2">
                        {account.status === "connected" ? (
                          <>
                            <CheckCircle2 size={16} className="text-green-600" />
                            <span className="text-sm text-green-600 font-medium">Connected</span>
                          </>
                        ) : (
                          <>
                            <XCircle size={16} className="text-red-500" />
                            <span className="text-sm text-red-500 font-medium">Error</span>
                          </>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleOpenView(account)}
                        data-testid={`view-account-${account.account_id}`}
                        title="View details"
                      >
                        <Eye size={18} className="text-slate-400 hover:text-blue-600" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleOpenEdit(account)}
                        data-testid={`edit-account-${account.account_id}`}
                        title="Edit server settings"
                      >
                        <Edit3 size={18} className="text-slate-400 hover:text-violet-600" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-slate-400 hover:text-red-500"
                        onClick={() => { setSelectedAccount(account); setDeleteDialogOpen(true); }}
                        data-testid={`delete-account-${account.account_id}`}
                      >
                        <Trash2 size={18} />
                      </Button>
                    </div>
                  </div>

                  {account.last_error && (
                    <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                      {account.last_error}
                    </div>
                  )}

                  <div className="mt-4 pt-4 border-t border-slate-100">
                    <div className="flex flex-wrap items-center gap-4">
                      {/* Daily Limit Editor */}
                      <div className="flex items-center gap-2">
                        <Label className="text-xs text-slate-500 whitespace-nowrap">Daily Limit:</Label>
                        <Input
                          type="number"
                          min="1"
                          value={editingLimit[account.account_id] || 50}
                          onChange={(e) => setEditingLimit({
                            ...editingLimit,
                            [account.account_id]: Math.max(1, parseInt(e.target.value) || 50)
                          })}
                          className="w-24 h-8 text-sm"
                          data-testid={`limit-input-${account.account_id}`}
                        />
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleUpdateLimit(account.account_id)}
                          disabled={savingLimit[account.account_id]}
                          className="h-8"
                          data-testid={`save-limit-${account.account_id}`}
                        >
                          {savingLimit[account.account_id] ? (
                            <Loader2 size={14} className="animate-spin" />
                          ) : (
                            <Save size={14} />
                          )}
                        </Button>
                      </div>

                      {/* Send Delay Editor */}
                      <div className="flex items-center gap-2">
                        <Label className="text-xs text-slate-500 whitespace-nowrap">Send Delay:</Label>
                        <Input
                          type="number"
                          min="10"
                          max="300"
                          value={editingDelay[account.account_id] || 30}
                          onChange={(e) => setEditingDelay({
                            ...editingDelay,
                            [account.account_id]: parseInt(e.target.value) || 30
                          })}
                          className="w-20 h-8 text-sm"
                          data-testid={`delay-input-${account.account_id}`}
                        />
                        <span className="text-xs text-slate-400">sec</span>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleUpdateDelay(account.account_id)}
                          disabled={savingDelay[account.account_id]}
                          className="h-8"
                          data-testid={`save-delay-${account.account_id}`}
                        >
                          {savingDelay[account.account_id] ? (
                            <Loader2 size={14} className="animate-spin" />
                          ) : (
                            <Save size={14} />
                          )}
                        </Button>
                      </div>
                    </div>

                    {/* Usage Stats */}
                    <div className="flex items-center gap-4 mt-4">
                      <div>
                        <p className="text-xs text-slate-500">Sent Today</p>
                        <p className="font-semibold text-slate-900">
                          {account.daily_send_count || 0} / {account.daily_limit || 50}
                        </p>
                      </div>
                      <div className="flex-1">
                        <Progress
                          value={((account.daily_send_count || 0) / (account.daily_limit || 50)) * 100}
                          className="h-2"
                        />
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">Remaining</p>
                        <p className="font-semibold text-slate-900">
                          {(account.daily_limit || 50) - (account.daily_send_count || 0)}
                        </p>
                      </div>
                    </div>

                    {/* Warmup Section */}
                    <div className="mt-4 pt-4 border-t border-slate-100">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <Flame size={18} className={account.warmup_enabled ? "text-orange-500" : "text-slate-400"} />
                          <div>
                            <p className="text-sm font-medium text-slate-700">Email Warmup</p>
                            <p className="text-xs text-slate-500">
                              {account.warmup_enabled 
                                ? `Status: ${account.warmup_status === 'active' ? 'Active' : 'Paused'} • Day ${account.warmup_day || 1}`
                                : 'Gradually warm up this account'
                              }
                            </p>
                          </div>
                        </div>
                        
                        <div className="flex items-center gap-2">
                          {account.warmup_enabled ? (
                            <>
                              {/* Stats Button */}
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => fetchWarmupStats(account.account_id)}
                                className="text-slate-500"
                                data-testid={`warmup-stats-${account.account_id}`}
                              >
                                <BarChart3 size={14} className="mr-1" />
                                Stats
                              </Button>
                              
                              {/* Pause/Resume */}
                              {account.warmup_status === 'active' ? (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handlePauseWarmup(account.account_id)}
                                  disabled={warmupLoading[account.account_id]}
                                  className="text-amber-600"
                                  data-testid={`pause-warmup-${account.account_id}`}
                                >
                                  {warmupLoading[account.account_id] ? (
                                    <Loader2 size={14} className="animate-spin mr-1" />
                                  ) : (
                                    <Pause size={14} className="mr-1" />
                                  )}
                                  Pause
                                </Button>
                              ) : (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleResumeWarmup(account.account_id)}
                                  disabled={warmupLoading[account.account_id]}
                                  className="text-green-600"
                                  data-testid={`resume-warmup-${account.account_id}`}
                                >
                                  {warmupLoading[account.account_id] ? (
                                    <Loader2 size={14} className="animate-spin mr-1" />
                                  ) : (
                                    <Play size={14} className="mr-1" />
                                  )}
                                  Resume
                                </Button>
                              )}
                              
                              {/* Settings */}
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => openWarmupSettings(account)}
                                className="text-slate-500"
                                data-testid={`warmup-settings-${account.account_id}`}
                              >
                                <Settings size={14} />
                              </Button>
                              
                              {/* Disable */}
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDisableWarmup(account.account_id)}
                                disabled={warmupLoading[account.account_id]}
                                className="text-red-500"
                                data-testid={`disable-warmup-${account.account_id}`}
                              >
                                Disable
                              </Button>
                            </>
                          ) : (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => openWarmupSettings(account)}
                              className="text-orange-600 border-orange-300 hover:bg-orange-50"
                              data-testid={`enable-warmup-${account.account_id}`}
                            >
                              <Flame size={14} className="mr-1" />
                              Enable Warmup
                            </Button>
                          )}
                        </div>
                      </div>
                      
                      {/* Warmup Progress - Show when enabled */}
                      {account.warmup_enabled && account.warmup_status === 'active' && (
                        <div className="mt-3 p-3 bg-orange-50 border border-orange-100 rounded-lg">
                          <div className="flex items-center justify-between text-sm">
                            <span className="text-orange-700">
                              <TrendingUp size={14} className="inline mr-1" />
                              Warming up: Day {account.warmup_day || 1}
                            </span>
                            <span className="text-orange-600 font-medium">
                              {account.warmup_settings?.starting_emails_per_day || 5} → {account.warmup_settings?.max_emails_per_day || 50} emails/day
                            </span>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          ) : (
            <div className="bg-white border border-slate-200 rounded-md p-12 text-center">
              <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Mail size={32} className="text-slate-400" />
              </div>
              <h3 className="font-heading font-semibold text-lg text-slate-900 mb-2">
                No email accounts yet
              </h3>
              <p className="text-slate-500 mb-6">
                Add your first SMTP email account to start sending campaigns
              </p>
              <Button
                onClick={() => { resetForm(); setAddDialogOpen(true); }}
                className="bg-electric-blue hover:bg-blue-700"
                data-testid="add-first-account-btn"
              >
                <Plus size={18} className="mr-2" />
                Add Email Account
              </Button>
            </div>
          )}
        </div>
      </main>

      {/* Add Account Dialog */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="font-heading font-semibold">Add SMTP Email Account</DialogTitle>
            <DialogDescription>Connect your email account via SMTP to start sending campaigns.</DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div>
              <Label>Email Provider</Label>
              <Select value={formData.preset} onValueChange={handlePresetChange}>
                <SelectTrigger className="mt-1.5" data-testid="preset-select">
                  <SelectValue placeholder="Choose provider" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="gmail">Gmail</SelectItem>
                  <SelectItem value="outlook">Outlook / Office 365</SelectItem>
                  <SelectItem value="yahoo">Yahoo Mail</SelectItem>
                  <SelectItem value="custom">Custom SMTP</SelectItem>
                </SelectContent>
              </Select>
              {SMTP_PRESETS[formData.preset]?.note && (
                <p className="text-xs text-amber-600 mt-1">{SMTP_PRESETS[formData.preset].note}</p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="email">Email Address</Label>
                <Input id="email" type="email" placeholder="your@email.com" value={formData.email}
                  onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                  className="mt-1.5" data-testid="email-input" />
              </div>
              <div>
                <Label htmlFor="display_name">Display Name</Label>
                <Input id="display_name" placeholder="John Doe" value={formData.display_name}
                  onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                  className="mt-1.5" data-testid="display-name-input" />
              </div>
              <div>
                <Label htmlFor="from_name">Default From Name</Label>
                <Input id="from_name" placeholder="e.g. Sales Team" value={formData.from_name}
                  onChange={(e) => setFormData({ ...formData, from_name: e.target.value })}
                  className="mt-1.5" data-testid="from-name-input" />
                <p className="text-xs text-slate-500 mt-1">
                  Used as the sender display name unless a campaign overrides it.
                </p>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-200">
              <p className="font-medium text-slate-900 mb-3 flex items-center gap-2">
                <Server size={16} /> SMTP Settings
              </p>

              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="smtp_host">SMTP Host</Label>
                    <Input id="smtp_host" placeholder="smtp.example.com" value={formData.smtp_host}
                      onChange={(e) => setFormData({ ...formData, smtp_host: e.target.value })}
                      className="mt-1.5" data-testid="smtp-host-input" />
                  </div>
                  <div>
                    <Label htmlFor="smtp_port">Port</Label>
                    <Input id="smtp_port" type="number" placeholder="587" value={formData.smtp_port}
                      onChange={(e) => setFormData({ ...formData, smtp_port: parseInt(e.target.value) || 587 })}
                      className="mt-1.5" data-testid="smtp-port-input" />
                  </div>
                </div>

                <div>
                  <Label htmlFor="smtp_username">Username</Label>
                  <Input id="smtp_username" placeholder="your@email.com" value={formData.smtp_username}
                    onChange={(e) => setFormData({ ...formData, smtp_username: e.target.value })}
                    className="mt-1.5" data-testid="smtp-username-input" />
                </div>

                <div>
                  <Label htmlFor="smtp_password">Password / App Password</Label>
                  <div className="relative mt-1.5">
                    <Input id="smtp_password" type={showPassword ? "text" : "password"} placeholder="••••••••••••"
                      value={formData.smtp_password}
                      onChange={(e) => setFormData({ ...formData, smtp_password: e.target.value })}
                      className="pr-10" data-testid="smtp-password-input" />
                    <button type="button" onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                      {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label>Encryption</Label>
                    <Select value={formData.smtp_encryption}
                      onValueChange={(value) => setFormData({ ...formData, smtp_encryption: value })}>
                      <SelectTrigger className="mt-1.5" data-testid="encryption-select">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="tls">TLS (Recommended)</SelectItem>
                        <SelectItem value="ssl">SSL</SelectItem>
                        <SelectItem value="none">None</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>Daily Limit</Label>
                    <Input type="number" min="1" value={formData.daily_limit}
                      onChange={(e) => setFormData({ ...formData, daily_limit: Math.max(1, parseInt(e.target.value) || 50) })}
                      className="mt-1.5" data-testid="daily-limit-input" />
                    <p className="text-xs text-slate-500 mt-1">
                      Recommended maximum: 50 emails per day for better deliverability.
                    </p>
                  </div>
                </div>

                <div>
                  <Label>Delay Between Emails (seconds)</Label>
                  <Input type="number" min="10" max="300" value={formData.send_delay}
                    onChange={(e) => setFormData({ ...formData, send_delay: parseInt(e.target.value) || 30 })}
                    className="mt-1.5" data-testid="send-delay-input" />
                  <p className="text-xs text-slate-500 mt-1">
                    Time to wait between consecutive emails (10-300 seconds). Default: 30 seconds.
                  </p>
                </div>
              </div>
            </div>

            {/* IMAP / Receiving Settings */}
            <div className="pt-4 border-t border-slate-200">
              <p className="font-medium text-slate-900 mb-1 flex items-center gap-2">
                <Server size={16} /> Receiving Settings (IMAP)
              </p>
              <p className="text-xs text-slate-500 mb-3">
                Required for Unibox reply tracking and incoming email sync. Leave blank to skip — sending will still work.
              </p>
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <Label htmlFor="imap_host">IMAP Host</Label>
                    <Input id="imap_host" placeholder="imap.example.com" value={formData.imap_host}
                      onChange={(e) => setFormData({ ...formData, imap_host: e.target.value })}
                      className="mt-1.5" data-testid="imap-host-input" />
                  </div>
                  <div>
                    <Label htmlFor="imap_port">IMAP Port</Label>
                    <Input id="imap_port" type="number" placeholder="993" value={formData.imap_port}
                      onChange={(e) => setFormData({ ...formData, imap_port: parseInt(e.target.value) || 993 })}
                      className="mt-1.5" data-testid="imap-port-input" />
                  </div>
                </div>
                <div>
                  <Label htmlFor="imap_username">IMAP Username</Label>
                  <Input id="imap_username" placeholder="defaults to email if blank" value={formData.imap_username}
                    onChange={(e) => setFormData({ ...formData, imap_username: e.target.value })}
                    className="mt-1.5" data-testid="imap-username-input" />
                </div>
                <div>
                  <Label htmlFor="imap_password">IMAP Password / App Password</Label>
                  <Input id="imap_password" type="password" placeholder="leave blank to reuse SMTP password"
                    value={formData.imap_password}
                    onChange={(e) => setFormData({ ...formData, imap_password: e.target.value })}
                    className="mt-1.5" data-testid="imap-password-input" />
                </div>
                <div>
                  <Label>IMAP Encryption</Label>
                  <Select value={formData.imap_encryption}
                    onValueChange={(value) => setFormData({ ...formData, imap_encryption: value })}>
                    <SelectTrigger className="mt-1.5" data-testid="imap-encryption-select">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="ssl">SSL (Recommended for IMAP)</SelectItem>
                      <SelectItem value="tls">STARTTLS</SelectItem>
                      <SelectItem value="none">None</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>

            <div className="flex items-start gap-2 p-3 bg-slate-50 rounded-md">
              <Lock size={16} className="text-slate-500 flex-shrink-0 mt-0.5" />
              <p className="text-xs text-slate-600">
                Your credentials are encrypted before storage. We never store plain-text passwords.
              </p>
            </div>
          </div>

          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button variant="outline" onClick={handleTestConnection} disabled={testing} data-testid="test-connection-btn">
              {testing ? <><Loader2 size={16} className="mr-2 animate-spin" />Testing...</> : "Test Connection"}
            </Button>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => { setAddDialogOpen(false); resetForm(); }} data-testid="cancel-add-btn">
                Cancel
              </Button>
              <Button onClick={handleAddAccount} disabled={submitting} className="bg-electric-blue hover:bg-blue-700"
                data-testid="confirm-add-btn">
                {submitting ? "Adding..." : "Add Account"}
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading font-semibold">Remove Email Account</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove {selectedAccount?.email}? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="cancel-delete-btn">Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteAccount} className="bg-red-600 hover:bg-red-700"
              data-testid="confirm-delete-btn">Remove</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Warmup Settings Modal */}
      <Dialog open={warmupModalOpen} onOpenChange={setWarmupModalOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Flame className="text-orange-500" />
              Email Warmup Settings
            </DialogTitle>
            <DialogDescription>
              Configure warmup settings for {warmupAccount?.email}
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="bg-orange-50 border border-orange-200 rounded-lg p-3">
              <p className="text-sm text-orange-800">
                <strong>Note:</strong> Warmup emails will include "(RTM)" in the subject line for easy identification. 
                Emails are sent between your connected accounts.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Starting Emails/Day</Label>
                <Input
                  type="number"
                  min="1"
                  max="20"
                  value={warmupSettings.starting_emails_per_day}
                  onChange={(e) => setWarmupSettings({
                    ...warmupSettings,
                    starting_emails_per_day: parseInt(e.target.value) || 5
                  })}
                  className="mt-1.5"
                />
                <p className="text-xs text-slate-500 mt-1">1-20 emails</p>
              </div>
              <div>
                <Label>Max Emails/Day</Label>
                <Input
                  type="number"
                  min="10"
                  max="100"
                  value={warmupSettings.max_emails_per_day}
                  onChange={(e) => setWarmupSettings({
                    ...warmupSettings,
                    max_emails_per_day: parseInt(e.target.value) || 50
                  })}
                  className="mt-1.5"
                />
                <p className="text-xs text-slate-500 mt-1">10-100 emails</p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Daily Increment</Label>
                <Input
                  type="number"
                  min="1"
                  max="10"
                  value={warmupSettings.daily_increment}
                  onChange={(e) => setWarmupSettings({
                    ...warmupSettings,
                    daily_increment: parseInt(e.target.value) || 5
                  })}
                  className="mt-1.5"
                />
                <p className="text-xs text-slate-500 mt-1">+1 to +10/day</p>
              </div>
              <div>
                <Label>Reply Rate (%)</Label>
                <Input
                  type="number"
                  min="30"
                  max="50"
                  value={warmupSettings.reply_rate}
                  onChange={(e) => setWarmupSettings({
                    ...warmupSettings,
                    reply_rate: parseInt(e.target.value) || 40
                  })}
                  className="mt-1.5"
                />
                <p className="text-xs text-slate-500 mt-1">30-50%</p>
              </div>
            </div>

            <div className="pt-3 border-t border-slate-100">
              <p className="text-sm text-slate-600">
                <strong>Warmup Schedule:</strong> Day 1: {warmupSettings.starting_emails_per_day} emails → 
                Day {Math.ceil((warmupSettings.max_emails_per_day - warmupSettings.starting_emails_per_day) / warmupSettings.daily_increment) + 1}: {warmupSettings.max_emails_per_day} emails
              </p>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setWarmupModalOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={() => warmupAccount && handleEnableWarmup(warmupAccount)}
              disabled={warmupLoading[warmupAccount?.account_id]}
              className="bg-orange-500 hover:bg-orange-600"
            >
              {warmupLoading[warmupAccount?.account_id] ? (
                <Loader2 size={16} className="animate-spin mr-2" />
              ) : (
                <Flame size={16} className="mr-2" />
              )}
              {warmupAccount?.warmup_enabled ? "Update Settings" : "Enable Warmup"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bulk Delete Confirmation */}
      <AlertDialog open={bulkDeleteOpen} onOpenChange={(o) => { if (!o) { setBulkDeleteOpen(false); setBulkDeleteBlocked(null); } }}>
        <AlertDialogContent data-testid="bulk-delete-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <Trash2 className="text-red-600" />
              {bulkDeleteBlocked ? "Some accounts are in use" : "Delete selected email accounts?"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {!bulkDeleteBlocked ? (
                <>
                  Are you sure you want to delete the <span className="font-semibold">{selectedIds.length}</span>{" "}
                  selected email account{selectedIds.length === 1 ? "" : "s"}? <span className="font-semibold">This action cannot be undone.</span>
                  <span className="block mt-2 text-slate-600">
                    Campaign history, sending logs, and Unibox replies will NOT be deleted — only the
                    account configurations will be removed and they will no longer appear in campaign account selection.
                  </span>
                </>
              ) : (
                <>
                  <span className="block">
                    {bulkDeleteBlocked.blocked_accounts.length} selected account
                    {bulkDeleteBlocked.blocked_accounts.length === 1 ? " is" : "s are"} currently used by a running or scheduled campaign.
                  </span>
                  {bulkDeleteBlocked.active_campaigns?.length > 0 && (
                    <span className="block mt-2 text-slate-700">
                      Active campaigns: {bulkDeleteBlocked.active_campaigns.map((c) => c.name).join(", ")}
                    </span>
                  )}
                  {bulkDeleteBlocked.active_drips?.length > 0 && (
                    <span className="block text-slate-700">
                      Active drips: {bulkDeleteBlocked.active_drips.map((c) => c.name).join(", ")}
                    </span>
                  )}
                  <span className="block mt-2 text-amber-700 font-medium">
                    Continuing will break those campaigns. Pause them first if you want to be safe.
                  </span>
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={bulkDeleteBusy} data-testid="cancel-bulk-delete">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => submitBulkDelete(!!bulkDeleteBlocked)}
              disabled={bulkDeleteBusy}
              className="bg-red-600 hover:bg-red-700"
              data-testid="confirm-bulk-delete"
            >
              {bulkDeleteBusy ? <Loader2 size={14} className="animate-spin mr-2" /> : <Trash2 size={14} className="mr-2" />}
              {bulkDeleteBlocked ? "Delete Anyway" : "Delete Accounts"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>


      {/* Bulk Warmup Settings Modal */}
      <Dialog open={bulkSettingsOpen} onOpenChange={setBulkSettingsOpen}>
        <DialogContent className="sm:max-w-lg" data-testid="bulk-settings-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Flame className="text-orange-500" />
              {bulkSettingsMode === "start" ? "Start Warmup — Bulk" : "Update Warmup Settings — Bulk"}
            </DialogTitle>
            <DialogDescription>
              These settings will apply to all <span className="font-semibold">{selectedIds.length}</span> selected account{selectedIds.length === 1 ? "" : "s"}.
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-4 py-2">
            <div>
              <Label className="text-xs text-slate-500">Starting emails/day</Label>
              <Input
                type="number"
                min="1"
                max="20"
                value={bulkSettings.starting_emails_per_day}
                onChange={(e) =>
                  setBulkSettings({ ...bulkSettings, starting_emails_per_day: parseInt(e.target.value) || 1 })
                }
                data-testid="bulk-starting"
              />
            </div>
            <div>
              <Label className="text-xs text-slate-500">Max emails/day</Label>
              <Input
                type="number"
                min="10"
                max="100"
                value={bulkSettings.max_emails_per_day}
                onChange={(e) =>
                  setBulkSettings({ ...bulkSettings, max_emails_per_day: parseInt(e.target.value) || 10 })
                }
                data-testid="bulk-max"
              />
            </div>
            <div>
              <Label className="text-xs text-slate-500">Daily increment</Label>
              <Input
                type="number"
                min="1"
                max="10"
                value={bulkSettings.daily_increment}
                onChange={(e) =>
                  setBulkSettings({ ...bulkSettings, daily_increment: parseInt(e.target.value) || 1 })
                }
                data-testid="bulk-increment"
              />
            </div>
            <div>
              <Label className="text-xs text-slate-500">Reply rate (%)</Label>
              <Input
                type="number"
                min="30"
                max="50"
                value={bulkSettings.reply_rate}
                onChange={(e) =>
                  setBulkSettings({ ...bulkSettings, reply_rate: parseInt(e.target.value) || 30 })
                }
                data-testid="bulk-reply-rate"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setBulkSettingsOpen(false)} disabled={bulkBusy} data-testid="bulk-settings-cancel">
              Cancel
            </Button>
            <Button
              onClick={submitBulkSettings}
              disabled={bulkBusy || selectedIds.length === 0}
              className="bg-orange-500 hover:bg-orange-600 text-white"
              data-testid="bulk-settings-confirm"
            >
              {bulkBusy ? <Loader2 size={16} className="animate-spin mr-2" /> : null}
              {bulkSettingsMode === "start" ? "Start Warmup" : "Save Settings"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Warmup Stats Modal */}
      <Dialog open={warmupStatsModal} onOpenChange={setWarmupStatsModal}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <BarChart3 className="text-blue-500" />
              Warmup Statistics
            </DialogTitle>
          </DialogHeader>
          
          {warmupStats && (
            <div className="space-y-4 py-4">
              {/* Today's Stats */}
              <div className="bg-slate-50 rounded-lg p-4">
                <h4 className="font-medium text-slate-700 mb-3">Today's Activity</h4>
                <div className="grid grid-cols-3 gap-4">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-blue-600">{warmupStats.today?.emails_sent || 0}</p>
                    <p className="text-xs text-slate-500">Emails Sent</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-green-600">{warmupStats.today?.replies_sent || 0}</p>
                    <p className="text-xs text-slate-500">Replies</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-purple-600">{warmupStats.today?.opens_tracked || 0}</p>
                    <p className="text-xs text-slate-500">Opens</p>
                  </div>
                </div>
              </div>

              {/* Current Progress */}
              <div className="bg-orange-50 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-orange-700">Warmup Day {warmupStats.warmup_day || 1}</span>
                  <span className="text-sm font-medium text-orange-800">
                    Target: {warmupStats.current_daily_target || 5} emails/day
                  </span>
                </div>
                <Progress 
                  value={((warmupStats.today?.emails_sent || 0) / (warmupStats.current_daily_target || 5)) * 100}
                  className="h-2 bg-orange-200"
                />
              </div>

              {/* Weekly Summary */}
              <div>
                <h4 className="font-medium text-slate-700 mb-3">Last 7 Days</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-blue-50 rounded-lg p-3 text-center">
                    <p className="text-xl font-bold text-blue-600">{warmupStats.weekly?.total_sent || 0}</p>
                    <p className="text-xs text-slate-500">Total Sent</p>
                  </div>
                  <div className="bg-green-50 rounded-lg p-3 text-center">
                    <p className="text-xl font-bold text-green-600">{warmupStats.weekly?.total_replies || 0}</p>
                    <p className="text-xs text-slate-500">Total Replies</p>
                  </div>
                </div>
              </div>

              {/* Settings Summary */}
              <div className="pt-3 border-t border-slate-100">
                <p className="text-sm text-slate-600">
                  <strong>Settings:</strong> {warmupStats.settings?.starting_emails_per_day || 5} → {warmupStats.settings?.max_emails_per_day || 50} emails/day 
                  (+{warmupStats.settings?.daily_increment || 5}/day), {warmupStats.settings?.reply_rate || 40}% reply rate
                </p>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setWarmupStatsModal(false)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* View Account Dialog */}
      <Dialog open={!!viewAccount} onOpenChange={(o) => !o && setViewAccount(null)}>
        <DialogContent data-testid="view-account-dialog">
          <DialogHeader>
            <DialogTitle>Account details</DialogTitle>
            <DialogDescription>
              Current server configuration for this email account.
            </DialogDescription>
          </DialogHeader>
          {viewAccount && (
            <div className="space-y-3 text-sm">
              <DetailRow label="Display name" value={viewAccount.display_name} />
              <DetailRow label="Email" value={viewAccount.email} mono />
              <DetailRow label="SMTP host" value={viewAccount.smtp_host} mono />
              <DetailRow label="SMTP port" value={viewAccount.smtp_port} mono />
              <DetailRow label="SMTP username" value={viewAccount.smtp_username || viewAccount.email} mono />
              <DetailRow label="Encryption" value={(viewAccount.smtp_encryption || "tls").toUpperCase()} />
              <DetailRow label="Password" value="••••••••••• (hidden)" mono />
              <DetailRow label="Daily sending limit" value={`${viewAccount.daily_limit || 50} emails/day`} />
              <DetailRow label="Delay between emails" value={`${viewAccount.send_delay || 30}s`} />
              <DetailRow
                label="Status"
                value={viewAccount.status === "connected" ? "Connected" : "Error"}
              />
              {viewAccount.last_error && (
                <div className="p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
                  {viewAccount.last_error}
                </div>
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setViewAccount(null)}>Close</Button>
            {viewAccount && (
              <Button
                onClick={() => { handleOpenEdit(viewAccount); setViewAccount(null); }}
                className="bg-electric-blue hover:bg-blue-700"
                data-testid="view-to-edit-btn"
              >
                <Edit3 size={14} className="mr-2" /> Edit settings
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Account Dialog */}
      <Dialog open={!!editingAccount} onOpenChange={(o) => !o && setEditingAccount(null)}>
        <DialogContent className="max-w-xl" data-testid="edit-account-dialog">
          <DialogHeader>
            <DialogTitle>Edit server settings</DialogTitle>
            <DialogDescription>
              Update SMTP details. Your saved password is never displayed — only set a new value if
              you want to rotate it.
            </DialogDescription>
          </DialogHeader>
          {editingAccount && (
            <div className="space-y-3 max-h-[60vh] overflow-y-auto pr-1">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Email address</Label>
                  <Input
                    value={editForm.email || ""}
                    onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                    data-testid="edit-email"
                  />
                </div>
                <div>
                  <Label>Display name</Label>
                  <Input
                    value={editForm.display_name || ""}
                    onChange={(e) => setEditForm({ ...editForm, display_name: e.target.value })}
                    data-testid="edit-display-name"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>SMTP host</Label>
                  <Input
                    value={editForm.smtp_host || ""}
                    onChange={(e) => setEditForm({ ...editForm, smtp_host: e.target.value })}
                    data-testid="edit-smtp-host"
                  />
                </div>
                <div>
                  <Label>SMTP port</Label>
                  <Input
                    type="number"
                    value={editForm.smtp_port || ""}
                    onChange={(e) => setEditForm({ ...editForm, smtp_port: parseInt(e.target.value || "0") })}
                    data-testid="edit-smtp-port"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>SMTP username</Label>
                  <Input
                    value={editForm.smtp_username || ""}
                    onChange={(e) => setEditForm({ ...editForm, smtp_username: e.target.value })}
                    data-testid="edit-smtp-username"
                  />
                </div>
                <div>
                  <Label>Encryption</Label>
                  <Select
                    value={editForm.smtp_encryption || "tls"}
                    onValueChange={(v) => setEditForm({ ...editForm, smtp_encryption: v })}
                  >
                    <SelectTrigger data-testid="edit-encryption">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="tls">STARTTLS</SelectItem>
                      <SelectItem value="ssl">SSL</SelectItem>
                      <SelectItem value="none">None</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div>
                <Label>Password / App password</Label>
                <div className="relative">
                  <Input
                    type={showEditPassword ? "text" : "password"}
                    placeholder="Saved credentials shown — edit to update"
                    value={editForm.smtp_password || ""}
                    onChange={(e) => setEditForm({ ...editForm, smtp_password: e.target.value })}
                    className="pr-10"
                    data-testid="edit-smtp-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowEditPassword(!showEditPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400"
                    aria-label="Toggle password visibility"
                  >
                    {showEditPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                <p className="text-xs text-slate-500 mt-1">
                  Your saved app password is shown so you can review or edit it. Changes are
                  re-tested via SMTP before saving.
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Daily sending limit</Label>
                  <Input
                    type="number"
                    min={1}
                    value={editForm.daily_limit || 50}
                    onChange={(e) => setEditForm({ ...editForm, daily_limit: Math.max(1, parseInt(e.target.value || "0")) })}
                    data-testid="edit-daily-limit"
                  />
                  <p className="text-xs text-slate-500 mt-1">
                    Recommended maximum: 50 emails per day for better deliverability.
                  </p>
                </div>
                <div>
                  <Label>Delay between emails (s)</Label>
                  <Input
                    type="number"
                    min={10}
                    max={300}
                    value={editForm.send_delay || 30}
                    onChange={(e) => setEditForm({ ...editForm, send_delay: parseInt(e.target.value || "0") })}
                    data-testid="edit-send-delay"
                  />
                </div>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingAccount(null)}>Cancel</Button>
            <Button
              onClick={handleSaveEdit}
              disabled={savingEdit}
              className="bg-electric-blue hover:bg-blue-700"
              data-testid="edit-account-save-btn"
            >
              {savingEdit ? "Saving…" : "Save changes"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Bulk Import Dialog */}
      <Dialog open={importDialogOpen} onOpenChange={(o) => { setImportDialogOpen(o); if (!o) { setImportFile(null); setImportResult(null); } }}>
        <DialogContent className="max-w-xl" data-testid="import-accounts-dialog">
          <DialogHeader>
            <DialogTitle>Import email accounts via CSV</DialogTitle>
            <DialogDescription>
              Each valid row is tested via SMTP before being added. Duplicates (by email) are skipped.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="bg-slate-50 border border-slate-200 rounded-md p-3 text-xs text-slate-600">
              Required columns: <span className="font-mono">email, password, smtp_host, smtp_port</span>.
              Optional: <span className="font-mono">imap_host, imap_port, use_ssl, daily_limit, delay_seconds</span>.
              Delay defaults to <strong>30s</strong> when empty.
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleDownloadSample}
                data-testid="dialog-download-sample-btn"
              >
                <Download size={14} className="mr-1.5" /> Download sample CSV
              </Button>
            </div>
            <div>
              <Label>CSV file</Label>
              <Input
                type="file"
                accept=".csv"
                onChange={(e) => { setImportFile(e.target.files?.[0] || null); setImportResult(null); }}
                data-testid="import-file-input"
                className="mt-1.5"
              />
            </div>

            {importResult && (
              <div className="space-y-2" data-testid="import-result-panel">
                <div className="flex gap-2 text-xs">
                  <span className="px-2 py-1 rounded bg-green-100 text-green-700">
                    Imported {importResult.imported}
                  </span>
                  <span className="px-2 py-1 rounded bg-slate-100 text-slate-700">
                    Skipped {importResult.skipped}
                  </span>
                  <span className="px-2 py-1 rounded bg-red-100 text-red-700">
                    Failed {importResult.failed}
                  </span>
                </div>
                <div className="max-h-48 overflow-y-auto border border-slate-200 rounded-md">
                  <table className="w-full text-xs">
                    <thead className="bg-slate-50">
                      <tr className="text-left text-slate-500">
                        <th className="px-2 py-1">Row</th>
                        <th className="px-2 py-1">Email</th>
                        <th className="px-2 py-1">Status</th>
                        <th className="px-2 py-1">Error</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(importResult.results || []).map((r, i) => (
                        <tr key={i} className="border-t border-slate-100">
                          <td className="px-2 py-1 text-slate-500">{r.row}</td>
                          <td className="px-2 py-1 font-mono">{r.email}</td>
                          <td className="px-2 py-1">
                            <span className={
                              r.status === "imported" ? "text-green-700" :
                              r.status === "skipped" ? "text-slate-500" : "text-red-600"
                            }>
                              {r.status}
                            </span>
                          </td>
                          <td className="px-2 py-1 text-red-600">{r.error || ""}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setImportDialogOpen(false)}>Close</Button>
            <Button
              onClick={handleImportSubmit}
              disabled={importing || !importFile}
              className="bg-electric-blue hover:bg-blue-700"
              data-testid="import-submit-btn"
            >
              {importing ? (<><Loader2 size={14} className="animate-spin mr-2" /> Importing…</>) : "Import accounts"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function DetailRow({ label, value, mono }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-slate-100 pb-2 last:border-0">
      <span className="text-slate-500">{label}</span>
      <span className={`text-slate-900 ${mono ? "font-mono text-xs" : ""}`}>{value || "—"}</span>
    </div>
  );
}
