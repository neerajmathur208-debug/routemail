import { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Mail,
  Send,
  BarChart3,
  FileText,
  User,
  Calendar,
  Shield,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { api } from "../App";
import { toast } from "sonner";

export default function AdminUserDetail({ user: currentUser, setUser }) {
  const navigate = useNavigate();
  const { userId } = useParams();
  const [userData, setUserData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchUserDetail = useCallback(async () => {
    try {
      const response = await api.get(`/admin/users/${userId}`);
      setUserData(response.data);
    } catch (error) {
      if (error.response?.status === 403) {
        toast.error("Access denied. Super admin required.");
        navigate("/dashboard");
      } else if (error.response?.status === 404) {
        toast.error("User not found");
        navigate("/admin");
      } else {
        toast.error("Failed to load user details");
      }
    } finally {
      setLoading(false);
    }
  }, [userId, navigate]);

  useEffect(() => {
    fetchUserDetail();
  }, [fetchUserDetail]);

  const formatDate = (dateStr) => {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleDateString("en-US", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const StatCard = ({ icon: Icon, label, value, color, bgColor }) => (
    <div className="bg-white rounded-xl p-4 shadow-sm border border-slate-100">
      <div className="flex items-center gap-3">
        <div className={`w-10 h-10 ${bgColor} rounded-lg flex items-center justify-center`}>
          <Icon size={18} className={color} />
        </div>
        <div>
          <p className="text-xs text-slate-500">{label}</p>
          <p className="text-xl font-bold text-slate-900">{value}</p>
        </div>
      </div>
    </div>
  );

  if (loading) {
    return (
      <div className="min-h-screen bg-[#faf9f7] flex items-center justify-center">
        <div className="w-10 h-10 border-3 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!userData) return null;

  const { user, accounts, campaigns, lists, stats } = userData;

  return (
    <div className="min-h-screen bg-[#faf9f7]">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div className="max-w-[1200px] mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => navigate("/admin")}
              data-testid="back-to-admin"
            >
              <ArrowLeft size={20} />
            </Button>
            <div className="flex items-center gap-2">
              <Shield size={20} className="text-violet-600" />
              <span className="font-heading font-semibold text-slate-900">
                User Details
              </span>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-[1200px] mx-auto px-6 py-8">
        {/* User Info Card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6 mb-6"
        >
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-violet-500 rounded-2xl flex items-center justify-center">
                <User size={32} className="text-white" />
              </div>
              <div>
                <h1 className="font-heading font-bold text-2xl text-slate-900">
                  {user.name || "No Name"}
                </h1>
                <p className="text-slate-500">{user.email}</p>
                <div className="flex items-center gap-2 mt-2">
                  <Badge
                    className={
                      user.role === "super_admin"
                        ? "bg-violet-100 text-violet-700"
                        : "bg-slate-100 text-slate-600"
                    }
                  >
                    {user.role}
                  </Badge>
                  <Badge
                    className={
                      user.subscription_status === "active"
                        ? "bg-emerald-100 text-emerald-700"
                        : "bg-slate-100 text-slate-600"
                    }
                  >
                    {user.subscription_status}
                  </Badge>
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="flex items-center gap-2 text-slate-500 text-sm">
                <Calendar size={14} />
                <span>Joined {formatDate(user.created_at)}</span>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
          <StatCard
            icon={Mail}
            label="Accounts"
            value={stats.total_accounts}
            color="text-blue-600"
            bgColor="bg-blue-50"
          />
          <StatCard
            icon={BarChart3}
            label="Campaigns"
            value={stats.total_campaigns}
            color="text-violet-600"
            bgColor="bg-violet-50"
          />
          <StatCard
            icon={FileText}
            label="Lists"
            value={stats.total_lists}
            color="text-amber-600"
            bgColor="bg-amber-50"
          />
          <StatCard
            icon={Send}
            label="Sent"
            value={stats.emails_sent}
            color="text-emerald-600"
            bgColor="bg-emerald-50"
          />
          <StatCard
            icon={XCircle}
            label="Failed"
            value={stats.emails_failed}
            color="text-red-600"
            bgColor="bg-red-50"
          />
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          {/* Email Accounts */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden"
          >
            <div className="p-5 border-b border-slate-100">
              <h2 className="font-heading font-semibold text-lg text-slate-900">
                Connected Accounts ({accounts.length})
              </h2>
            </div>
            {accounts.length > 0 ? (
              <div className="divide-y divide-slate-50">
                {accounts.map((account) => (
                  <div key={account.account_id} className="p-4 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={`w-2 h-2 rounded-full ${
                        account.status === "connected" ? "bg-emerald-500" : "bg-red-500"
                      }`} />
                      <div>
                        <p className="font-medium text-slate-800">{account.email}</p>
                        <p className="text-xs text-slate-400">{account.account_type.toUpperCase()}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-medium text-slate-700">
                        {account.daily_send_count || 0} / {account.daily_limit}
                      </p>
                      <p className="text-xs text-slate-400">daily limit</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-8 text-center text-slate-500">
                No accounts connected
              </div>
            )}
          </motion.div>

          {/* Email Lists */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden"
          >
            <div className="p-5 border-b border-slate-100">
              <h2 className="font-heading font-semibold text-lg text-slate-900">
                Email Lists ({lists.length})
              </h2>
            </div>
            {lists.length > 0 ? (
              <div className="divide-y divide-slate-50">
                {lists.slice(0, 10).map((list) => (
                  <div key={list.list_id} className="p-4 flex items-center justify-between">
                    <div>
                      <p className="font-medium text-slate-800">{list.name}</p>
                      <p className="text-xs text-slate-400">{list.original_filename}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-medium text-slate-700">
                        {list.valid_emails || 0} contacts
                      </p>
                      <p className="text-xs text-slate-400">{formatDate(list.created_at)}</p>
                    </div>
                  </div>
                ))}
                {lists.length > 10 && (
                  <div className="p-4 text-center text-sm text-slate-400">
                    +{lists.length - 10} more lists
                  </div>
                )}
              </div>
            ) : (
              <div className="p-8 text-center text-slate-500">
                No lists uploaded
              </div>
            )}
          </motion.div>
        </div>

        {/* Campaigns Table */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="mt-6 bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden"
        >
          <div className="p-5 border-b border-slate-100">
            <h2 className="font-heading font-semibold text-lg text-slate-900">
              Campaigns ({campaigns.length})
            </h2>
          </div>
          {campaigns.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Campaign Name</TableHead>
                  <TableHead>Subject</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-center">Total</TableHead>
                  <TableHead className="text-center">Sent</TableHead>
                  <TableHead className="text-center">Failed</TableHead>
                  <TableHead>Created</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {campaigns.slice(0, 20).map((campaign) => (
                  <TableRow key={campaign.campaign_id}>
                    <TableCell className="font-medium">{campaign.name || "-"}</TableCell>
                    <TableCell className="max-w-[200px] truncate">{campaign.subject}</TableCell>
                    <TableCell>
                      <Badge
                        className={
                          campaign.status === "completed" ? "bg-emerald-100 text-emerald-700" :
                          campaign.status === "running" ? "bg-blue-100 text-blue-700" :
                          campaign.status === "paused" ? "bg-amber-100 text-amber-700" :
                          "bg-slate-100 text-slate-600"
                        }
                      >
                        {campaign.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-center">{campaign.total_emails}</TableCell>
                    <TableCell className="text-center text-emerald-600">{campaign.sent_count}</TableCell>
                    <TableCell className="text-center text-red-500">{campaign.failed_count}</TableCell>
                    <TableCell className="text-slate-500 text-sm">{formatDate(campaign.created_at)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <div className="p-8 text-center text-slate-500">
              No campaigns created
            </div>
          )}
        </motion.div>

        {/* Back Button */}
        <div className="mt-6">
          <Button
            variant="outline"
            onClick={() => navigate("/admin")}
            data-testid="back-to-admin-btn"
          >
            <ArrowLeft size={16} className="mr-2" />
            Back to Admin
          </Button>
        </div>
      </main>
    </div>
  );
}
