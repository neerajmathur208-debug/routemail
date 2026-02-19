import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  Send,
  Play,
  Pause,
  RotateCw,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Mail,
  Users,
  Clock,
  RefreshCw,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { Progress } from "../components/ui/progress";
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

export default function Campaign({ user, setUser }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [lists, setLists] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [campaigns, setCampaigns] = useState([]);
  const [currentCampaign, setCurrentCampaign] = useState(null);
  const [startDialogOpen, setStartDialogOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    list_id: "",
    subject: "",
    body: "",
  });

  const fetchData = async () => {
    try {
      const [listsRes, accountsRes, campaignsRes] = await Promise.all([
        api.get("/lists"),
        api.get("/accounts"),
        api.get("/campaigns"),
      ]);

      setLists(listsRes.data);
      setAccounts(accountsRes.data);
      setCampaigns(campaignsRes.data);

      // Find running campaign
      const running = campaignsRes.data.find(
        (c) => c.status === "running" || c.status === "paused"
      );
      if (running) {
        const detailRes = await api.get(`/campaigns/${running.campaign_id}`);
        setCurrentCampaign(detailRes.data);
      }
    } catch (error) {
      console.error("Failed to fetch data:", error);
      toast.error("Failed to load campaign data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();

    // Poll for updates
    const interval = setInterval(() => {
      if (currentCampaign?.status === "running") {
        fetchCampaignStatus();
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [currentCampaign?.campaign_id, currentCampaign?.status]);

  const fetchCampaignStatus = async () => {
    if (!currentCampaign) return;
    try {
      const response = await api.get(`/campaigns/${currentCampaign.campaign_id}`);
      setCurrentCampaign(response.data);
    } catch (error) {
      console.error("Failed to fetch campaign status:", error);
    }
  };

  const handleCreateCampaign = async () => {
    if (!formData.list_id || !formData.subject || !formData.body) {
      toast.error("Please fill in all fields");
      return;
    }

    setSubmitting(true);
    try {
      const response = await api.post("/campaigns", formData);
      toast.success("Campaign created");
      setCurrentCampaign({ ...formData, ...response.data, sent_count: 0, failed_count: 0 });
      setStartDialogOpen(true);
    } catch (error) {
      const message = error.response?.data?.detail || "Failed to create campaign";
      toast.error(message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleStartCampaign = async (campaignId) => {
    try {
      await api.post(`/campaigns/${campaignId}/start`);
      toast.success("Campaign started");
      setStartDialogOpen(false);
      fetchData();
    } catch (error) {
      const message = error.response?.data?.detail || "Failed to start campaign";
      toast.error(message);
    }
  };

  const handlePauseCampaign = async () => {
    if (!currentCampaign) return;
    try {
      await api.post(`/campaigns/${currentCampaign.campaign_id}/pause`);
      toast.success("Campaign paused");
      fetchData();
    } catch (error) {
      toast.error("Failed to pause campaign");
    }
  };

  const handleResumeCampaign = async () => {
    if (!currentCampaign) return;
    try {
      await api.post(`/campaigns/${currentCampaign.campaign_id}/resume`);
      toast.success("Campaign resumed");
      fetchData();
    } catch (error) {
      const message = error.response?.data?.detail || "Failed to resume campaign";
      toast.error(message);
    }
  };

  const needsSubscription = user?.subscription_status !== "active";
  const hasAccounts = accounts.length > 0;
  const hasLists = lists.length > 0;
  const canCreate = !needsSubscription && hasAccounts && hasLists && !currentCampaign;

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
          <div className="mb-8">
            <h1 className="font-heading font-extrabold text-2xl sm:text-3xl text-slate-900">
              Campaign
            </h1>
            <p className="text-slate-500 mt-1">
              Create and manage your email campaigns
            </p>
          </div>

          {/* Alerts */}
          {needsSubscription && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-6 bg-amber-50 border border-amber-200 rounded-md p-4 flex items-center gap-4"
            >
              <AlertCircle size={20} className="text-amber-600 flex-shrink-0" />
              <div className="flex-1">
                <p className="text-amber-800 font-medium">Subscription required</p>
                <p className="text-amber-700 text-sm">Subscribe to create campaigns</p>
              </div>
              <Button
                size="sm"
                className="bg-amber-600 hover:bg-amber-700"
                onClick={() => navigate("/subscription")}
              >
                Subscribe
              </Button>
            </motion.div>
          )}

          {!needsSubscription && !hasAccounts && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-6 bg-blue-50 border border-blue-200 rounded-md p-4 flex items-center gap-4"
            >
              <Mail size={20} className="text-blue-600 flex-shrink-0" />
              <div className="flex-1">
                <p className="text-blue-800 font-medium">Add email accounts first</p>
                <p className="text-blue-700 text-sm">
                  You need at least one email account to send campaigns
                </p>
              </div>
              <Button
                size="sm"
                variant="outline"
                className="border-blue-300 text-blue-700"
                onClick={() => navigate("/accounts")}
              >
                Add Account
              </Button>
            </motion.div>
          )}

          {!needsSubscription && hasAccounts && !hasLists && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-6 bg-blue-50 border border-blue-200 rounded-md p-4 flex items-center gap-4"
            >
              <Users size={20} className="text-blue-600 flex-shrink-0" />
              <div className="flex-1">
                <p className="text-blue-800 font-medium">Upload an email list first</p>
                <p className="text-blue-700 text-sm">
                  You need at least one email list to create a campaign
                </p>
              </div>
              <Button
                size="sm"
                variant="outline"
                className="border-blue-300 text-blue-700"
                onClick={() => navigate("/upload")}
              >
                Upload List
              </Button>
            </motion.div>
          )}

          {/* Active Campaign */}
          {currentCampaign && (currentCampaign.status === "running" || currentCampaign.status === "paused") && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="mb-8 bg-white border border-slate-200 rounded-md p-6"
            >
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-3 h-3 rounded-full ${
                      currentCampaign.status === "running"
                        ? "bg-green-500 animate-pulse"
                        : "bg-amber-500"
                    }`}
                  />
                  <h2 className="font-heading font-semibold text-xl text-slate-900">
                    {currentCampaign.status === "running" ? "Campaign Running" : "Campaign Paused"}
                  </h2>
                </div>
                <div className="flex gap-2">
                  {currentCampaign.status === "running" ? (
                    <Button
                      variant="outline"
                      onClick={handlePauseCampaign}
                      data-testid="pause-campaign-btn"
                    >
                      <Pause size={16} className="mr-2" />
                      Pause
                    </Button>
                  ) : (
                    <Button
                      className="bg-electric-blue hover:bg-blue-700"
                      onClick={handleResumeCampaign}
                      data-testid="resume-campaign-btn"
                    >
                      <Play size={16} className="mr-2" />
                      Resume
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={fetchCampaignStatus}
                    data-testid="refresh-status-btn"
                  >
                    <RefreshCw size={18} />
                  </Button>
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <p className="text-sm text-slate-500 mb-1">Subject</p>
                  <p className="font-medium text-slate-900">{currentCampaign.subject}</p>
                </div>

                <div>
                  <div className="flex justify-between text-sm mb-2">
                    <span className="text-slate-500">Progress</span>
                    <span className="font-mono text-slate-900">
                      {currentCampaign.sent_count} / {currentCampaign.total_emails}
                    </span>
                  </div>
                  <Progress
                    value={(currentCampaign.sent_count / currentCampaign.total_emails) * 100}
                    className="h-3"
                  />
                </div>

                <div className="grid grid-cols-3 gap-4 pt-4 border-t border-slate-100">
                  <div className="text-center">
                    <div className="flex items-center justify-center gap-2 mb-1">
                      <CheckCircle2 size={18} className="text-green-600" />
                      <span className="text-2xl font-bold text-slate-900">
                        {currentCampaign.sent_count}
                      </span>
                    </div>
                    <p className="text-sm text-slate-500">Sent</p>
                  </div>
                  <div className="text-center">
                    <div className="flex items-center justify-center gap-2 mb-1">
                      <XCircle size={18} className="text-red-500" />
                      <span className="text-2xl font-bold text-slate-900">
                        {currentCampaign.failed_count}
                      </span>
                    </div>
                    <p className="text-sm text-slate-500">Failed</p>
                  </div>
                  <div className="text-center">
                    <div className="flex items-center justify-center gap-2 mb-1">
                      <Clock size={18} className="text-slate-400" />
                      <span className="text-2xl font-bold text-slate-900">
                        {currentCampaign.total_emails - currentCampaign.sent_count - currentCampaign.failed_count}
                      </span>
                    </div>
                    <p className="text-sm text-slate-500">Remaining</p>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* Create Campaign Form */}
          {canCreate && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-white border border-slate-200 rounded-md p-6"
            >
              <h2 className="font-heading font-semibold text-xl text-slate-900 mb-6">
                Create New Campaign
              </h2>

              <div className="space-y-6">
                <div>
                  <Label htmlFor="list">Select Email List</Label>
                  <Select
                    value={formData.list_id}
                    onValueChange={(value) =>
                      setFormData({ ...formData, list_id: value })
                    }
                  >
                    <SelectTrigger className="mt-1.5" data-testid="list-select">
                      <SelectValue placeholder="Choose a list" />
                    </SelectTrigger>
                    <SelectContent>
                      {lists.map((list) => (
                        <SelectItem key={list.list_id} value={list.list_id}>
                          {list.name} ({list.valid_emails} contacts)
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label htmlFor="subject">Subject Line</Label>
                  <Input
                    id="subject"
                    placeholder="Hi {first_name}, quick question about {company}"
                    value={formData.subject}
                    onChange={(e) =>
                      setFormData({ ...formData, subject: e.target.value })
                    }
                    className="mt-1.5"
                    data-testid="subject-input"
                  />
                  <p className="text-xs text-slate-500 mt-1">
                    Use {"{first_name}"} and {"{company}"} for personalization
                  </p>
                </div>

                <div>
                  <Label htmlFor="body">Email Body</Label>
                  <Textarea
                    id="body"
                    placeholder="Hi {first_name},

I noticed that {company} might benefit from...

Best regards"
                    value={formData.body}
                    onChange={(e) =>
                      setFormData({ ...formData, body: e.target.value })
                    }
                    className="mt-1.5 min-h-[200px] font-mono text-sm"
                    data-testid="body-textarea"
                  />
                  <p className="text-xs text-slate-500 mt-1">
                    Plain text only. An unsubscribe link will be automatically added.
                  </p>
                </div>

                <div className="flex items-center justify-between pt-4 border-t border-slate-100">
                  <div className="flex items-center gap-2 text-sm text-slate-500">
                    <RotateCw size={16} />
                    <span>
                      Will rotate across {accounts.length} account
                      {accounts.length > 1 ? "s" : ""}
                    </span>
                  </div>
                  <Button
                    onClick={handleCreateCampaign}
                    disabled={submitting}
                    className="bg-signal-orange hover:bg-orange-600"
                    data-testid="create-campaign-btn"
                  >
                    <Send size={16} className="mr-2" />
                    {submitting ? "Creating..." : "Create Campaign"}
                  </Button>
                </div>
              </div>
            </motion.div>
          )}

          {/* Previous Campaigns */}
          {campaigns.filter((c) => c.status === "completed").length > 0 && (
            <div className="mt-8">
              <h2 className="font-heading font-semibold text-lg text-slate-900 mb-4">
                Previous Campaigns
              </h2>
              <div className="space-y-3">
                {campaigns
                  .filter((c) => c.status === "completed")
                  .slice(0, 5)
                  .map((campaign, index) => (
                    <motion.div
                      key={campaign.campaign_id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05 }}
                      className="bg-white border border-slate-200 rounded-md p-4"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium text-slate-900">{campaign.subject}</p>
                          <p className="text-sm text-slate-500">
                            {campaign.sent_count} sent, {campaign.failed_count} failed
                          </p>
                        </div>
                        <span className="px-2 py-1 bg-green-100 text-green-700 text-xs font-medium rounded">
                          Completed
                        </span>
                      </div>
                    </motion.div>
                  ))}
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Start Campaign Dialog */}
      <AlertDialog open={startDialogOpen} onOpenChange={setStartDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading font-semibold">
              Start Campaign?
            </AlertDialogTitle>
            <AlertDialogDescription>
              This will begin sending emails to your list. Emails will be sent
              gradually with random delays and rotated across your{" "}
              {accounts.length} connected account{accounts.length > 1 ? "s" : ""}.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="cancel-start-btn">
              Save as Draft
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={() => handleStartCampaign(currentCampaign?.campaign_id)}
              className="bg-signal-orange hover:bg-orange-600"
              data-testid="confirm-start-btn"
            >
              <Play size={16} className="mr-2" />
              Start Now
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
