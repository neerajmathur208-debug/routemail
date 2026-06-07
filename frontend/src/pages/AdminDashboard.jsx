import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Users,
  Mail,
  Send,
  BarChart3,
  FileText,
  Activity,
  Search,
  ChevronLeft,
  ChevronRight,
  Eye,
  Trash2,
  Shield,
  ArrowLeft,
  AlertTriangle,
  KeyRound,
  CreditCard,
  X,
  Loader2,
  Crown,
  UserCog,
  Database,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
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
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "../components/ui/dialog";
import { api } from "../App";
import { toast } from "sonner";

export default function AdminDashboard({ user, setUser }) {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [resetLoading, setResetLoading] = useState(false);
  
  // Subscription modal state
  const [subscriptionModalOpen, setSubscriptionModalOpen] = useState(false);
  const [subscriptionData, setSubscriptionData] = useState(null);
  const [subscriptionLoading, setSubscriptionLoading] = useState(false);
  
  // Plan override state
  const [overrideModalOpen, setOverrideModalOpen] = useState(false);
  const [overrideLoading, setOverrideLoading] = useState(false);
  const [removeOverrideDialogOpen, setRemoveOverrideDialogOpen] = useState(false);

  // Role change confirmation dialog state
  const [roleDialogOpen, setRoleDialogOpen] = useState(false);
  const [roleTargetUser, setRoleTargetUser] = useState(null);
  const [roleTargetNew, setRoleTargetNew] = useState(null);
  const [roleLoading, setRoleLoading] = useState(false);

  const fetchStats = useCallback(async () => {
    try {
      const response = await api.get("/admin/stats");
      setStats(response.data);
    } catch (error) {
      if (error.response?.status === 403) {
        toast.error("Access denied. Super admin required.");
        navigate("/dashboard");
      } else {
        toast.error("Failed to load admin stats");
      }
    }
  }, [navigate]);

  const fetchUsers = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      params.append("page", page.toString());
      params.append("limit", "15");
      if (search) params.append("search", search);
      if (statusFilter && statusFilter !== "all") params.append("status", statusFilter);

      const response = await api.get(`/admin/users?${params.toString()}`);
      setUsers(response.data.users);
      setTotalPages(response.data.total_pages);
    } catch (error) {
      if (error.response?.status === 403) {
        toast.error("Access denied. Super admin required.");
        navigate("/dashboard");
      } else {
        toast.error("Failed to load users");
      }
    }
  }, [page, search, statusFilter, navigate]);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchStats(), fetchUsers()]);
      setLoading(false);
    };
    loadData();
  }, [fetchStats, fetchUsers]);

  const handleDeleteClick = (user) => {
    setSelectedUser(user);
    setDeleteDialogOpen(true);
  };

  const handleDeleteUser = async () => {
    if (!selectedUser) return;
    try {
      await api.delete(`/admin/users/${selectedUser.user_id}`);
      toast.success("User deleted successfully");
      setDeleteDialogOpen(false);
      setSelectedUser(null);
      fetchUsers();
      fetchStats();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to delete user");
    }
  };

  const handleResetClick = (u) => {
    setSelectedUser(u);
    setResetDialogOpen(true);
  };

  const handleForcePasswordReset = async () => {
    if (!selectedUser) return;
    setResetLoading(true);
    try {
      await api.post(`/admin/users/${selectedUser.user_id}/force-password-reset`);
      toast.success(`Password reset email sent to ${selectedUser.email}`);
      setResetDialogOpen(false);
      setSelectedUser(null);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to send password reset");
    } finally {
      setResetLoading(false);
    }
  };

  const handleRoleChangeRequest = (u, newRole) => {
    setRoleTargetUser(u);
    setRoleTargetNew(newRole);
    setRoleDialogOpen(true);
  };

  const handleRoleChangeConfirm = async () => {
    if (!roleTargetUser || !roleTargetNew) return;
    setRoleLoading(true);
    try {
      await api.put(`/admin/users/${roleTargetUser.user_id}/role`, { role: roleTargetNew });
      toast.success(
        roleTargetNew === "super_admin"
          ? `Granted Super Admin access to ${roleTargetUser.email}`
          : `Removed Super Admin access from ${roleTargetUser.email}`
      );
      setRoleDialogOpen(false);
      setRoleTargetUser(null);
      setRoleTargetNew(null);
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to update role");
    } finally {
      setRoleLoading(false);
    }
  };

  const handleViewSubscription = async (u) => {
    setSelectedUser(u);
    setSubscriptionModalOpen(true);
    setSubscriptionLoading(true);
    setSubscriptionData(null);
    
    try {
      const response = await api.get(`/admin/users/${u.user_id}/subscription`);
      setSubscriptionData(response.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to load subscription details");
      setSubscriptionModalOpen(false);
    } finally {
      setSubscriptionLoading(false);
    }
  };

  const formatDateTime = (dateStr) => {
    if (!dateStr) return "N/A";
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const getBillingStatusColor = (status) => {
    switch (status) {
      case "active":
      case "permanent":
        return "bg-emerald-100 text-emerald-700";
      case "admin_override":
        return "bg-violet-100 text-violet-700";
      case "trialing":
        return "bg-blue-100 text-blue-700";
      case "past_due":
        return "bg-amber-100 text-amber-700";
      case "canceled":
      case "incomplete":
      case "unpaid":
        return "bg-red-100 text-red-700";
      default:
        return "bg-slate-100 text-slate-600";
    }
  };

  // Plan Override Functions
  const handleOpenOverrideModal = async (u) => {
    setSelectedUser(u);
    // Fetch subscription data to check if user has Stripe subscription
    setSubscriptionLoading(true);
    try {
      const response = await api.get(`/admin/users/${u.user_id}/subscription`);
      setSubscriptionData(response.data);
      setOverrideModalOpen(true);
    } catch (error) {
      toast.error("Failed to load user subscription data");
    } finally {
      setSubscriptionLoading(false);
    }
  };

  const handleAssignPlan = async (plan) => {
    if (!selectedUser) return;
    
    setOverrideLoading(true);
    try {
      await api.post(`/admin/users/${selectedUser.user_id}/assign-plan`, { plan });
      toast.success(`Successfully assigned ${plan.charAt(0).toUpperCase() + plan.slice(1)} plan`);
      setOverrideModalOpen(false);
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to assign plan");
    } finally {
      setOverrideLoading(false);
    }
  };

  const handleRemoveOverride = async () => {
    if (!selectedUser) return;
    
    setOverrideLoading(true);
    try {
      await api.post(`/admin/users/${selectedUser.user_id}/remove-override`);
      toast.success("Admin override removed. User reverted to Free plan.");
      setRemoveOverrideDialogOpen(false);
      setOverrideModalOpen(false);
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to remove override");
    } finally {
      setOverrideLoading(false);
    }
  };

  const handleSetLimitOverride = async ({ max_accounts, max_contacts }) => {
    if (!selectedUser) return;
    setOverrideLoading(true);
    try {
      const res = await api.post(
        `/admin/users/${selectedUser.user_id}/limit-override`,
        { max_accounts, max_contacts }
      );
      toast.success(
        `Limits updated — accounts: ${res.data?.effective_limits?.max_accounts}, contacts: ${res.data?.effective_limits?.max_contacts}`
      );
      // Re-load the dialog state with updated values
      const refresh = await api.get(`/admin/users/${selectedUser.user_id}/subscription`);
      setSubscriptionData(refresh.data);
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to update limits");
    } finally {
      setOverrideLoading(false);
    }
  };

  const getPlanSourceBadge = (source) => {
    switch (source) {
      case "stripe":
        return <Badge className="bg-blue-100 text-blue-700">Stripe</Badge>;
      case "admin_override":
        return <Badge className="bg-violet-100 text-violet-700">Admin Override</Badge>;
      case "permanent":
        return <Badge className="bg-amber-100 text-amber-700">Permanent</Badge>;
      default:
        return <Badge className="bg-slate-100 text-slate-600">Free</Badge>;
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  // Stat Card Component
  const StatCard = ({ icon: Icon, label, value, color, bgColor }) => (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white rounded-2xl p-5 shadow-sm border border-slate-100"
    >
      <div className="flex items-center gap-4">
        <div className={`w-12 h-12 ${bgColor} rounded-xl flex items-center justify-center`}>
          <Icon size={22} className={color} />
        </div>
        <div>
          <p className="text-sm text-slate-500">{label}</p>
          <p className="text-2xl font-bold text-slate-900">{value?.toLocaleString() || 0}</p>
        </div>
      </div>
    </motion.div>
  );

  if (loading) {
    return (
      <div className="min-h-screen bg-[#faf9f7] flex items-center justify-center">
        <div className="w-10 h-10 border-3 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#faf9f7]">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div className="max-w-[1400px] mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate("/dashboard")}
              data-testid="back-to-dashboard"
            >
              <ArrowLeft size={20} />
            </Button>
            <div className="flex items-center gap-2">
              <Shield size={24} className="text-violet-600" />
              <span className="font-heading font-extrabold text-xl text-slate-900">
                Super Admin
              </span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate("/admin/system-backup")}
              data-testid="admin-nav-system-backup-btn"
            >
              <Database size={14} className="mr-1.5" /> System Backup
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => navigate("/admin/blogs")}
              data-testid="admin-nav-blogs-btn"
            >
              Manage Blogs
            </Button>
            <Badge className="bg-violet-100 text-violet-700">
              {user?.email}
            </Badge>
          </div>
        </div>
      </header>

      <main className="max-w-[1400px] mx-auto px-6 py-8">
        {/* Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard
            icon={Users}
            label="Total Users"
            value={stats?.total_users}
            color="text-blue-600"
            bgColor="bg-blue-50"
          />
          <StatCard
            icon={Activity}
            label="Active (7d)"
            value={stats?.active_users}
            color="text-emerald-600"
            bgColor="bg-emerald-50"
          />
          <StatCard
            icon={BarChart3}
            label="Total Campaigns"
            value={stats?.total_campaigns}
            color="text-violet-600"
            bgColor="bg-violet-50"
          />
          <StatCard
            icon={Send}
            label="Emails Sent"
            value={stats?.total_emails_sent}
            color="text-amber-600"
            bgColor="bg-amber-50"
          />
        </div>

        {/* Secondary Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard
            icon={Mail}
            label="Connected Accounts"
            value={stats?.total_accounts}
            color="text-rose-600"
            bgColor="bg-rose-50"
          />
          <StatCard
            icon={FileText}
            label="Email Lists"
            value={stats?.total_lists}
            color="text-cyan-600"
            bgColor="bg-cyan-50"
          />
          <StatCard
            icon={Activity}
            label="Running Campaigns"
            value={stats?.running_campaigns}
            color="text-green-600"
            bgColor="bg-green-50"
          />
          <StatCard
            icon={AlertTriangle}
            label="Failed Emails"
            value={stats?.failed_emails}
            color="text-red-600"
            bgColor="bg-red-50"
          />
        </div>

        {/* Users Table */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
          <div className="p-5 border-b border-slate-100">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <h2 className="font-heading font-semibold text-lg text-slate-900">
                Users Management
              </h2>
              <div className="flex items-center gap-3 w-full sm:w-auto">
                <div className="relative flex-1 sm:flex-none">
                  <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <Input
                    placeholder="Search users..."
                    value={search}
                    onChange={(e) => {
                      setSearch(e.target.value);
                      setPage(1);
                    }}
                    className="pl-9 w-full sm:w-64"
                    data-testid="search-users"
                  />
                </div>
                <Select
                  value={statusFilter}
                  onValueChange={(value) => {
                    setStatusFilter(value);
                    setPage(1);
                  }}
                >
                  <SelectTrigger className="w-36" data-testid="filter-status">
                    <SelectValue placeholder="Status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Status</SelectItem>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>User</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-center">Accounts</TableHead>
                <TableHead className="text-center">Campaigns</TableHead>
                <TableHead className="text-center">Emails Sent</TableHead>
                <TableHead>Registered</TableHead>
                <TableHead>Last Login</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((u, index) => (
                <motion.tr
                  key={u.user_id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ delay: index * 0.02 }}
                  className="border-b border-slate-50"
                >
                  <TableCell>
                    <div>
                      <p className="font-medium text-slate-900">{u.name || "No Name"}</p>
                      <p className="text-sm text-slate-500">{u.email}</p>
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Badge
                        data-testid={`role-badge-${u.user_id}`}
                        className={
                          u.role === "super_admin"
                            ? "bg-violet-100 text-violet-700 border border-violet-200 hover:bg-violet-100"
                            : "bg-slate-100 text-slate-700 border border-slate-200 hover:bg-slate-100"
                        }
                      >
                        {u.role === "super_admin" ? (
                          <span className="flex items-center gap-1">
                            <Crown size={12} /> Super Admin
                          </span>
                        ) : (
                          "User"
                        )}
                      </Badge>
                      {u.role === "super_admin" ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 px-2 text-xs text-red-600 hover:text-red-700 hover:bg-red-50"
                          onClick={() => handleRoleChangeRequest(u, "user")}
                          data-testid={`revoke-superadmin-${u.user_id}`}
                          title="Remove Super Admin access"
                        >
                          Revoke
                        </Button>
                      ) : (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 px-2 text-xs text-violet-600 hover:text-violet-700 hover:bg-violet-50"
                          onClick={() => handleRoleChangeRequest(u, "super_admin")}
                          data-testid={`grant-superadmin-${u.user_id}`}
                          title="Grant Super Admin access"
                        >
                          Grant
                        </Button>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge
                      className={
                        u.subscription_status === "active"
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-slate-100 text-slate-600"
                      }
                    >
                      {u.subscription_status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-center font-medium">{u.accounts_count}</TableCell>
                  <TableCell className="text-center font-medium">{u.campaigns_count}</TableCell>
                  <TableCell className="text-center font-medium">{u.emails_sent}</TableCell>
                  <TableCell className="text-slate-500 text-sm">{formatDate(u.created_at)}</TableCell>
                  <TableCell className="text-slate-500 text-sm">{formatDate(u.last_login)}</TableCell>
                  <TableCell>
                    <div className="flex items-center justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => handleOpenOverrideModal(u)}
                        data-testid={`plan-override-${u.user_id}`}
                        title="Manage Plan Override"
                      >
                        <UserCog size={16} className="text-slate-400 hover:text-violet-500" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => handleViewSubscription(u)}
                        data-testid={`view-subscription-${u.user_id}`}
                        title="View Subscription Details"
                      >
                        <CreditCard size={16} className="text-slate-400 hover:text-violet-500" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => navigate(`/admin/users/${u.user_id}`)}
                        data-testid={`view-user-${u.user_id}`}
                        title="View Details"
                      >
                        <Eye size={16} className="text-slate-400" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => handleResetClick(u)}
                        data-testid={`reset-password-${u.user_id}`}
                        title="Force Password Reset"
                      >
                        <KeyRound size={16} className="text-slate-400 hover:text-amber-500" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => handleDeleteClick(u)}
                        disabled={u.role === "super_admin"}
                        data-testid={`delete-user-${u.user_id}`}
                        title="Delete User"
                      >
                        <Trash2 size={16} className="text-slate-400 hover:text-red-500" />
                      </Button>
                    </div>
                  </TableCell>
                </motion.tr>
              ))}
              {users.length === 0 && (
                <TableRow>
                  <TableCell colSpan={9} className="text-center py-8 text-slate-500">
                    No users found
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="p-4 border-t border-slate-100 flex items-center justify-between">
              <p className="text-sm text-slate-500">Page {page} of {totalPages}</p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  <ChevronLeft size={16} />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                >
                  <ChevronRight size={16} />
                </Button>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Delete Confirmation */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading font-semibold">
              Delete User
            </AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{selectedUser?.email}"? This will permanently remove
              all their accounts, campaigns, lists, and data. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="cancel-delete">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteUser}
              className="bg-red-600 hover:bg-red-700"
              data-testid="confirm-delete"
            >
              Delete User
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Role Change Confirmation */}
      <AlertDialog open={roleDialogOpen} onOpenChange={setRoleDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading font-semibold flex items-center gap-2">
              <Crown size={20} className={roleTargetNew === "super_admin" ? "text-violet-500" : "text-slate-400"} />
              {roleTargetNew === "super_admin" ? "Grant Super Admin Access" : "Remove Super Admin Access"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {roleTargetNew === "super_admin" ? (
                <>
                  Are you sure you want to grant <span className="font-semibold">Super Admin</span> access
                  to <span className="font-semibold">{roleTargetUser?.email}</span>? They will gain full
                  control over the platform — including managing users, billing overrides, and other Super Admins.
                </>
              ) : (
                <>
                  Are you sure you want to remove <span className="font-semibold">Super Admin</span> access
                  from <span className="font-semibold">{roleTargetUser?.email}</span>? They will lose access
                  to the admin panel and all super-admin actions.
                  {roleTargetUser?.email === user?.email && (
                    <span className="block mt-2 text-amber-600 font-medium">
                      Warning: You are revoking your own Super Admin access. You will be logged out of admin features immediately after this action.
                    </span>
                  )}
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="cancel-role-change" disabled={roleLoading}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleRoleChangeConfirm}
              disabled={roleLoading}
              className={
                roleTargetNew === "super_admin"
                  ? "bg-violet-600 hover:bg-violet-700"
                  : "bg-red-600 hover:bg-red-700"
              }
              data-testid="confirm-role-change"
            >
              {roleLoading ? (
                <span className="flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> Saving...</span>
              ) : roleTargetNew === "super_admin" ? (
                "Grant Super Admin"
              ) : (
                "Remove Super Admin"
              )}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Force Password Reset Confirmation */}
      <AlertDialog open={resetDialogOpen} onOpenChange={setResetDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading font-semibold flex items-center gap-2">
              <KeyRound size={20} className="text-amber-500" />
              Force Password Reset
            </AlertDialogTitle>
            <AlertDialogDescription>
              This will send a password reset email to <strong>{selectedUser?.email}</strong>.
              The user will receive a link to set a new password (expires in 1 hour).
              <br /><br />
              <span className="text-slate-600">Note: This does not reveal or change their current password.</span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="cancel-reset" disabled={resetLoading}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleForcePasswordReset}
              className="bg-amber-600 hover:bg-amber-700"
              data-testid="confirm-reset"
              disabled={resetLoading}
            >
              {resetLoading ? "Sending..." : "Send Reset Email"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Subscription Details Modal */}
      <Dialog open={subscriptionModalOpen} onOpenChange={setSubscriptionModalOpen}>
        <DialogContent className="sm:max-w-[500px]" data-testid="subscription-modal">
          <DialogHeader>
            <DialogTitle className="font-heading font-semibold flex items-center gap-2">
              <CreditCard size={20} className="text-violet-500" />
              Subscription Details
            </DialogTitle>
          </DialogHeader>
          
          {subscriptionLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 size={32} className="text-violet-500 animate-spin" />
            </div>
          ) : subscriptionData ? (
            <div className="space-y-4">
              {/* User Info */}
              <div className="bg-slate-50 rounded-lg p-3">
                <p className="text-sm text-slate-500">User</p>
                <p className="font-medium text-slate-900">{subscriptionData.email}</p>
              </div>

              {/* Subscription Grid */}
              <div className="grid grid-cols-2 gap-3">
                {/* Current Plan */}
                <div className="bg-slate-50 rounded-lg p-3">
                  <p className="text-sm text-slate-500">Current Plan</p>
                  <p className="font-semibold text-slate-900" data-testid="sub-current-plan">
                    {subscriptionData.current_plan}
                  </p>
                </div>

                {/* Currency */}
                <div className="bg-slate-50 rounded-lg p-3">
                  <p className="text-sm text-slate-500">Currency</p>
                  <p className="font-semibold text-slate-900" data-testid="sub-currency">
                    {subscriptionData.currency}
                  </p>
                </div>

                {/* Billing Status */}
                <div className="bg-slate-50 rounded-lg p-3 col-span-2">
                  <p className="text-sm text-slate-500 mb-1">Billing Status</p>
                  <Badge 
                    className={getBillingStatusColor(subscriptionData.billing_status)}
                    data-testid="sub-billing-status"
                  >
                    {subscriptionData.billing_status}
                  </Badge>
                  {subscriptionData.is_permanent_plan && (
                    <span className="ml-2 text-xs text-violet-600">(Permanent Assignment)</span>
                  )}
                </div>

                {/* Plan Source */}
                <div className="bg-slate-50 rounded-lg p-3">
                  <p className="text-sm text-slate-500">Plan Source</p>
                  <p className="font-semibold text-slate-900" data-testid="sub-plan-source">
                    {subscriptionData.plan_source || "free"}
                  </p>
                </div>

                {/* Downgraded From */}
                <div className="bg-slate-50 rounded-lg p-3">
                  <p className="text-sm text-slate-500">Downgraded From</p>
                  <p className="font-medium text-slate-900 text-sm" data-testid="sub-downgraded-from">
                    {subscriptionData.downgraded_to_free_at
                      ? `${subscriptionData.downgrade_reason || "expired"} · ${formatDateTime(subscriptionData.downgraded_to_free_at)}`
                      : "—"}
                  </p>
                </div>

                {/* Subscription End Date */}
                <div className="bg-slate-50 rounded-lg p-3 col-span-2">
                  <p className="text-sm text-slate-500">Subscription End Date</p>
                  <p className="font-medium text-slate-900" data-testid="sub-end-date">
                    {subscriptionData.subscription_end_date 
                      ? formatDateTime(subscriptionData.subscription_end_date) 
                      : "N/A"}
                  </p>
                </div>
              </div>

              {/* Stripe IDs Section */}
              <div className="border-t border-slate-200 pt-4 mt-4">
                <h4 className="font-medium text-slate-700 mb-3 text-sm">Stripe Information</h4>
                <div className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-500">Customer ID</span>
                    <code className="bg-slate-100 px-2 py-0.5 rounded text-xs font-mono text-slate-700" data-testid="sub-stripe-customer">
                      {subscriptionData.stripe_customer_id}
                    </code>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-500">Subscription ID</span>
                    <code className="bg-slate-100 px-2 py-0.5 rounded text-xs font-mono text-slate-700" data-testid="sub-stripe-subscription">
                      {subscriptionData.stripe_subscription_id}
                    </code>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-slate-500">Price ID</span>
                    <code className="bg-slate-100 px-2 py-0.5 rounded text-xs font-mono text-slate-700" data-testid="sub-stripe-price">
                      {subscriptionData.stripe_price_id}
                    </code>
                  </div>
                </div>
              </div>

              {/* Notes if any */}
              {subscriptionData.notes && (
                <div className="bg-violet-50 border border-violet-200 rounded-lg p-3">
                  <p className="text-sm text-violet-700">{subscriptionData.notes}</p>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-8 text-slate-500">
              Failed to load subscription details
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Plan Override Modal */}
      <Dialog open={overrideModalOpen} onOpenChange={setOverrideModalOpen}>
        <DialogContent className="sm:max-w-[500px]" data-testid="plan-override-modal">
          <DialogHeader>
            <DialogTitle className="font-heading font-semibold flex items-center gap-2">
              <UserCog size={20} className="text-violet-500" />
              Manage Plan Override
            </DialogTitle>
            <DialogDescription>
              Assign or remove plan access for <strong>{selectedUser?.email}</strong>
            </DialogDescription>
          </DialogHeader>
          
          {subscriptionLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 size={32} className="text-violet-500 animate-spin" />
            </div>
          ) : subscriptionData ? (
            <div className="space-y-4">
              {/* Current Status */}
              <div className="bg-slate-50 rounded-lg p-4">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-slate-500">Current Plan</p>
                    <p className="font-semibold text-slate-900">{subscriptionData.current_plan}</p>
                  </div>
                  <div>
                    <p className="text-sm text-slate-500">Plan Source</p>
                    {getPlanSourceBadge(subscriptionData.plan_source)}
                  </div>
                </div>
              </div>

              {/* Admin Override Badge if active */}
              {subscriptionData.admin_override_active && (
                <div className="bg-violet-50 border border-violet-200 rounded-lg p-3">
                  <div className="flex items-center gap-2">
                    <Crown size={16} className="text-violet-600" />
                    <span className="font-medium text-violet-700">Admin Override Active</span>
                  </div>
                  <p className="text-sm text-violet-600 mt-1">
                    Override plan: {subscriptionData.admin_override_plan?.charAt(0).toUpperCase() + subscriptionData.admin_override_plan?.slice(1)}
                  </p>
                  {subscriptionData.admin_override_updated_at && (
                    <p className="text-xs text-violet-500 mt-1">
                      Assigned: {formatDateTime(subscriptionData.admin_override_updated_at)}
                    </p>
                  )}
                </div>
              )}

              {/* Check if user has Stripe subscription */}
              {subscriptionData.has_stripe_subscription ? (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <AlertTriangle size={20} className="text-amber-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium text-amber-800">Stripe Subscription Active</p>
                      <p className="text-sm text-amber-700 mt-1">
                        This user has an active Stripe subscription. Plan changes must be handled through Stripe billing.
                      </p>
                    </div>
                  </div>
                </div>
              ) : subscriptionData.is_permanent_plan ? (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                  <div className="flex items-start gap-3">
                    <AlertTriangle size={20} className="text-amber-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium text-amber-800">Permanent Plan User</p>
                      <p className="text-sm text-amber-700 mt-1">
                        This user has a permanently assigned plan that cannot be overridden.
                      </p>
                    </div>
                  </div>
                </div>
              ) : (
                <>
                  {/* Plan Assignment Buttons */}
                  <div className="space-y-3">
                    <p className="text-sm font-medium text-slate-700">Assign Plan:</p>
                    <div className="grid grid-cols-2 gap-3">
                      <Button
                        onClick={() => handleAssignPlan("starter")}
                        disabled={overrideLoading || subscriptionData.admin_override_plan === "starter"}
                        className="bg-blue-600 hover:bg-blue-700"
                        data-testid="assign-starter-btn"
                      >
                        {overrideLoading ? (
                          <Loader2 size={16} className="animate-spin mr-2" />
                        ) : (
                          <Crown size={16} className="mr-2" />
                        )}
                        Assign Starter
                      </Button>
                      <Button
                        onClick={() => handleAssignPlan("growth")}
                        disabled={overrideLoading || subscriptionData.admin_override_plan === "growth"}
                        className="bg-violet-600 hover:bg-violet-700"
                        data-testid="assign-growth-btn"
                      >
                        {overrideLoading ? (
                          <Loader2 size={16} className="animate-spin mr-2" />
                        ) : (
                          <Crown size={16} className="mr-2" />
                        )}
                        Assign Growth
                      </Button>
                    </div>
                  </div>

                  {/* Manual Limit Overrides — independent of plan selection */}
                  <div className="pt-4 border-t border-slate-200" data-testid="manual-limit-overrides">
                    <p className="text-sm font-medium text-slate-700 mb-2">
                      Manual Limit Overrides
                    </p>
                    <p className="text-xs text-slate-500 mb-3">
                      Apply per-user caps that take priority over the plan. Leave blank to clear.
                      Does NOT change Stripe billing.
                    </p>
                    <ManualLimitOverrideForm
                      defaultMaxAccounts={subscriptionData.admin_override_max_accounts}
                      defaultMaxContacts={subscriptionData.admin_override_max_contacts}
                      saving={overrideLoading}
                      onSave={handleSetLimitOverride}
                    />
                  </div>

                  {/* Remove Override Button (if override is active) */}
                  {subscriptionData.admin_override_active && (
                    <div className="pt-4 border-t border-slate-200">
                      <Button
                        variant="outline"
                        onClick={() => setRemoveOverrideDialogOpen(true)}
                        disabled={overrideLoading}
                        className="w-full text-red-600 border-red-200 hover:bg-red-50"
                        data-testid="remove-override-btn"
                      >
                        <Trash2 size={16} className="mr-2" />
                        Remove Admin Override
                      </Button>
                      <p className="text-xs text-slate-500 mt-2 text-center">
                        User will be reverted to Free plan
                      </p>
                    </div>
                  )}
                </>
              )}
            </div>
          ) : (
            <div className="text-center py-8 text-slate-500">
              Failed to load user data
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Remove Override Confirmation Dialog */}
      <AlertDialog open={removeOverrideDialogOpen} onOpenChange={setRemoveOverrideDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading font-semibold flex items-center gap-2">
              <AlertTriangle size={20} className="text-red-500" />
              Remove Admin Override
            </AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to remove the admin override for <strong>{selectedUser?.email}</strong>?
              <br /><br />
              The user will be reverted to the <strong>Free plan</strong> and will lose access to premium features.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="cancel-remove-override" disabled={overrideLoading}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleRemoveOverride}
              className="bg-red-600 hover:bg-red-700"
              data-testid="confirm-remove-override"
              disabled={overrideLoading}
            >
              {overrideLoading ? "Removing..." : "Remove Override"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function ManualLimitOverrideForm({ defaultMaxAccounts, defaultMaxContacts, saving, onSave }) {
  const [accountsVal, setAccountsVal] = useState(
    defaultMaxAccounts !== null && defaultMaxAccounts !== undefined ? String(defaultMaxAccounts) : ""
  );
  const [contactsVal, setContactsVal] = useState(
    defaultMaxContacts !== null && defaultMaxContacts !== undefined ? String(defaultMaxContacts) : ""
  );

  useEffect(() => {
    setAccountsVal(
      defaultMaxAccounts !== null && defaultMaxAccounts !== undefined
        ? String(defaultMaxAccounts)
        : ""
    );
    setContactsVal(
      defaultMaxContacts !== null && defaultMaxContacts !== undefined
        ? String(defaultMaxContacts)
        : ""
    );
  }, [defaultMaxAccounts, defaultMaxContacts]);

  const submit = () => {
    const max_accounts = accountsVal === "" ? null : Math.max(0, parseInt(accountsVal, 10) || 0);
    const max_contacts = contactsVal === "" ? null : Math.max(0, parseInt(contactsVal, 10) || 0);
    onSave({ max_accounts, max_contacts });
  };

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-medium text-slate-600 mb-1 block">
            Max Email Accounts
          </label>
          <input
            type="number"
            min={0}
            value={accountsVal}
            onChange={(e) => setAccountsVal(e.target.value)}
            placeholder="Plan default"
            className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm"
            data-testid="override-max-accounts-input"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-slate-600 mb-1 block">
            Monthly Contact Limit
          </label>
          <input
            type="number"
            min={0}
            value={contactsVal}
            onChange={(e) => setContactsVal(e.target.value)}
            placeholder="Plan default"
            className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm"
            data-testid="override-max-contacts-input"
          />
        </div>
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={submit}
          disabled={saving}
          className="px-3 py-1.5 rounded-md bg-violet-600 hover:bg-violet-700 text-white text-sm disabled:opacity-60"
          data-testid="save-limit-overrides-btn"
        >
          {saving ? "Saving…" : "Save Limit Overrides"}
        </button>
        <button
          type="button"
          onClick={() => {
            setAccountsVal("");
            setContactsVal("");
            onSave({ max_accounts: null, max_contacts: null });
          }}
          disabled={saving}
          className="px-3 py-1.5 rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50 text-sm"
          data-testid="clear-limit-overrides-btn"
        >
          Clear
        </button>
      </div>
    </div>
  );
}

