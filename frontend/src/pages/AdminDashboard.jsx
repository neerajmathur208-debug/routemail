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

  const handleRoleChange = async (userId, newRole) => {
    try {
      await api.put(`/admin/users/${userId}/role`, { role: newRole });
      toast.success(`Role updated to ${newRole}`);
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to update role");
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
                    <Select
                      value={u.role}
                      onValueChange={(value) => handleRoleChange(u.user_id, value)}
                      disabled={u.role === "super_admin" && u.email === user?.email}
                    >
                      <SelectTrigger className="w-28 h-8" data-testid={`role-${u.user_id}`}>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="user">User</SelectItem>
                        <SelectItem value="super_admin">Super Admin</SelectItem>
                      </SelectContent>
                    </Select>
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
    </div>
  );
}
