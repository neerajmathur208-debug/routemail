import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import {
  Mail,
  Plus,
  Trash2,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Info,
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

export default function EmailAccounts({ user, setUser }) {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState(null);
  const [formData, setFormData] = useState({ email: "", display_name: "" });
  const [submitting, setSubmitting] = useState(false);

  const fetchAccounts = async () => {
    try {
      const response = await api.get("/accounts");
      setAccounts(response.data);
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

  const handleAddAccount = async () => {
    if (!formData.email || !formData.display_name) {
      toast.error("Please fill in all fields");
      return;
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(formData.email)) {
      toast.error("Please enter a valid email address");
      return;
    }

    setSubmitting(true);
    try {
      await api.post("/accounts", formData);
      toast.success("Email account added successfully");
      setAddDialogOpen(false);
      setFormData({ email: "", display_name: "" });
      fetchAccounts();
    } catch (error) {
      const message = error.response?.data?.detail || "Failed to add account";
      toast.error(message);
    } finally {
      setSubmitting(false);
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

  const needsSubscription = false; // Subscription removed - all features unlocked

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
          {/* Header */}
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="font-heading font-extrabold text-2xl sm:text-3xl text-slate-900">
                Email Accounts
              </h1>
              <p className="text-slate-500 mt-1">
                Manage your connected email accounts for sending
              </p>
            </div>
            <Button
              onClick={() => setAddDialogOpen(true)}
              disabled={needsSubscription}
              className="bg-electric-blue hover:bg-blue-700"
              data-testid="add-account-btn"
            >
              <Plus size={18} className="mr-2" />
              Add Account
            </Button>
          </div>

          {/* Subscription Alert */}
          {needsSubscription && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-6 bg-amber-50 border border-amber-200 rounded-md p-4 flex items-center gap-4"
            >
              <AlertCircle size={20} className="text-amber-600 flex-shrink-0" />
              <div className="flex-1">
                <p className="text-amber-800 font-medium">Subscription required</p>
                <p className="text-amber-700 text-sm">
                  Subscribe to add and manage email accounts
                </p>
              </div>
            </motion.div>
          )}

          {/* Info Box */}
          <div className="mb-6 bg-blue-50 border border-blue-200 rounded-md p-4 flex items-start gap-3">
            <Info size={20} className="text-blue-600 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-blue-800 font-medium">Simulated Email Accounts</p>
              <p className="text-blue-700 text-sm mt-1">
                This is a demo mode. Add email accounts to test the rotation logic.
                Actual email sending is simulated.
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
                        <p className="font-semibold text-slate-900">
                          {account.display_name}
                        </p>
                        <p className="font-mono text-sm text-slate-500">
                          {account.email}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-2">
                        {account.status === "connected" ? (
                          <>
                            <CheckCircle2 size={16} className="text-green-600" />
                            <span className="text-sm text-green-600 font-medium">
                              Connected
                            </span>
                          </>
                        ) : (
                          <>
                            <XCircle size={16} className="text-red-500" />
                            <span className="text-sm text-red-500 font-medium">
                              Error
                            </span>
                          </>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-slate-400 hover:text-red-500"
                        onClick={() => {
                          setSelectedAccount(account);
                          setDeleteDialogOpen(true);
                        }}
                        data-testid={`delete-account-${account.account_id}`}
                      >
                        <Trash2 size={18} />
                      </Button>
                    </div>
                  </div>

                  <div className="mt-4 pt-4 border-t border-slate-100 flex items-center gap-6">
                    <div>
                      <p className="text-xs text-slate-500 uppercase tracking-wide">
                        Sent Today
                      </p>
                      <p className="font-semibold text-slate-900">
                        {account.daily_send_count || 0} / 50
                      </p>
                    </div>
                    <div className="flex-1">
                      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-electric-blue rounded-full transition-all"
                          style={{
                            width: `${((account.daily_send_count || 0) / 50) * 100}%`,
                          }}
                        />
                      </div>
                    </div>
                    <div>
                      <p className="text-xs text-slate-500 uppercase tracking-wide">
                        Remaining
                      </p>
                      <p className="font-semibold text-slate-900">
                        {50 - (account.daily_send_count || 0)}
                      </p>
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
                Add your first email account to start sending campaigns
              </p>
              <Button
                onClick={() => setAddDialogOpen(true)}
                disabled={needsSubscription}
                className="bg-electric-blue hover:bg-blue-700"
                data-testid="add-first-account-btn"
              >
                <Plus size={18} className="mr-2" />
                Add Email Account
              </Button>
            </div>
          )}

          {/* Limit Info */}
          <div className="mt-8 p-4 bg-slate-100 rounded-md">
            <p className="text-sm text-slate-600">
              <strong>Daily Limit:</strong> Each email account can send up to 50
              emails per day. This limit resets at midnight UTC. When an account
              reaches its limit, the system automatically rotates to the next
              available account.
            </p>
          </div>
        </div>
      </main>

      {/* Add Account Dialog */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="font-heading font-semibold">
              Add Email Account
            </DialogTitle>
            <DialogDescription>
              Add an email account to use for sending campaigns. This is a demo
              mode - actual OAuth connection is not required.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="email">Email Address</Label>
              <Input
                id="email"
                type="email"
                placeholder="your@email.com"
                value={formData.email}
                onChange={(e) =>
                  setFormData({ ...formData, email: e.target.value })
                }
                className="mt-1.5"
                data-testid="email-input"
              />
            </div>
            <div>
              <Label htmlFor="display_name">Display Name</Label>
              <Input
                id="display_name"
                placeholder="John Doe"
                value={formData.display_name}
                onChange={(e) =>
                  setFormData({ ...formData, display_name: e.target.value })
                }
                className="mt-1.5"
                data-testid="display-name-input"
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setAddDialogOpen(false)}
              data-testid="cancel-add-btn"
            >
              Cancel
            </Button>
            <Button
              onClick={handleAddAccount}
              disabled={submitting}
              className="bg-electric-blue hover:bg-blue-700"
              data-testid="confirm-add-btn"
            >
              {submitting ? "Adding..." : "Add Account"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading font-semibold">
              Remove Email Account
            </AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove {selectedAccount?.email}? This
              action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="cancel-delete-btn">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteAccount}
              className="bg-red-600 hover:bg-red-700"
              data-testid="confirm-delete-btn"
            >
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
