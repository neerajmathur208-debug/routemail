import { useState, useEffect, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
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
  Save,
  Copy,
  Trash2,
  Edit,
  Eye,
  ArrowLeft,
  FileText,
  Code,
  Calendar,
  CalendarClock,
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
import { Switch } from "../components/ui/switch";
import { Checkbox } from "../components/ui/checkbox";
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
import Sidebar from "../components/Sidebar";
import RichTextEditor from "../components/RichTextEditor";
import { api } from "../App";
import { toast } from "sonner";

export default function Campaign({ user, setUser }) {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const editId = searchParams.get("edit");
  
  const [loading, setLoading] = useState(true);
  const [lists, setLists] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [campaigns, setCampaigns] = useState([]);
  const [currentCampaign, setCurrentCampaign] = useState(null);
  const [selectedList, setSelectedList] = useState(null);
  const [startDialogOpen, setStartDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [campaignToDelete, setCampaignToDelete] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [showPlainText, setShowPlainText] = useState(false);
  const [view, setView] = useState("list"); // list, create, edit
  
  // Send Test Email state
  const [testEmailDialogOpen, setTestEmailDialogOpen] = useState(false);
  const [testEmailAddress, setTestEmailAddress] = useState("");
  const [sendingTestEmail, setSendingTestEmail] = useState(false);

  // Form state
  const [formData, setFormData] = useState({
    name: "",
    subject: "",
    body: "",
    body_text: "",
    from_name: "",
    list_id: "",
    account_ids: [],
    scheduled_at: "",
  });
  
  // Scheduler state
  const [sendOption, setSendOption] = useState("now"); // "now" or "schedule"
  const [scheduleDate, setScheduleDate] = useState("");
  const [scheduleTime, setScheduleTime] = useState("");

  const fetchData = useCallback(async () => {
    try {
      const [listsRes, accountsRes, campaignsRes] = await Promise.all([
        api.get("/lists"),
        api.get("/accounts"),
        api.get("/campaigns"),
      ]);

      setLists(listsRes.data);
      // Handle accounts response - API returns { accounts: [], limit_info: {} }
      const accountsData = accountsRes.data?.accounts || accountsRes.data || [];
      setAccounts(Array.isArray(accountsData) ? accountsData : []);
      setCampaigns(campaignsRes.data);

      // Find running campaign
      const running = campaignsRes.data.find(
        (c) => c.status === "running" || c.status === "paused"
      );
      if (running) {
        const detailRes = await api.get(`/campaigns/${running.campaign_id}`);
        setCurrentCampaign(detailRes.data);
      }

      // If editing, load campaign data
      if (editId) {
        const campaign = campaignsRes.data.find(c => c.campaign_id === editId);
        if (campaign) {
          setFormData({
            name: campaign.name || "",
            subject: campaign.subject || "",
            body: campaign.body || "",
            body_text: campaign.body_text || "",
            from_name: campaign.from_name || "",
            list_id: campaign.list_id || "",
            account_ids: campaign.account_ids || [],
            scheduled_at: campaign.scheduled_at || "",
          });
          setView("edit");
          
          // If campaign has scheduled_at, set schedule mode
          if (campaign.scheduled_at) {
            setSendOption("schedule");
            const dt = new Date(campaign.scheduled_at);
            setScheduleDate(dt.toISOString().split('T')[0]);
            setScheduleTime(dt.toTimeString().slice(0, 5));
          }
          
          // Load selected list for variables
          if (campaign.list_id) {
            const listRes = await api.get(`/lists/${campaign.list_id}`);
            setSelectedList(listRes.data);
          }
        }
      }
    } catch (error) {
      console.error("Failed to fetch data:", error);
      toast.error("Failed to load campaign data");
    } finally {
      setLoading(false);
    }
  }, [editId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    // Poll for updates if campaign is running
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

  const handleListChange = async (listId) => {
    setFormData({ ...formData, list_id: listId });
    if (listId) {
      try {
        const response = await api.get(`/lists/${listId}`);
        setSelectedList(response.data);
      } catch (error) {
        console.error("Failed to load list:", error);
      }
    } else {
      setSelectedList(null);
    }
  };

  const handleAccountToggle = (accountId) => {
    const newIds = formData.account_ids.includes(accountId)
      ? formData.account_ids.filter(id => id !== accountId)
      : [...formData.account_ids, accountId];
    setFormData({ ...formData, account_ids: newIds });
  };

  const handleSaveCampaign = async () => {
    if (!formData.name || !formData.subject || !formData.body) {
      toast.error("Please fill in campaign name, subject, and body");
      return;
    }

    // Build scheduled_at from date/time if scheduling
    let scheduled_at = null;
    if (sendOption === "schedule" && scheduleDate && scheduleTime) {
      const scheduledDateTime = new Date(`${scheduleDate}T${scheduleTime}`);
      if (scheduledDateTime <= new Date()) {
        toast.error("Scheduled time must be in the future");
        return;
      }
      scheduled_at = scheduledDateTime.toISOString();
    }

    const payload = {
      ...formData,
      scheduled_at: scheduled_at || "",
    };

    setSubmitting(true);
    try {
      if (editId) {
        await api.put(`/campaigns/${editId}`, payload);
        toast.success("Campaign updated");
      } else {
        const response = await api.post("/campaigns", payload);
        toast.success("Campaign saved");
        navigate(`/campaign?edit=${response.data.campaign_id}`);
      }
      fetchData();
    } catch (error) {
      const message = error.response?.data?.detail || "Failed to save campaign";
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
      setView("list");
      fetchData();
    } catch (error) {
      const message = error.response?.data?.detail || "Failed to start campaign";
      toast.error(message);
    }
  };

  const handleScheduleCampaign = async (campaignId) => {
    // First save the campaign with scheduled_at
    if (!scheduleDate || !scheduleTime) {
      toast.error("Please select date and time for scheduling");
      return;
    }
    
    const scheduledDateTime = new Date(`${scheduleDate}T${scheduleTime}`);
    if (scheduledDateTime <= new Date()) {
      toast.error("Scheduled time must be in the future");
      return;
    }

    try {
      // Update campaign with scheduled_at
      await api.put(`/campaigns/${campaignId}`, {
        ...formData,
        scheduled_at: scheduledDateTime.toISOString(),
      });
      
      // Then schedule it
      await api.post(`/campaigns/${campaignId}/schedule`);
      toast.success("Campaign scheduled successfully");
      setStartDialogOpen(false);
      setView("list");
      fetchData();
    } catch (error) {
      const message = error.response?.data?.detail || "Failed to schedule campaign";
      toast.error(message);
    }
  };

  const handleUnscheduleCampaign = async (campaignId) => {
    try {
      await api.post(`/campaigns/${campaignId}/unschedule`);
      toast.success("Campaign unscheduled");
      fetchData();
    } catch (error) {
      const message = error.response?.data?.detail || "Failed to unschedule campaign";
      toast.error(message);
    }
  };

  const handlePauseCampaign = async (campaignId) => {
    try {
      await api.post(`/campaigns/${campaignId}/pause`);
      toast.success("Campaign paused");
      fetchData();
    } catch (error) {
      toast.error("Failed to pause campaign");
    }
  };

  const handleResumeCampaign = async (campaignId) => {
    try {
      await api.post(`/campaigns/${campaignId}/resume`);
      toast.success("Campaign resumed");
      fetchData();
    } catch (error) {
      const message = error.response?.data?.detail || "Failed to resume campaign";
      toast.error(message);
    }
  };

  const handleDuplicateCampaign = async (campaignId) => {
    try {
      const response = await api.post(`/campaigns/${campaignId}/duplicate`);
      toast.success("Campaign duplicated");
      navigate(`/campaign?edit=${response.data.campaign_id}`);
      fetchData();
    } catch (error) {
      toast.error("Failed to duplicate campaign");
    }
  };

  const handleDeleteCampaign = async () => {
    if (!campaignToDelete) return;
    try {
      await api.delete(`/campaigns/${campaignToDelete}`);
      toast.success("Campaign deleted");
      setDeleteDialogOpen(false);
      setCampaignToDelete(null);
      if (editId === campaignToDelete) {
        navigate("/campaign");
        setView("list");
      }
      fetchData();
    } catch (error) {
      toast.error("Failed to delete campaign");
    }
  };

  const resetForm = () => {
    setFormData({
      name: "",
      subject: "",
      body: "",
      body_text: "",
      from_name: "",
      list_id: "",
      account_ids: [],
      scheduled_at: "",
    });
    setSelectedList(null);
    setSendOption("now");
    setScheduleDate("");
    setScheduleTime("");
  };

  const hasAccounts = accounts.length > 0;
  const hasLists = lists.length > 0;

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

  // Campaign Editor View
  if (view === "create" || view === "edit") {
    const availableVariables = selectedList?.column_headers || [];
    
    return (
      <div className="flex min-h-screen bg-slate-50">
        <Sidebar user={user} setUser={setUser} />

        <main className="flex-1 p-6 lg:p-8 overflow-y-auto">
          <div className="max-w-4xl mx-auto">
            {/* Header */}
            <div className="flex items-center gap-4 mb-8">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => {
                  setView("list");
                  resetForm();
                  navigate("/campaign");
                }}
                data-testid="back-btn"
              >
                <ArrowLeft size={20} />
              </Button>
              <div>
                <h1 className="font-heading font-extrabold text-2xl sm:text-3xl text-slate-900">
                  {view === "edit" ? "Edit Campaign" : "Create Campaign"}
                </h1>
                <p className="text-slate-500 mt-1">
                  {view === "edit" ? "Modify your campaign settings" : "Set up your email campaign"}
                </p>
              </div>
            </div>

            {/* Alert - Missing Requirements Warning */}
            {(!hasAccounts || !hasLists) && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className="mb-6 bg-amber-50 border border-amber-200 rounded-lg p-4 flex items-start gap-3"
                data-testid="setup-warning"
              >
                <AlertCircle size={20} className="text-amber-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-amber-800 font-medium">Complete setup before launching</p>
                  <p className="text-amber-700 text-sm mt-1">
                    You need to connect at least one email account and upload at least one contact list before launching a campaign.
                  </p>
                  <div className="flex gap-3 mt-3">
                    {!hasAccounts && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="border-amber-300 text-amber-700 hover:bg-amber-100"
                        onClick={() => navigate("/accounts")}
                      >
                        <Mail size={14} className="mr-1.5" />
                        Add Account
                      </Button>
                    )}
                    {!hasLists && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="border-amber-300 text-amber-700 hover:bg-amber-100"
                        onClick={() => navigate("/upload")}
                      >
                        <Users size={14} className="mr-1.5" />
                        Upload List
                      </Button>
                    )}
                  </div>
                </div>
              </motion.div>
            )}

            {/* Individual Alerts - Only show when respective item is missing */}
            {!hasAccounts && hasLists && (
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

            {hasAccounts && !hasLists && (
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

            {/* Campaign Form */}
            <div className="bg-white border border-slate-200 rounded-md p-6 space-y-6">
              {/* Campaign Name */}
              <div>
                <Label htmlFor="name">Campaign Name *</Label>
                <Input
                  id="name"
                  placeholder="My Email Campaign"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="mt-1.5"
                  data-testid="campaign-name-input"
                />
              </div>

              {/* From Name */}
              <div>
                <Label htmlFor="from_name">From Name (optional)</Label>
                <Input
                  id="from_name"
                  placeholder="John Doe"
                  value={formData.from_name}
                  onChange={(e) => setFormData({ ...formData, from_name: e.target.value })}
                  className="mt-1.5"
                  data-testid="from-name-input"
                />
                <p className="text-xs text-slate-500 mt-1">
                  Display name that recipients will see
                </p>
              </div>

              {/* Email List Selection */}
              <div>
                <Label>Select Email List *</Label>
                <Select
                  value={formData.list_id}
                  onValueChange={handleListChange}
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

              {/* Email Accounts Selection */}
              <div>
                <Label>Select Email Accounts (optional)</Label>
                <p className="text-xs text-slate-500 mb-2">
                  Leave empty to use all connected accounts
                </p>
                <div className="space-y-2 mt-1.5">
                  {accounts.map((account) => (
                    <div
                      key={account.account_id}
                      className="flex items-center gap-3 p-3 border border-slate-200 rounded-md"
                    >
                      <Checkbox
                        id={account.account_id}
                        checked={formData.account_ids.includes(account.account_id)}
                        onCheckedChange={() => handleAccountToggle(account.account_id)}
                        data-testid={`account-checkbox-${account.account_id}`}
                      />
                      <label
                        htmlFor={account.account_id}
                        className="flex-1 cursor-pointer"
                      >
                        <p className="font-medium text-slate-900">{account.display_name}</p>
                        <p className="text-sm text-slate-500 font-mono">{account.email}</p>
                      </label>
                      <span className={`text-xs px-2 py-1 rounded ${
                        account.status === "connected" 
                          ? "bg-green-100 text-green-700" 
                          : "bg-red-100 text-red-700"
                      }`}>
                        {account.status}
                      </span>
                    </div>
                  ))}
                  {accounts.length === 0 && (
                    <p className="text-slate-500 text-sm">No accounts connected yet</p>
                  )}
                </div>
              </div>

              {/* Subject Line */}
              <div>
                <Label htmlFor="subject">Subject Line *</Label>
                <Input
                  id="subject"
                  placeholder="Hi {{first_name}}, quick question about {{company}}"
                  value={formData.subject}
                  onChange={(e) => setFormData({ ...formData, subject: e.target.value })}
                  className="mt-1.5"
                  data-testid="subject-input"
                />
                <p className="text-xs text-slate-500 mt-1">
                  Use {"{{column_name}}"} for personalization
                </p>
              </div>

              {/* Email Body */}
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <Label>Email Body *</Label>
                  <div className="flex items-center gap-2">
                    <FileText size={14} className="text-slate-400" />
                    <span className="text-xs text-slate-500">Rich Text</span>
                    <Switch
                      checked={showPlainText}
                      onCheckedChange={setShowPlainText}
                      data-testid="plain-text-toggle"
                    />
                    <Code size={14} className="text-slate-400" />
                    <span className="text-xs text-slate-500">Plain Text</span>
                  </div>
                </div>
                <RichTextEditor
                  value={formData.body}
                  onChange={(value) => setFormData({ ...formData, body: value })}
                  placeholder="Hi {{first_name}},

I noticed that {{company}} might benefit from...

Best regards"
                  variables={availableVariables}
                  showPlainText={showPlainText}
                  plainTextValue={formData.body_text}
                  onPlainTextChange={(value) => setFormData({ ...formData, body_text: value })}
                />
              </div>

              {/* Sending Options */}
              <div className="border-t border-slate-100 pt-6">
                <Label className="mb-3 block">Sending Options</Label>
                <div className="flex gap-4">
                  <div
                    onClick={() => setSendOption("now")}
                    className={`flex-1 p-4 rounded-xl border-2 cursor-pointer transition-all ${
                      sendOption === "now"
                        ? "border-blue-500 bg-blue-50"
                        : "border-slate-200 hover:border-slate-300"
                    }`}
                    data-testid="send-now-option"
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                        sendOption === "now" ? "bg-blue-500 text-white" : "bg-slate-100 text-slate-500"
                      }`}>
                        <Send size={18} />
                      </div>
                      <div>
                        <p className="font-semibold text-slate-900">Send Now</p>
                        <p className="text-sm text-slate-500">Start immediately</p>
                      </div>
                    </div>
                  </div>
                  <div
                    onClick={() => setSendOption("schedule")}
                    className={`flex-1 p-4 rounded-xl border-2 cursor-pointer transition-all ${
                      sendOption === "schedule"
                        ? "border-blue-500 bg-blue-50"
                        : "border-slate-200 hover:border-slate-300"
                    }`}
                    data-testid="schedule-option"
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                        sendOption === "schedule" ? "bg-blue-500 text-white" : "bg-slate-100 text-slate-500"
                      }`}>
                        <CalendarClock size={18} />
                      </div>
                      <div>
                        <p className="font-semibold text-slate-900">Schedule for Later</p>
                        <p className="text-sm text-slate-500">Set date and time</p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Schedule DateTime Picker */}
                {sendOption === "schedule" && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mt-4 p-4 bg-slate-50 rounded-xl border border-slate-200"
                  >
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <Label htmlFor="schedule-date" className="text-sm">Date</Label>
                        <Input
                          id="schedule-date"
                          type="date"
                          value={scheduleDate}
                          onChange={(e) => setScheduleDate(e.target.value)}
                          min={new Date().toISOString().split('T')[0]}
                          className="mt-1.5"
                          data-testid="schedule-date-input"
                        />
                      </div>
                      <div>
                        <Label htmlFor="schedule-time" className="text-sm">Time</Label>
                        <Input
                          id="schedule-time"
                          type="time"
                          value={scheduleTime}
                          onChange={(e) => setScheduleTime(e.target.value)}
                          className="mt-1.5"
                          data-testid="schedule-time-input"
                        />
                      </div>
                    </div>
                    <p className="text-xs text-slate-500 mt-3 flex items-center gap-1">
                      <Clock size={12} />
                      Time zone: {Intl.DateTimeFormat().resolvedOptions().timeZone}
                    </p>
                  </motion.div>
                )}
              </div>

              {/* Actions */}
              <div className="flex items-center justify-between pt-4 border-t border-slate-100">
                <div className="flex items-center gap-2 text-sm text-slate-500">
                  <RotateCw size={16} />
                  <span>
                    {formData.account_ids.length > 0 
                      ? `Will rotate across ${formData.account_ids.length} selected account${formData.account_ids.length > 1 ? "s" : ""}`
                      : `Will rotate across all ${accounts.length} account${accounts.length !== 1 ? "s" : ""}`
                    }
                  </span>
                </div>
                <div className="flex gap-3">
                  <Button
                    variant="outline"
                    onClick={handleSaveCampaign}
                    disabled={submitting}
                    data-testid="save-campaign-btn"
                  >
                    <Save size={16} className="mr-2" />
                    {submitting ? "Saving..." : "Save Draft"}
                  </Button>
                  {view === "edit" && (
                    <Button
                      onClick={() => setStartDialogOpen(true)}
                      disabled={submitting || !formData.list_id || !hasAccounts || !hasLists}
                      className={sendOption === "schedule" ? "bg-blue-600 hover:bg-blue-700" : "bg-signal-orange hover:bg-orange-600"}
                      data-testid="start-campaign-btn"
                      title={!hasAccounts || !hasLists ? "Complete setup to launch campaign" : ""}
                    >
                      {sendOption === "schedule" ? (
                        <>
                          <CalendarClock size={16} className="mr-2" />
                          Schedule Campaign
                        </>
                      ) : (
                        <>
                          <Send size={16} className="mr-2" />
                          Start Campaign
                        </>
                      )}
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </div>
        </main>

        {/* Start/Schedule Campaign Dialog */}
        <AlertDialog open={startDialogOpen} onOpenChange={setStartDialogOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle className="font-heading font-semibold">
                {sendOption === "schedule" ? "Schedule Campaign?" : "Start Campaign?"}
              </AlertDialogTitle>
              <AlertDialogDescription>
                {sendOption === "schedule" ? (
                  scheduleDate && scheduleTime ? (
                    <>
                      This campaign will be scheduled to start on{" "}
                      <span className="font-semibold text-slate-900">
                        {new Date(`${scheduleDate}T${scheduleTime}`).toLocaleString()}
                      </span>
                      . Emails will be sent gradually with random delays and rotated across your connected accounts.
                    </>
                  ) : (
                    "Please select a date and time to schedule this campaign."
                  )
                ) : (
                  "This will begin sending emails to your list. Emails will be sent gradually with random delays and rotated across your connected accounts."
                )}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel data-testid="cancel-start-btn">
                Cancel
              </AlertDialogCancel>
              {sendOption === "schedule" ? (
                <AlertDialogAction
                  onClick={() => handleScheduleCampaign(editId)}
                  disabled={!scheduleDate || !scheduleTime}
                  className="bg-blue-600 hover:bg-blue-700"
                  data-testid="confirm-schedule-btn"
                >
                  <CalendarClock size={16} className="mr-2" />
                  Schedule
                </AlertDialogAction>
              ) : (
                <AlertDialogAction
                  onClick={() => handleStartCampaign(editId)}
                  className="bg-signal-orange hover:bg-orange-600"
                  data-testid="confirm-start-btn"
                >
                  <Play size={16} className="mr-2" />
                  Start Now
                </AlertDialogAction>
              )}
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </div>
    );
  }

  // Campaign List View
  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar user={user} setUser={setUser} />

      <main className="flex-1 p-6 lg:p-8 overflow-y-auto">
        <div className="max-w-6xl mx-auto">
          {/* Back Button */}
          <motion.div
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            className="mb-4"
          >
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/dashboard")}
              className="text-slate-500 hover:text-slate-700 -ml-2"
              data-testid="back-to-dashboard-btn"
            >
              <ArrowLeft size={16} className="mr-1.5" />
              Back to Dashboard
            </Button>
          </motion.div>

          {/* Header */}
          <div className="flex items-center justify-between mb-8">
            <div>
              <h1 className="font-heading font-extrabold text-2xl sm:text-3xl text-slate-900">
                Campaigns
              </h1>
              <p className="text-slate-500 mt-1">
                Create and manage your email campaigns
              </p>
            </div>
            <Button
              onClick={() => {
                resetForm();
                setView("create");
              }}
              className="bg-electric-blue hover:bg-blue-700"
              data-testid="create-campaign-btn"
            >
              <Send size={16} className="mr-2" />
              New Campaign
            </Button>
          </div>

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
                    {currentCampaign.name || "Active Campaign"}
                  </h2>
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    currentCampaign.status === "running"
                      ? "bg-green-100 text-green-700"
                      : "bg-amber-100 text-amber-700"
                  }`}>
                    {currentCampaign.status}
                  </span>
                </div>
                <div className="flex gap-2">
                  {currentCampaign.status === "running" ? (
                    <Button
                      variant="outline"
                      onClick={() => handlePauseCampaign(currentCampaign.campaign_id)}
                      data-testid="pause-campaign-btn"
                    >
                      <Pause size={16} className="mr-2" />
                      Pause
                    </Button>
                  ) : (
                    <Button
                      className="bg-electric-blue hover:bg-blue-700"
                      onClick={() => handleResumeCampaign(currentCampaign.campaign_id)}
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

          {/* Campaign List */}
          <div className="bg-white border border-slate-200 rounded-md">
            <div className="p-4 border-b border-slate-200">
              <h2 className="font-heading font-semibold text-lg text-slate-900">
                All Campaigns
              </h2>
            </div>

            {campaigns.length > 0 ? (
              <div className="divide-y divide-slate-100">
                {campaigns.map((campaign, index) => (
                  <motion.div
                    key={campaign.campaign_id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className="p-4 hover:bg-slate-50 transition-colors"
                  >
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
                            campaign.status === "scheduled" ? "bg-purple-100 text-purple-700" :
                            "bg-slate-100 text-slate-600"
                          }`}>
                            {campaign.status}
                          </span>
                          {campaign.status === "scheduled" && campaign.scheduled_at && (
                            <span className="flex items-center gap-1 text-xs text-purple-600">
                              <CalendarClock size={12} />
                              {new Date(campaign.scheduled_at).toLocaleString()}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-4 mt-1 text-sm text-slate-500">
                          <span>{campaign.total_emails} recipients</span>
                          {campaign.status !== "draft" && campaign.status !== "scheduled" && (
                            <span>{campaign.sent_count} sent</span>
                          )}
                          <span>
                            {new Date(campaign.created_at).toLocaleDateString()}
                          </span>
                        </div>
                        {campaign.status !== "draft" && campaign.status !== "scheduled" && campaign.total_emails > 0 && (
                          <div className="mt-2">
                            <Progress
                              value={(campaign.sent_count / campaign.total_emails) * 100}
                              className="h-1.5"
                            />
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-2 ml-4">
                        {(campaign.status === "draft" || campaign.status === "scheduled") && (
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => navigate(`/campaign?edit=${campaign.campaign_id}`)}
                            data-testid={`edit-campaign-${campaign.campaign_id}`}
                          >
                            <Edit size={18} className="text-slate-400" />
                          </Button>
                        )}
                        {campaign.status === "scheduled" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleUnscheduleCampaign(campaign.campaign_id)}
                            className="text-purple-600 hover:text-purple-700"
                            data-testid={`unschedule-${campaign.campaign_id}`}
                          >
                            <XCircle size={16} className="mr-1" />
                            Unschedule
                          </Button>
                        )}
                        {campaign.status === "paused" && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleResumeCampaign(campaign.campaign_id)}
                            data-testid={`resume-${campaign.campaign_id}`}
                          >
                            <Play size={16} className="mr-1" />
                            Resume
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => handleDuplicateCampaign(campaign.campaign_id)}
                          data-testid={`duplicate-campaign-${campaign.campaign_id}`}
                        >
                          <Copy size={18} className="text-slate-400" />
                        </Button>
                        {(campaign.status === "completed" || campaign.status === "running" || campaign.status === "paused") && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => navigate(`/campaign/${campaign.campaign_id}/logs`)}
                            data-testid={`view-logs-${campaign.campaign_id}`}
                          >
                            <Eye size={14} className="mr-1" />
                            Logs
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            setCampaignToDelete(campaign.campaign_id);
                            setDeleteDialogOpen(true);
                          }}
                          disabled={campaign.status === "running"}
                          data-testid={`delete-campaign-${campaign.campaign_id}`}
                        >
                          <Trash2 size={18} className="text-slate-400 hover:text-red-500" />
                        </Button>
                      </div>
                    </div>
                  </motion.div>
                ))}
              </div>
            ) : (
              <div className="p-12 text-center">
                <Send size={32} className="mx-auto mb-3 text-slate-300" />
                <p className="text-slate-500 mb-4">No campaigns yet</p>
                <Button
                  onClick={() => {
                    resetForm();
                    setView("create");
                  }}
                  className="bg-electric-blue hover:bg-blue-700"
                >
                  Create Your First Campaign
                </Button>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Delete Confirmation */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading font-semibold">
              Delete Campaign
            </AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete this campaign? This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="cancel-delete-btn">
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDeleteCampaign}
              className="bg-red-600 hover:bg-red-700"
              data-testid="confirm-delete-btn"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
