import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Mail,
  Users,
  Send,
  Clock,
  ArrowRight,
  Play,
  Pause,
  CheckCircle2,
  XCircle,
  Edit,
  Copy,
  RefreshCw,
  Eye,
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
    // Poll for updates every 10 seconds if campaign is running
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

  const StatCard = ({ icon: Icon, label, value, subtext, color = "slate" }) => (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white border border-slate-200 rounded-md p-6"
    >
      <div className="flex items-center gap-3 mb-4">
        <div className={`w-10 h-10 bg-${color}-100 rounded-md flex items-center justify-center`}>
          <Icon size={20} className={`text-${color}-600`} strokeWidth={1.5} />
        </div>
        <span className="text-slate-500 text-sm font-medium">{label}</span>
      </div>
      <p className="font-heading font-extrabold text-3xl text-slate-900">{value}</p>
      {subtext && <p className="text-sm text-slate-500 mt-1">{subtext}</p>}
    </motion.div>
  );

  const AccountUsageCard = ({ account }) => {
    const percentage = (account.daily_sent / account.daily_limit) * 100;
    
    return (
      <div className="flex items-center gap-4 p-4 border border-slate-200 rounded-md">
        <div className="flex-shrink-0">
          <div className={`status-dot ${account.status === "connected" ? "status-connected" : "status-error"}`} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-mono text-sm text-slate-900 truncate">{account.email}</p>
          <div className="mt-2 flex items-center gap-2">
            <Progress value={percentage} className="h-1.5 flex-1" />
            <span className="text-xs text-slate-500 whitespace-nowrap">
              {account.daily_sent}/{account.daily_limit}
            </span>
          </div>
        </div>
      </div>
    );
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

  const needsAccounts = stats?.total_accounts === 0;
  const needsList = stats?.total_lists === 0;

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar user={user} setUser={setUser} />
      
      <main className="flex-1 p-6 lg:p-8 overflow-y-auto">
        <div className="max-w-6xl mx-auto">
          {/* Header */}
          <div className="mb-8">
            <h1 className="font-heading font-extrabold text-2xl sm:text-3xl text-slate-900">
              Dashboard
            </h1>
            <p className="text-slate-500 mt-1">Overview of your email campaigns</p>
          </div>

          {/* Stats Grid */}
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <StatCard
              icon={Mail}
              label="Email Accounts"
              value={stats?.total_accounts || 0}
              subtext={`${stats?.total_available_today || 0} sends available today`}
            />
            <StatCard
              icon={Users}
              label="Total Contacts"
              value={stats?.total_contacts || 0}
              subtext={`${stats?.total_lists || 0} lists`}
            />
            <StatCard
              icon={Send}
              label="Emails Sent"
              value={stats?.total_sent || 0}
              subtext={`${stats?.total_failed || 0} failed`}
            />
            <StatCard
              icon={Clock}
              label="Campaigns"
              value={stats?.total_campaigns || 0}
            />
          </div>

          {/* Current Campaign */}
          {stats?.current_campaign && (stats.current_campaign.status === "running" || stats.current_campaign.status === "paused") && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="mb-8 bg-white border border-slate-200 rounded-md p-6"
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className={`w-3 h-3 rounded-full ${
                    stats.current_campaign.status === "running" 
                      ? "bg-green-500 animate-pulse" 
                      : stats.current_campaign.status === "paused"
                      ? "bg-amber-500"
                      : "bg-slate-400"
                  }`} />
                  <h2 className="font-heading font-semibold text-lg text-slate-900">
                    {stats.current_campaign.name || "Active Campaign"}
                  </h2>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    stats.current_campaign.status === "running"
                      ? "bg-green-100 text-green-700"
                      : stats.current_campaign.status === "paused"
                      ? "bg-amber-100 text-amber-700"
                      : "bg-slate-100 text-slate-600"
                  }`}>
                    {stats.current_campaign.status}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {stats.current_campaign.status === "running" ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handlePauseCampaign(stats.current_campaign.campaign_id)}
                    >
                      <Pause size={14} className="mr-1" />
                      Pause
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      className="bg-electric-blue hover:bg-blue-700"
                      onClick={() => handleResumeCampaign(stats.current_campaign.campaign_id)}
                    >
                      <Play size={14} className="mr-1" />
                      Resume
                    </Button>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => navigate("/campaign")}
                    data-testid="view-campaign-btn"
                  >
                    View Details
                    <ArrowRight size={14} className="ml-1" />
                  </Button>
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <p className="text-sm text-slate-500 mb-1">Subject</p>
                  <p className="text-slate-900 font-medium">{stats.current_campaign.subject}</p>
                </div>

                <div>
                  <div className="flex justify-between text-sm mb-2">
                    <span className="text-slate-500">Progress</span>
                    <span className="text-slate-900 font-medium">
                      {stats.current_campaign.sent_count} / {stats.current_campaign.total_emails}
                    </span>
                  </div>
                  <Progress 
                    value={(stats.current_campaign.sent_count / stats.current_campaign.total_emails) * 100} 
                    className="h-2"
                  />
                </div>

                <div className="flex gap-6 text-sm">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 size={16} className="text-green-600" />
                    <span className="text-slate-600">{stats.current_campaign.sent_count} sent</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <XCircle size={16} className="text-red-500" />
                    <span className="text-slate-600">{stats.current_campaign.failed_count} failed</span>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* All Campaigns Section */}
          {stats?.campaigns && stats.campaigns.length > 0 && (
            <div className="mb-8 bg-white border border-slate-200 rounded-md">
              <div className="p-4 border-b border-slate-200 flex items-center justify-between">
                <h2 className="font-heading font-semibold text-lg text-slate-900">
                  All Campaigns
                </h2>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => navigate("/campaign")}
                >
                  View All
                  <ArrowRight size={14} className="ml-1" />
                </Button>
              </div>
              <div className="divide-y divide-slate-100">
                {stats.campaigns.slice(0, 5).map((campaign) => (
                  <div key={campaign.campaign_id} className="p-4 hover:bg-slate-50">
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3">
                          <p className="font-medium text-slate-900 truncate">
                            {campaign.name || campaign.subject}
                          </p>
                          <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                            campaign.status === "completed" ? "bg-green-100 text-green-700" :
                            campaign.status === "running" ? "bg-blue-100 text-blue-700" :
                            campaign.status === "paused" ? "bg-amber-100 text-amber-700" :
                            "bg-slate-100 text-slate-600"
                          }`}>
                            {campaign.status}
                          </span>
                        </div>
                        <div className="flex items-center gap-4 mt-1 text-sm text-slate-500">
                          <span>{campaign.total_emails} recipients</span>
                          {campaign.status !== "draft" && (
                            <span>{campaign.sent_count} sent</span>
                          )}
                        </div>
                        {campaign.status !== "draft" && campaign.total_emails > 0 && (
                          <Progress
                            value={(campaign.sent_count / campaign.total_emails) * 100}
                            className="h-1.5 mt-2 max-w-xs"
                          />
                        )}
                      </div>
                      <div className="flex items-center gap-2 ml-4">
                        {campaign.status === "draft" && (
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => navigate(`/campaign?edit=${campaign.campaign_id}`)}
                          >
                            <Edit size={16} className="text-slate-400" />
                          </Button>
                        )}
                        {campaign.status === "paused" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleResumeCampaign(campaign.campaign_id)}
                          >
                            <Play size={14} className="mr-1" />
                            Resume
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Quick Actions */}
          <div className="grid lg:grid-cols-2 gap-6">
            {/* Account Usage */}
            <div className="bg-white border border-slate-200 rounded-md p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-heading font-semibold text-lg text-slate-900">
                  Account Usage Today
                </h2>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => navigate("/accounts")}
                  data-testid="manage-accounts-btn"
                >
                  Manage
                  <ArrowRight size={14} className="ml-1" />
                </Button>
              </div>

              {stats?.accounts?.length > 0 ? (
                <div className="space-y-3">
                  {stats.accounts.slice(0, 4).map((account) => (
                    <AccountUsageCard key={account.account_id} account={account} />
                  ))}
                  {stats.accounts.length > 4 && (
                    <p className="text-sm text-slate-500 text-center pt-2">
                      +{stats.accounts.length - 4} more accounts
                    </p>
                  )}
                </div>
              ) : (
                <div className="empty-state">
                  <Mail size={32} className="mx-auto mb-3 text-slate-300" />
                  <p className="text-slate-500">No email accounts connected</p>
                  <Button
                    variant="outline"
                    size="sm"
                    className="mt-4"
                    onClick={() => navigate("/accounts")}
                    data-testid="add-first-account-btn"
                  >
                    Add Account
                  </Button>
                </div>
              )}
            </div>

            {/* Quick Start */}
            <div className="bg-white border border-slate-200 rounded-md p-6">
              <h2 className="font-heading font-semibold text-lg text-slate-900 mb-4">
                Quick Start
              </h2>

              <div className="space-y-4">
                <div className={`flex items-center gap-4 p-4 rounded-md border ${
                  needsAccounts ? "border-slate-200" : "border-green-200 bg-green-50"
                }`}>
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                    needsAccounts ? "bg-slate-100" : "bg-green-100"
                  }`}>
                    {needsAccounts ? (
                      <span className="text-slate-600 font-semibold">1</span>
                    ) : (
                      <CheckCircle2 size={18} className="text-green-600" />
                    )}
                  </div>
                  <div className="flex-1">
                    <p className={`font-medium ${needsAccounts ? "text-slate-700" : "text-green-800"}`}>
                      Connect Email Accounts
                    </p>
                    <p className={`text-sm ${needsAccounts ? "text-slate-500" : "text-green-600"}`}>
                      {needsAccounts ? "Add your sender accounts" : `${stats?.total_accounts} accounts connected`}
                    </p>
                  </div>
                  {needsAccounts && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => navigate("/accounts")}
                      data-testid="quick-add-account-btn"
                    >
                      Add
                    </Button>
                  )}
                </div>

                <div className={`flex items-center gap-4 p-4 rounded-md border ${
                  needsList ? "border-slate-200" : "border-green-200 bg-green-50"
                }`}>
                  <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                    needsList ? "bg-slate-100" : "bg-green-100"
                  }`}>
                    {needsList ? (
                      <span className="text-slate-600 font-semibold">2</span>
                    ) : (
                      <CheckCircle2 size={18} className="text-green-600" />
                    )}
                  </div>
                  <div className="flex-1">
                    <p className={`font-medium ${needsList ? "text-slate-700" : "text-green-800"}`}>
                      Upload Email List
                    </p>
                    <p className={`text-sm ${needsList ? "text-slate-500" : "text-green-600"}`}>
                      {needsList ? "Import your contacts via CSV" : `${stats?.total_contacts} contacts uploaded`}
                    </p>
                  </div>
                  {needsList && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => navigate("/upload")}
                      data-testid="quick-upload-btn"
                    >
                      Upload
                    </Button>
                  )}
                </div>

                <div className="flex items-center gap-4 p-4 rounded-md border border-slate-200">
                  <div className="w-8 h-8 rounded-full flex items-center justify-center bg-slate-100">
                    <span className="text-slate-600 font-semibold">3</span>
                  </div>
                  <div className="flex-1">
                    <p className="font-medium text-slate-700">Start Campaign</p>
                    <p className="text-sm text-slate-500">Compose and send your emails</p>
                  </div>
                  {!needsAccounts && !needsList && (
                    <Button
                      size="sm"
                      className="bg-electric-blue hover:bg-blue-700"
                      onClick={() => navigate("/campaign")}
                      data-testid="quick-campaign-btn"
                    >
                      Create
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
