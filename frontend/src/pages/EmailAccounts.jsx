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
import { api } from "../App";
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

  const [formData, setFormData] = useState({
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
        smtp_host: formData.smtp_host,
        smtp_port: formData.smtp_port,
        smtp_username: formData.smtp_username,
        smtp_password: formData.smtp_password,
        smtp_encryption: formData.smtp_encryption,
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
    const newLimit = editingLimit[accountId];
    if (newLimit < 10 || newLimit > 200) {
      toast.error("Daily limit must be between 10 and 200");
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
            <Button
              onClick={() => { resetForm(); setAddDialogOpen(true); }}
              className="bg-electric-blue hover:bg-blue-700"
              data-testid="add-account-btn"
            >
              <Plus size={18} className="mr-2" />
              Add Account
            </Button>
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

          {/* Accounts List */}
          {accounts.length > 0 ? (
            <div className="space-y-4">
              {accounts.map((account, index) => (
                <motion.div
                  key={account.account_id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                  className="bg-white border border-slate-200 rounded-md p-6"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-center gap-4">
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

                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2">
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
                          min="10"
                          max="200"
                          value={editingLimit[account.account_id] || 50}
                          onChange={(e) => setEditingLimit({
                            ...editingLimit,
                            [account.account_id]: parseInt(e.target.value) || 50
                          })}
                          className="w-20 h-8 text-sm"
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
                    <Label>Daily Limit (10-200)</Label>
                    <Input type="number" min="10" max="200" value={formData.daily_limit}
                      onChange={(e) => setFormData({ ...formData, daily_limit: parseInt(e.target.value) || 50 })}
                      className="mt-1.5" data-testid="daily-limit-input" />
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
    </div>
  );
}
