import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Mail,
  Users,
  Send,
  BarChart3,
  ArrowRight,
  Play,
  Pause,
  CheckCircle2,
  XCircle,
  Edit,
  Eye,
  TrendingUp,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Progress } from "../components/ui/progress";
import Sidebar from "../components/Sidebar";
import { api } from "../App";
import { toast } from "sonner";

export default function Dashboard({ user, setUser }) {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = async () => {
    try {
      const response = await api.get("/dashboard/stats");
      setStats(response.data);
    } catch (error) {
      console.error("Failed to fetch stats:", error);
      toast.error("Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    const interval = setInterval(() => {
      if (stats?.current_campaign?.status === "running") {
        fetchStats();
      }
    }, 10000);
    return () => clearInterval(interval);
  }, [stats?.current_campaign?.status]);

  const handlePauseCampaign = async (campaignId) => {
    try {
      await api.post(`/campaigns/${campaignId}/pause`);
      toast.success("Campaign paused");
      fetchStats();
    } catch (error) {
      toast.error("Failed to pause campaign");
    }
  };

  const handleResumeCampaign = async (campaignId) => {
    try {
      await api.post(`/campaigns/${campaignId}/resume`);
      toast.success("Campaign resumed");
      fetchStats();
    } catch (error) {
      toast.error("Failed to resume campaign");
    }
  };

  // Modern Stat Card Component
  const StatCard = ({ icon: Icon, label, value, subtext, iconBg, iconColor, delay = 0 }) => (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
      className="bg-white rounded-2xl p-6 shadow-sm hover:shadow-md transition-all duration-200 border border-slate-100"
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-slate-500 text-sm font-medium mb-1">{label}</p>
          <p className="font-heading font-extrabold text-3xl text-slate-900">{value}</p>
          {subtext && (
            <p className="text-sm text-slate-400 mt-1.5 flex items-center gap-1">
              <TrendingUp size={12} className="text-emerald-500" />
              {subtext}
            </p>
          )}
        </div>
        <div className={`w-12 h-12 ${iconBg} rounded-xl flex items-center justify-center`}>
          <Icon size={22} className={iconColor} strokeWidth={1.5} />
        </div>
      </div>
    </motion.div>
  );

  // Modern Account Usage Card
  const AccountUsageCard = ({ account, index }) => {
    const percentage = Math.round((account.daily_sent / account.daily_limit) * 100);
    
    return (
      <motion.div
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ delay: index * 0.05 }}
        className="group flex items-center gap-4 p-4 rounded-xl bg-slate-50/50 hover:bg-slate-50 transition-colors duration-200"
      >
        <div className="flex-shrink-0">
          <div className={`w-2.5 h-2.5 rounded-full ${account.status === "connected" ? "bg-emerald-500" : "bg-red-500"}`} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-sm text-slate-800 truncate">{account.email}</p>
          <div className="mt-2 flex items-center gap-3">
            <div className="flex-1 h-2 bg-slate-200 rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${percentage}%` }}
                transition={{ duration: 0.8, delay: index * 0.1 }}
                className="h-full bg-gradient-to-r from-blue-500 to-blue-600 rounded-full"
              />
            </div>
            <span className="text-xs font-medium text-slate-500 whitespace-nowrap min-w-[80px] text-right">
              {account.daily_sent}/{account.daily_limit} · {percentage}%
            </span>
          </div>
        </div>
      </motion.div>
    );
  };

  if (loading) {
    return (
      <div className="flex min-h-screen bg-slate-50">
        <Sidebar user={user} setUser={setUser} />
        <main className="flex-1 p-8">
          <div className="animate-pulse flex items-center justify-center h-64">
            <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
          </div>
        </main>
      </div>
    );
  }

  const needsAccounts = stats?.total_accounts === 0;
  const needsList = stats?.total_lists === 0;

  return (
    <div className="flex min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
      <Sidebar user={user} setUser={setUser} />
      
      <main className="flex-1 p-6 lg:p-8 overflow-y-auto">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <motion.div 
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-8"
          >
            <h1 className="font-heading font-extrabold text-2xl sm:text-3xl text-slate-900">
              Dashboard
            </h1>
            <p className="text-slate-500 mt-1">Welcome back! Here's your email campaign overview.</p>
          </motion.div>

          {/* Stats Grid */}
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-5 mb-8">
            <StatCard
              icon={Mail}
              label="Email Accounts"
              value={stats?.total_accounts || 0}
              subtext={`${stats?.total_available_today || 0} sends available`}
              iconBg="bg-blue-50"
              iconColor="text-blue-600"
              delay={0}
            />
            <StatCard
              icon={Users}
              label="Total Contacts"
              value={stats?.total_contacts || 0}
              subtext={`${stats?.total_lists || 0} lists`}
              iconBg="bg-emerald-50"
              iconColor="text-emerald-600"
              delay={0.1}
            />
            <StatCard
              icon={Send}
              label="Emails Sent"
              value={stats?.total_sent || 0}
              subtext={stats?.total_failed > 0 ? `${stats.total_failed} failed` : "All delivered"}
              iconBg="bg-violet-50"
              iconColor="text-violet-600"
              delay={0.2}
            />
            <StatCard
              icon={BarChart3}
              label="Campaigns"
              value={stats?.total_campaigns || 0}
              subtext="Total created"
              iconBg="bg-amber-50"
              iconColor="text-amber-600"
              delay={0.3}
            />
          </div>

          {/* Current Campaign */}
          {stats?.current_campaign && (stats.current_campaign.status === "running" || stats.current_campaign.status === "paused") && (
            <motion.div
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              className="mb-8 bg-white rounded-2xl p-6 shadow-sm border border-slate-100"
            >
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-3">
                  <div className={`w-3 h-3 rounded-full ${
                    stats.current_campaign.status === "running" 
                      ? "bg-emerald-500 animate-pulse" 
                      : "bg-amber-500"
                  }`} />
                  <h2 className="font-heading font-semibold text-lg text-slate-900">
                    {stats.current_campaign.name || "Active Campaign"}
                  </h2>
                  <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${
                    stats.current_campaign.status === "running"
                      ? "bg-emerald-100 text-emerald-700"
                      : "bg-amber-100 text-amber-700"
                  }`}>
                    {stats.current_campaign.status}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {stats.current_campaign.status === "running" ? (
                    <Button
                      variant="outline"
                      size="sm"
                      className="rounded-lg"
                      onClick={() => handlePauseCampaign(stats.current_campaign.campaign_id)}
                    >
                      <Pause size={14} className="mr-1.5" />
                      Pause
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      className="bg-blue-600 hover:bg-blue-700 rounded-lg"
                      onClick={() => handleResumeCampaign(stats.current_campaign.campaign_id)}
                    >
                      <Play size={14} className="mr-1.5" />
                      Resume
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    className="rounded-lg"
                    onClick={() => navigate("/campaign")}
                    data-testid="view-campaign-btn"
                  >
                    Details
                    <ArrowRight size={14} className="ml-1.5" />
                  </Button>
                </div>
              </div>

              <div className="space-y-4">
                <div className="p-3 bg-slate-50 rounded-xl">
                  <p className="text-xs text-slate-500 mb-1">Subject Line</p>
                  <p className="text-slate-800 font-medium">{stats.current_campaign.subject}</p>
                </div>

                <div>
                  <div className="flex justify-between text-sm mb-2">
                    <span className="text-slate-500">Progress</span>
                    <span className="text-slate-800 font-semibold">
                      {stats.current_campaign.sent_count} / {stats.current_campaign.total_emails}
                    </span>
                  </div>
                  <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${(stats.current_campaign.sent_count / stats.current_campaign.total_emails) * 100}%` }}
                      transition={{ duration: 1 }}
                      className="h-full bg-gradient-to-r from-blue-500 to-blue-600 rounded-full"
                    />
                  </div>
                </div>

                <div className="flex gap-6 pt-2">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 bg-emerald-50 rounded-lg flex items-center justify-center">
                      <CheckCircle2 size={16} className="text-emerald-600" />
                    </div>
                    <div>
                      <p className="text-lg font-semibold text-slate-800">{stats.current_campaign.sent_count}</p>
                      <p className="text-xs text-slate-500">Sent</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 bg-red-50 rounded-lg flex items-center justify-center">
                      <XCircle size={16} className="text-red-500" />
                    </div>
                    <div>
                      <p className="text-lg font-semibold text-slate-800">{stats.current_campaign.failed_count}</p>
                      <p className="text-xs text-slate-500">Failed</p>
                    </div>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* All Campaigns Section */}
          {stats?.campaigns && stats.campaigns.length > 0 && (
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="mb-8 bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden"
            >
              <div className="p-5 border-b border-slate-100 flex items-center justify-between">
                <h2 className="font-heading font-semibold text-lg text-slate-900">
                  Recent Campaigns
                </h2>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-slate-600 hover:text-slate-900"
                  onClick={() => navigate("/campaign")}
                >
                  View All
                  <ArrowRight size={14} className="ml-1.5" />
                </Button>
              </div>
              <div className="divide-y divide-slate-100">
                {stats.campaigns.slice(0, 5).map((campaign, index) => (
                  <motion.div 
                    key={campaign.campaign_id} 
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: index * 0.05 }}
                    className="p-4 hover:bg-slate-50/50 transition-colors duration-150"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3">
                          <p className="font-medium text-slate-800 truncate">
                            {campaign.name || campaign.subject}
                          </p>
                          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                            campaign.status === "completed" ? "bg-emerald-100 text-emerald-700" :
                            campaign.status === "running" ? "bg-blue-100 text-blue-700" :
                            campaign.status === "paused" ? "bg-amber-100 text-amber-700" :
                            "bg-slate-100 text-slate-600"
                          }`}>
                            {campaign.status}
                          </span>
                        </div>
                        <div className="flex items-center gap-4 mt-1.5 text-sm text-slate-500">
                          <span>{campaign.total_emails} recipients</span>
                          {campaign.status !== "draft" && (
                            <span className="text-emerald-600">{campaign.sent_count} sent</span>
                          )}
                        </div>
                        {campaign.status !== "draft" && campaign.total_emails > 0 && (
                          <div className="mt-2 h-1.5 bg-slate-100 rounded-full overflow-hidden max-w-xs">
                            <div 
                              className="h-full bg-gradient-to-r from-blue-400 to-blue-500 rounded-full"
                              style={{ width: `${(campaign.sent_count / campaign.total_emails) * 100}%` }}
                            />
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-1 ml-4">
                        {campaign.status === "draft" && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 rounded-lg"
                            onClick={() => navigate(`/campaign?edit=${campaign.campaign_id}`)}
                          >
                            <Edit size={15} className="text-slate-400" />
                          </Button>
                        )}
                        {campaign.status === "paused" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="rounded-lg text-blue-600 hover:text-blue-700 hover:bg-blue-50"
                            onClick={() => handleResumeCampaign(campaign.campaign_id)}
                          >
                            <Play size={14} className="mr-1" />
                            Resume
                          </Button>
                        )}
                        {(campaign.status === "completed" || campaign.status === "running" || campaign.status === "paused") && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="rounded-lg text-slate-600 hover:text-slate-800"
                            onClick={() => navigate(`/campaign/${campaign.campaign_id}/logs`)}
                            data-testid={`view-logs-${campaign.campaign_id}`}
                          >
                            <Eye size={14} className="mr-1" />
                            Logs
                          </Button>
                        )}
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          )}

          {/* Bottom Section */}
          <div className="grid lg:grid-cols-2 gap-6">
            {/* Account Usage */}
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100"
            >
              <div className="flex items-center justify-between mb-5">
                <h2 className="font-heading font-semibold text-lg text-slate-900">
                  Account Usage
                </h2>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-slate-500 hover:text-slate-700"
                  onClick={() => navigate("/accounts")}
                  data-testid="manage-accounts-btn"
                >
                  Manage
                  <ArrowRight size={14} className="ml-1" />
                </Button>
              </div>

              {stats?.accounts?.length > 0 ? (
                <div className="space-y-2">
                  {stats.accounts.slice(0, 4).map((account, index) => (
                    <AccountUsageCard key={account.account_id} account={account} index={index} />
                  ))}
                  {stats.accounts.length > 4 && (
                    <p className="text-sm text-slate-400 text-center pt-3">
                      +{stats.accounts.length - 4} more accounts
                    </p>
                  )}
                </div>
              ) : (
                <div className="text-center py-8">
                  <div className="w-14 h-14 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-3">
                    <Mail size={24} className="text-slate-400" />
                  </div>
                  <p className="text-slate-500 mb-4">No email accounts connected</p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="rounded-lg"
                    onClick={() => navigate("/accounts")}
                    data-testid="add-first-account-btn"
                  >
                    Add Account
                  </Button>
                </div>
              )}
            </motion.div>

            {/* Quick Start */}
            <motion.div 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100"
            >
              <h2 className="font-heading font-semibold text-lg text-slate-900 mb-5">
                Quick Start
              </h2>

              <div className="space-y-3">
                {/* Step 1 */}
                <div className={`flex items-center gap-4 p-4 rounded-xl transition-colors duration-200 ${
                  needsAccounts 
                    ? "bg-slate-50 border border-slate-200" 
                    : "bg-emerald-50/50 border border-emerald-200"
                }`}>
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                    needsAccounts ? "bg-white shadow-sm" : "bg-emerald-100"
                  }`}>
                    {needsAccounts ? (
                      <span className="text-slate-600 font-semibold">1</span>
                    ) : (
                      <CheckCircle2 size={20} className="text-emerald-600" />
                    )}
                  </div>
                  <div className="flex-1">
                    <p className={`font-medium ${needsAccounts ? "text-slate-700" : "text-emerald-800"}`}>
                      Connect Email Accounts
                    </p>
                    <p className={`text-sm ${needsAccounts ? "text-slate-500" : "text-emerald-600"}`}>
                      {needsAccounts ? "Add your sender accounts" : `${stats?.total_accounts} accounts connected`}
                    </p>
                  </div>
                  {needsAccounts && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="rounded-lg"
                      onClick={() => navigate("/accounts")}
                      data-testid="quick-add-account-btn"
                    >
                      Add
                    </Button>
                  )}
                </div>

                {/* Step 2 */}
                <div className={`flex items-center gap-4 p-4 rounded-xl transition-colors duration-200 ${
                  needsList 
                    ? "bg-slate-50 border border-slate-200" 
                    : "bg-emerald-50/50 border border-emerald-200"
                }`}>
                  <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                    needsList ? "bg-white shadow-sm" : "bg-emerald-100"
                  }`}>
                    {needsList ? (
                      <span className="text-slate-600 font-semibold">2</span>
                    ) : (
                      <CheckCircle2 size={20} className="text-emerald-600" />
                    )}
                  </div>
                  <div className="flex-1">
                    <p className={`font-medium ${needsList ? "text-slate-700" : "text-emerald-800"}`}>
                      Upload Email Lists
                    </p>
                    <p className={`text-sm ${needsList ? "text-slate-500" : "text-emerald-600"}`}>
                      {needsList 
                        ? "No email lists uploaded yet" 
                        : `${stats?.total_lists} list${stats?.total_lists !== 1 ? "s" : ""} uploaded`}
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="rounded-lg text-slate-600"
                    onClick={() => navigate("/email-lists")}
                    data-testid={needsList ? "quick-upload-btn" : "manage-lists-btn"}
                  >
                    {needsList ? "Upload" : "Manage"}
                  </Button>
                </div>

                {/* Step 3 */}
                <div className="flex items-center gap-4 p-4 rounded-xl bg-slate-50 border border-slate-200">
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center bg-white shadow-sm">
                    <span className="text-slate-600 font-semibold">3</span>
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-slate-700">Start Campaign</p>
                    <p className="text-sm text-slate-500">Compose and send your emails</p>
                  </div>
                  {!needsAccounts && !needsList && (
                    <Button
                      size="sm"
                      className="bg-blue-600 hover:bg-blue-700 rounded-lg"
                      onClick={() => navigate("/campaign")}
                      data-testid="quick-campaign-btn"
                    >
                      Create
                    </Button>
                  )}
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </main>
    </div>
  );
}
