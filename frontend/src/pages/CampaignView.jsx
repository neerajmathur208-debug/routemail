import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Mail,
  Calendar,
  Users,
  Send,
  AlertCircle,
  CheckCircle2,
  Clock,
  Globe,
  Pause,
  Play,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import Sidebar from "../components/Sidebar";
import { api } from "../App";
import { toast } from "sonner";

export default function CampaignView({ user, setUser }) {
  const { campaignId } = useParams();
  const navigate = useNavigate();
  const [campaign, setCampaign] = useState(null);
  const [loading, setLoading] = useState(true);
  const [listName, setListName] = useState("");
  const [accountNames, setAccountNames] = useState([]);
  const [actionLoading, setActionLoading] = useState(false);

  const fetchCampaign = async () => {
    try {
      const response = await api.get(`/campaigns/${campaignId}`);
      setCampaign(response.data);
      
      // Fetch list name if list_id exists
      if (response.data.list_id) {
        try {
          const listRes = await api.get(`/lists/${response.data.list_id}`);
          setListName(listRes.data.name || "Unknown List");
        } catch (e) {
          setListName("List Deleted");
        }
      }
      
      // Fetch account names
      if (response.data.account_ids?.length > 0) {
        try {
          const accountsRes = await api.get("/accounts");
          const accounts = accountsRes.data.accounts || accountsRes.data || [];
          const names = response.data.account_ids.map(id => {
            const acc = accounts.find(a => a.account_id === id);
            return acc ? acc.email : "Unknown";
          });
          setAccountNames(names);
        } catch (e) {
          setAccountNames(["Unable to load accounts"]);
        }
      }
    } catch (error) {
      toast.error("Failed to load campaign");
      navigate("/dashboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCampaign();
  }, [campaignId, navigate]);

  const handlePauseCampaign = async () => {
    setActionLoading(true);
    try {
      await api.post(`/campaigns/${campaignId}/pause`);
      toast.success("Campaign paused successfully");
      fetchCampaign();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to pause campaign");
    } finally {
      setActionLoading(false);
    }
  };

  const handleResumeCampaign = async () => {
    setActionLoading(true);
    try {
      await api.post(`/campaigns/${campaignId}/resume`);
      toast.success("Campaign resumed successfully");
      fetchCampaign();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to resume campaign");
    } finally {
      setActionLoading(false);
    }
  };

  const getStatusBadge = (status) => {
    const statusConfig = {
      draft: { color: "bg-slate-100 text-slate-700", icon: Clock },
      scheduled: { color: "bg-purple-100 text-purple-700", icon: Calendar },
      running: { color: "bg-blue-100 text-blue-700", icon: Send },
      completed: { color: "bg-emerald-100 text-emerald-700", icon: CheckCircle2 },
      paused: { color: "bg-amber-100 text-amber-700", icon: Pause },
      paused_daily_limit: { color: "bg-orange-100 text-orange-700", icon: AlertCircle },
      failed: { color: "bg-red-100 text-red-700", icon: AlertCircle },
    };
    const config = statusConfig[status] || statusConfig.draft;
    const Icon = config.icon;
    const displayStatus = status === "paused_daily_limit" ? "Daily Limit Reached" : status.charAt(0).toUpperCase() + status.slice(1);
    return (
      <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium ${config.color}`}>
        <Icon size={14} />
        {displayStatus}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (!campaign) {
    return null;
  }

  return (
    <div className="min-h-screen bg-slate-50 flex">
      <Sidebar user={user} setUser={setUser} />
      
      <main className="flex-1 lg:ml-64 p-6">
        <div className="max-w-5xl mx-auto">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6"
          >
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/dashboard")}
              className="mb-4 text-slate-600 hover:text-slate-900"
              data-testid="back-to-dashboard"
            >
              <ArrowLeft size={16} className="mr-2" />
              Back to Dashboard
            </Button>
            
            <div className="flex items-start justify-between">
              <div>
                <h1 className="text-2xl font-heading font-bold text-slate-900 mb-2">
                  {campaign.name}
                </h1>
                <div className="flex items-center gap-3">
                  {getStatusBadge(campaign.status)}
                  {campaign.scheduled_at && campaign.status === "scheduled" && (
                    <span className="text-sm text-slate-500 flex items-center gap-1">
                      <Calendar size={14} />
                      Scheduled: {new Date(campaign.scheduled_at).toLocaleString()}
                    </span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {/* Pause button for running/scheduled campaigns */}
                {(campaign.status === "running" || campaign.status === "scheduled") && (
                  <Button
                    variant="outline"
                    onClick={handlePauseCampaign}
                    disabled={actionLoading}
                    className="text-amber-600 border-amber-300 hover:bg-amber-50"
                    data-testid="pause-campaign-btn"
                  >
                    <Pause size={16} className="mr-2" />
                    Pause Campaign
                  </Button>
                )}
                {/* Resume button for paused campaigns */}
                {(campaign.status === "paused" || campaign.status === "paused_daily_limit") && (
                  <Button
                    variant="outline"
                    onClick={handleResumeCampaign}
                    disabled={actionLoading}
                    className="text-blue-600 border-blue-300 hover:bg-blue-50"
                    data-testid="resume-campaign-btn"
                  >
                    <Play size={16} className="mr-2" />
                    Resume Campaign
                  </Button>
                )}
                <Button
                  variant="outline"
                  onClick={() => navigate(`/campaign/${campaignId}/logs`)}
                  data-testid="view-logs-btn"
                >
                  View Logs
                </Button>
              </div>
            </div>
          </motion.div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column - Campaign Content */}
            <div className="lg:col-span-2 space-y-6">
              {/* Subject */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.1 }}
                className="bg-white rounded-xl shadow-sm border border-slate-200 p-6"
              >
                <h3 className="text-sm font-medium text-slate-500 mb-2">Subject Line</h3>
                <p className="text-lg font-medium text-slate-900">{campaign.subject}</p>
              </motion.div>

              {/* Email Content */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
                className="bg-white rounded-xl shadow-sm border border-slate-200 p-6"
              >
                <h3 className="text-sm font-medium text-slate-500 mb-4">Email Content</h3>
                <div 
                  className="prose prose-sm max-w-none border rounded-lg p-4 bg-slate-50 min-h-[300px]"
                  dangerouslySetInnerHTML={{ __html: campaign.body }}
                />
              </motion.div>
            </div>

            {/* Right Column - Campaign Stats */}
            <div className="space-y-6">
              {/* Stats Card */}
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.15 }}
                className="bg-white rounded-xl shadow-sm border border-slate-200 p-6"
              >
                <h3 className="text-sm font-medium text-slate-500 mb-4">Campaign Statistics</h3>
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <span className="text-slate-600">Total Recipients</span>
                    <span className="font-semibold text-slate-900">{campaign.total_emails || 0}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-600 flex items-center gap-1">
                      <CheckCircle2 size={14} className="text-emerald-500" />
                      Sent
                    </span>
                    <span className="font-semibold text-emerald-600">{campaign.sent_count || 0}</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-slate-600 flex items-center gap-1">
                      <AlertCircle size={14} className="text-red-500" />
                      Failed
                    </span>
                    <span className="font-semibold text-red-600">{campaign.failed_count || 0}</span>
                  </div>
                  {(campaign.suppressed_count || 0) > 0 && (
                    <div className="flex justify-between items-center">
                      <span className="text-slate-600 flex items-center gap-1">
                        <AlertCircle size={14} className="text-rose-500" />
                        Suppressed
                      </span>
                      <span className="font-semibold text-rose-600">{campaign.suppressed_count}</span>
                    </div>
                  )}
                  {campaign.total_emails > 0 && (
                    <div className="pt-3 border-t">
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-slate-600">Progress</span>
                        <span className="font-semibold text-slate-900">
                          {Math.round((campaign.sent_count / campaign.total_emails) * 100)}%
                        </span>
                      </div>
                      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-gradient-to-r from-blue-500 to-emerald-500 rounded-full transition-all"
                          style={{ width: `${(campaign.sent_count / campaign.total_emails) * 100}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              </motion.div>

              {/* Details Card */}
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.25 }}
                className="bg-white rounded-xl shadow-sm border border-slate-200 p-6"
              >
                <h3 className="text-sm font-medium text-slate-500 mb-4">Campaign Details</h3>
                <div className="space-y-4 text-sm">
                  {campaign.from_name && (
                    <div>
                      <span className="text-slate-500">From Name</span>
                      <p className="font-medium text-slate-900">{campaign.from_name}</p>
                    </div>
                  )}
                  <div>
                    <span className="text-slate-500">Selected List</span>
                    <p className="font-medium text-slate-900 flex items-center gap-1">
                      <Users size={14} />
                      {listName || "No list selected"}
                    </p>
                  </div>
                  <div>
                    <span className="text-slate-500">Email Accounts</span>
                    <div className="mt-1 space-y-1">
                      {accountNames.length > 0 ? (
                        accountNames.map((name, i) => (
                          <p key={i} className="font-medium text-slate-900 flex items-center gap-1">
                            <Mail size={14} />
                            {name}
                          </p>
                        ))
                      ) : (
                        <p className="text-slate-400">No accounts selected</p>
                      )}
                    </div>
                  </div>
                  {campaign.timezone && (
                    <div>
                      <span className="text-slate-500">Timezone</span>
                      <p className="font-medium text-slate-900 flex items-center gap-1">
                        <Globe size={14} />
                        {campaign.timezone}
                      </p>
                    </div>
                  )}
                  <div>
                    <span className="text-slate-500">Created</span>
                    <p className="font-medium text-slate-900">
                      {new Date(campaign.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
              </motion.div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
