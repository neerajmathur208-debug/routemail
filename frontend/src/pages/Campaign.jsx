import { useState, useEffect, useCallback, useRef } from "react";
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
  TestTube,
  Plus,
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
import AccountMultiSelect from "../components/AccountMultiSelect";
import { api } from "../App";
import { toast } from "sonner";
import useAutoSaveDraft from "../hooks/useAutoSaveDraft";

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
  const [testEmailAccountId, setTestEmailAccountId] = useState(""); // Selected account for test email
  const [testRecipientId, setTestRecipientId] = useState(""); // Selected contact row index from list
  const [sendingTestEmail, setSendingTestEmail] = useState(false);

  // Scheduler state with timezone
  const [sendOption, setSendOption] = useState("now"); // "now" or "schedule"
  const [scheduleDate, setScheduleDate] = useState("");
  const [scheduleTime, setScheduleTime] = useState("");
  const [selectedTimezone, setSelectedTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone);

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
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    suppression_list_ids: [],
    send_range_mode: "all",
    send_range_start: 1,
    send_range_end: 100,
    add_unsubscribe_footer: false,
  });
  const [dneLists, setDneLists] = useState([]);

  const fetchData = useCallback(async () => {
    try {
      const [listsRes, accountsRes, campaignsRes, dneRes] = await Promise.all([
        api.get("/lists"),
        api.get("/accounts"),
        api.get("/campaigns"),
        api.get("/dne-lists"),
      ]);

      setLists(listsRes.data);
      // Handle accounts response - API returns { accounts: [], limit_info: {} }
      const accountsData = accountsRes.data?.accounts || accountsRes.data || [];
      setAccounts(Array.isArray(accountsData) ? accountsData : []);
      setCampaigns(campaignsRes.data);
      setDneLists(dneRes.data || []);

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
            suppression_list_ids: campaign.suppression_list_ids || [],
            send_range_mode: campaign.send_range_mode || "all",
            send_range_start: campaign.send_range_start || 1,
            send_range_end: campaign.send_range_end || 100,
            add_unsubscribe_footer: campaign.add_unsubscribe_footer || false,
          });
          setView("edit");
          
          // If campaign has scheduled_at, set schedule mode using campaign's stored timezone
          if (campaign.scheduled_at) {
            setSendOption("schedule");
            const campaignTz = campaign.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone;
            setSelectedTimezone(campaignTz);
            // Render stored UTC back into the campaign's selected timezone (sv-SE locale → ISO-like)
            try {
              const localStr = new Date(campaign.scheduled_at).toLocaleString("sv-SE", {
                timeZone: campaignTz,
              }); // e.g. "2027-01-15 09:00:00"
              const [d, t] = localStr.split(" ");
              setScheduleDate(d);
              setScheduleTime((t || "00:00:00").slice(0, 5));
            } catch {
              const dt = new Date(campaign.scheduled_at);
              setScheduleDate(dt.toISOString().split("T")[0]);
              setScheduleTime(dt.toTimeString().slice(0, 5));
            }
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
    // Handle special "add_new_list" option
    if (listId === "add_new_list") {
      // Auto-save campaign as draft first
      if (formData.name || formData.subject || formData.body) {
        try {
          if (editId) {
            await api.put(`/campaigns/${editId}`, formData);
            toast.success("Campaign saved as draft");
          } else if (formData.name && formData.subject) {
            const response = await api.post("/campaigns", formData);
            toast.success("Campaign saved as draft");
            // Store the campaign ID to return to after list upload
            sessionStorage.setItem("returnToCampaign", response.data.campaign_id);
          }
        } catch (error) {
          console.error("Failed to auto-save:", error);
        }
      }
      // Store current campaign ID to return after uploading
      if (editId) {
        sessionStorage.setItem("returnToCampaign", editId);
      }
      navigate("/upload");
      return;
    }
    
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

  const handleDneToggle = (listId) => {
    const cur = formData.suppression_list_ids || [];
    const next = cur.includes(listId)
      ? cur.filter((id) => id !== listId)
      : [...cur, listId];
    setFormData({ ...formData, suppression_list_ids: next });
  };

  const handleSaveCampaign = async () => {
    if (!formData.name || !formData.subject || !formData.body) {
      toast.error("Please fill in campaign name, subject, and body");
      return;
    }

    // Build scheduled_at: send as a NAIVE local datetime string in the user's selected timezone.
    // Backend will localize using `timezone` and convert to UTC (no browser-tz leakage).
    let scheduled_at = null;
    if (sendOption === "schedule" && scheduleDate && scheduleTime) {
      // Lightweight future-time check (in the selected timezone). We don't need
      // absolute precision here — the backend will re-validate.
      const nowLocalISO = new Date().toLocaleString("sv-SE", { timeZone: selectedTimezone }).replace(" ", "T");
      const chosenISO = `${scheduleDate}T${scheduleTime}:00`;
      if (chosenISO <= nowLocalISO) {
        toast.error("Scheduled time must be in the future");
        return;
      }
      scheduled_at = chosenISO; // naive local time in selectedTimezone
    }

    const payload = {
      ...formData,
      scheduled_at: scheduled_at || "",
      timezone: selectedTimezone,
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

  // Internal: silent draft save used by auto-save on back / before send
  // Returns the campaign_id (existing edit id, or new one), or null when nothing meaningful to save.
  const autoSaveDraft = useCallback(async ({ silent = false } = {}) => {
    // Don't autosave a completely empty form
    if (!formData.name && !formData.subject && !formData.body) return null;
    const payload = {
      ...formData,
      scheduled_at: "",
      timezone: selectedTimezone,
    };
    try {
      if (editId) {
        await api.put(`/campaigns/${editId}`, payload);
        if (!silent) toast.success("Draft saved automatically");
        return editId;
      }
      // Create requires at least name+subject; silently skip otherwise
      if (!formData.name || !formData.subject) return null;
      const res = await api.post("/campaigns", payload);
      if (!silent) toast.success("Draft saved automatically");
      return res.data?.campaign_id || null;
    } catch (err) {
      console.error("Auto-save failed:", err);
      return null;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formData, selectedTimezone, editId]);

  // Trigger silent auto-save when the user navigates away (back button / route change / tab close)
  // while in create or edit view AND there are unsaved changes.
  const inEditor = view === "create" || view === "edit";
  const initialFormSnapshotRef = useRef(null);
  useEffect(() => {
    if (!inEditor) {
      initialFormSnapshotRef.current = null;
      return;
    }
    if (initialFormSnapshotRef.current === null) {
      initialFormSnapshotRef.current = JSON.stringify(formData);
    }
  }, [inEditor, formData]);
  const isDirtyForAutosave =
    inEditor &&
    initialFormSnapshotRef.current !== null &&
    JSON.stringify(formData) !== initialFormSnapshotRef.current;
  useAutoSaveDraft(() => autoSaveDraft({ silent: true }), isDirtyForAutosave);

  // Send Now - auto-save campaign first, then immediately start
  const handleSendNow = async (campaignId) => {
    try {
      // Persist any unsaved edits (subject/body/account/list/etc.) before starting
      const payload = {
        ...formData,
        scheduled_at: "",
        timezone: selectedTimezone,
      };
      let targetId = campaignId;
      try {
        if (targetId) {
          await api.put(`/campaigns/${targetId}`, payload);
        } else if (formData.name && formData.subject) {
          const res = await api.post("/campaigns", payload);
          targetId = res.data?.campaign_id;
        }
      } catch (saveErr) {
        const msg = saveErr.response?.data?.detail || "Failed to save campaign before sending";
        toast.error(msg);
        return;
      }
      if (!targetId) {
        toast.error("Could not save campaign — please fill in name and subject first.");
        return;
      }
      await api.post(`/campaigns/${targetId}/start`);
      toast.success("Campaign saved & started successfully!");
      setStartDialogOpen(false);
      setView("list");
      navigate("/campaign"); // Redirect to All Campaigns
    } catch (error) {
      const message = error.response?.data?.detail || "Failed to start campaign";
      toast.error(message);
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

    // Validate in selected timezone (not browser tz)
    const nowLocalISO = new Date()
      .toLocaleString("sv-SE", { timeZone: selectedTimezone })
      .replace(" ", "T");
    const chosenISO = `${scheduleDate}T${scheduleTime}:00`;
    if (chosenISO <= nowLocalISO) {
      toast.error("Scheduled time must be in the future");
      return;
    }

    try {
      // Send naive local datetime + timezone; backend converts to UTC using pytz
      await api.put(`/campaigns/${campaignId}`, {
        ...formData,
        scheduled_at: chosenISO,
        timezone: selectedTimezone,
      });
      
      // Then schedule it
      await api.post(`/campaigns/${campaignId}/schedule`);
      toast.success("Campaign saved & scheduled successfully");
      setStartDialogOpen(false);
      setView("list");
      navigate("/campaign"); // Redirect to All Campaigns
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

  // Send Test Email function
  const handleSendTestEmail = async () => {
    // Validate
    if (!testEmailAddress) {
      toast.error("Please enter a test email address");
      return;
    }
    if (!formData.subject) {
      toast.error("Please enter a subject line");
      return;
    }
    if (!formData.body) {
      toast.error("Please enter email content");
      return;
    }
    if (!hasAccounts) {
      toast.error("Please connect at least one email account first");
      return;
    }
    if (!testEmailAccountId) {
      toast.error("Please select an email account to send from");
      return;
    }

    setSendingTestEmail(true);
    try {
      // If user picked a contact, send their row data so {{vars}} get merged
      let recipientData = null;
      if (testRecipientId !== "" && selectedList?.emails) {
        const idx = parseInt(testRecipientId, 10);
        if (!Number.isNaN(idx) && selectedList.emails[idx]) {
          recipientData = selectedList.emails[idx];
        }
      }
      const response = await api.post("/campaigns/send-test", {
        test_email: testEmailAddress,
        subject: formData.subject,
        body: formData.body,
        from_name: formData.from_name || null,
        account_id: testEmailAccountId, // Send selected account
        recipient_data: recipientData,
      });
      
      if (response.data?.success) {
        toast.success("Test email sent successfully!");
      } else {
        toast.success(`Test email sent to ${testEmailAddress}`);
      }
      setTestEmailDialogOpen(false);
      setTestEmailAddress("");
      setTestRecipientId("");
    } catch (error) {
      const message = error.response?.data?.detail || "Failed to send test email";
      toast.error(message);
    } finally {
      setSendingTestEmail(false);
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
      suppression_list_ids: [],
    });
    setSelectedList(null);
    setSendOption("now");
    setScheduleDate("");
    setScheduleTime("");
  };

  const hasAccounts = accounts.length > 0;
  const hasLists = lists.length > 0;

  // Compute total daily sending capacity:
  // - If specific accounts selected → sum their daily_limits.
  // - If empty (= "use all connected accounts") → sum daily_limits of all connected accounts.
  const totalDailyCapacity = (() => {
    const connected = accounts.filter((a) => a.status === "connected" || !a.status);
    const pool =
      formData.account_ids && formData.account_ids.length > 0
        ? connected.filter((a) => formData.account_ids.includes(a.account_id))
        : connected;
    return pool.reduce((sum, a) => sum + (parseInt(a.daily_limit, 10) || 0), 0);
  })();
  const dailyCapacityCount =
    formData.account_ids.length > 0 ? formData.account_ids.length : accounts.length;

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
                onClick={async () => {
                  await autoSaveDraft();
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
                <Label htmlFor="name" className="text-violet-700">Campaign Name *</Label>
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
                <Label htmlFor="from_name" className="text-indigo-700">From Name (optional)</Label>
                <Input
                  id="from_name"
                  placeholder="John Doe"
                  value={formData.from_name}
                  onChange={(e) => setFormData({ ...formData, from_name: e.target.value })}
                  className="mt-1.5"
                  data-testid="from-name-input"
                />
                <p className="text-xs text-slate-500 mt-1">
                  If provided, this From Name will override individual email account sender names for this campaign. Leave blank to use each account's default From Name.
                </p>
              </div>

              {/* Email Accounts Selection */}
              <div>
                <Label className="text-blue-700">Select Email Accounts (optional)</Label>
                <p className="text-xs text-slate-500 mb-2">
                  Leave empty to use all connected accounts. Use search to quickly find accounts.
                </p>
                <AccountMultiSelect
                  accounts={accounts}
                  value={formData.account_ids}
                  onChange={(next) => setFormData({ ...formData, account_ids: next })}
                  testIdPrefix="campaign-accounts"
                  placeholder={accounts.length === 0 ? "No accounts connected yet" : "All connected accounts"}
                />
                {hasAccounts && (
                  <div
                    className="mt-2 inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-medium"
                    data-testid="total-daily-capacity"
                  >
                    <Send size={12} />
                    Total Daily Sending Capacity:&nbsp;
                    <span className="font-bold">{totalDailyCapacity.toLocaleString()}</span>
                    &nbsp;emails/day
                    <span className="text-emerald-600 font-normal ml-1">
                      ({dailyCapacityCount} account{dailyCapacityCount === 1 ? "" : "s"})
                    </span>
                  </div>
                )}
              </div>

              {/* Do Not Email Lists */}
              <div>
                <Label className="text-rose-700">Do Not Email Lists (optional)</Label>
                <p className="text-xs text-slate-500 mb-2">
                  Pick the lists this campaign should be checked against. Permanent unsubscribes
                  (anyone who clicked an unsubscribe link) are always blocked regardless.
                </p>
                <div className="space-y-2 mt-1.5">
                  {dneLists.length === 0 && (
                    <p className="text-sm text-slate-500">
                      No Do Not Email lists yet.{" "}
                      <button
                        type="button"
                        onClick={() => navigate("/do-not-email")}
                        className="text-blue-600 underline"
                      >
                        Manage suppression lists
                      </button>
                    </p>
                  )}
                  {dneLists.map((dne) => (
                    <div
                      key={dne.list_id}
                      className={`flex items-center gap-3 p-3 border rounded-md ${
                        dne.is_global
                          ? "border-rose-200 bg-rose-50/30"
                          : "border-slate-200"
                      }`}
                    >
                      <Checkbox
                        id={`dne-${dne.list_id}`}
                        checked={(formData.suppression_list_ids || []).includes(dne.list_id)}
                        onCheckedChange={() => handleDneToggle(dne.list_id)}
                        data-testid={`dne-checkbox-${dne.list_id}`}
                      />
                      <label
                        htmlFor={`dne-${dne.list_id}`}
                        className="flex-1 cursor-pointer"
                      >
                        <p className="font-medium text-slate-900 flex items-center gap-2">
                          {dne.name}
                          {dne.is_global && (
                            <span className="text-[10px] uppercase tracking-wide bg-rose-100 text-rose-700 px-2 py-0.5 rounded-full">
                              Global
                            </span>
                          )}
                        </p>
                        <p className="text-xs text-slate-500">
                          {dne.email_count || 0} suppressed email
                          {dne.email_count === 1 ? "" : "s"}
                        </p>
                      </label>
                    </div>
                  ))}
                  {dneLists.length > 0 && (formData.suppression_list_ids || []).length === 0 && (
                    <div
                      className="flex items-start gap-2 p-3 border border-amber-200 bg-amber-50 rounded-md text-amber-800 text-sm"
                      data-testid="dne-no-selection-warning"
                    >
                      <AlertCircle size={16} className="mt-0.5 shrink-0" />
                      <span>
                        No unsubscribe list selected. Emails will not be checked against any
                        suppression lists (permanent unsubscribes are always blocked).
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Email List Selection */}
              <div>
                <Label className="text-emerald-700">Select Email List *</Label>
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
                    <SelectItem 
                      value="add_new_list" 
                      className="text-blue-600 font-medium border-t border-slate-100 mt-1 pt-1"
                      data-testid="add-new-list-option"
                    >
                      <span className="flex items-center gap-2">
                        <Plus size={14} />
                        Add New List
                      </span>
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {/* Send Range */}
              <div data-testid="send-range-section">
                <Label className="text-cyan-700">Send Range</Label>
                <p className="text-xs text-slate-500 mb-2 mt-0.5">
                  Choose to send to all contacts in the list, or only to a subset (1-based, inclusive).
                </p>
                <div className="flex items-center gap-4 mb-2">
                  <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                    <input
                      type="radio"
                      name="send_range_mode"
                      value="all"
                      checked={(formData.send_range_mode || "all") === "all"}
                      onChange={() => setFormData({ ...formData, send_range_mode: "all" })}
                      data-testid="send-range-all-radio"
                    />
                    <span>All contacts{selectedList ? ` (${selectedList.valid_emails || 0})` : ""}</span>
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                    <input
                      type="radio"
                      name="send_range_mode"
                      value="range"
                      checked={formData.send_range_mode === "range"}
                      onChange={() => setFormData({ ...formData, send_range_mode: "range" })}
                      data-testid="send-range-range-radio"
                    />
                    <span>Custom range</span>
                  </label>
                </div>
                {formData.send_range_mode === "range" && (
                  <div className="flex items-center gap-3 mt-1">
                    <div className="flex items-center gap-2">
                      <Label htmlFor="send-range-start" className="text-xs text-slate-500">From</Label>
                      <Input
                        id="send-range-start"
                        type="number"
                        min={1}
                        value={formData.send_range_start || 1}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            send_range_start: Math.max(1, parseInt(e.target.value || "1", 10)),
                          })
                        }
                        className="w-28"
                        data-testid="send-range-start-input"
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <Label htmlFor="send-range-end" className="text-xs text-slate-500">To</Label>
                      <Input
                        id="send-range-end"
                        type="number"
                        min={1}
                        value={formData.send_range_end || 1}
                        onChange={(e) =>
                          setFormData({
                            ...formData,
                            send_range_end: Math.max(1, parseInt(e.target.value || "1", 10)),
                          })
                        }
                        className="w-28"
                        data-testid="send-range-end-input"
                      />
                    </div>
                    {selectedList && (
                      <span className="text-xs text-slate-400">
                        of {selectedList.valid_emails || 0} valid contacts
                      </span>
                    )}
                  </div>
                )}
              </div>

              {/* Subject Line */}
              <div>
                <Label htmlFor="subject" className="text-blue-700">Subject Line *</Label>
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
                  <Label className="text-violet-700">Email Body *</Label>
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

              {/* Actions Below Editor - Save Campaign & Send Test Email */}
              <div className="flex flex-wrap items-center gap-3 py-4 border-t border-slate-100">
                <Button
                  variant="outline"
                  onClick={handleSaveCampaign}
                  disabled={submitting}
                  data-testid="save-campaign-btn"
                >
                  <Save size={16} className="mr-2" />
                  {submitting ? "Saving..." : "Save Campaign"}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setTestEmailDialogOpen(true)}
                  disabled={!hasAccounts || !formData.subject || !formData.body}
                  data-testid="send-test-email-btn"
                  className="text-blue-600 border-blue-200 hover:bg-blue-50 hover:text-blue-700"
                >
                  <TestTube size={16} className="mr-2" />
                  Send Test Email
                </Button>
              </div>

              {/* Sending Options */}
              <div className="border-t border-slate-100 pt-6">
                <div className="flex items-start gap-3 mb-4 p-3 bg-slate-50 rounded-lg" data-testid="add-unsubscribe-footer-toggle">
                  <input
                    id="add-unsub-footer"
                    type="checkbox"
                    className="mt-0.5"
                    checked={!!formData.add_unsubscribe_footer}
                    onChange={(e) =>
                      setFormData({ ...formData, add_unsubscribe_footer: e.target.checked })
                    }
                    data-testid="add-unsubscribe-footer-checkbox"
                  />
                  <label htmlFor="add-unsub-footer" className="text-sm cursor-pointer flex-1">
                    <span className="font-medium text-slate-900">Add Unsubscribe Footer</span>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Off by default. When enabled, an unobtrusive "Unsubscribe" footer
                      is appended to every email. You can also insert the link inline
                      using the editor's Unsubscribe button.
                    </p>
                  </label>
                </div>
                <Label className="mb-3 block text-amber-700">Sending Options</Label>
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
                    <div className="mt-4">
                      <Label htmlFor="timezone" className="text-sm">Timezone</Label>
                      <Select value={selectedTimezone} onValueChange={setSelectedTimezone}>
                        <SelectTrigger className="mt-1.5" data-testid="timezone-select">
                          <SelectValue placeholder="Select timezone" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="America/New_York">Eastern Time (US & Canada)</SelectItem>
                          <SelectItem value="America/Chicago">Central Time (US & Canada)</SelectItem>
                          <SelectItem value="America/Denver">Mountain Time (US & Canada)</SelectItem>
                          <SelectItem value="America/Los_Angeles">Pacific Time (US & Canada)</SelectItem>
                          <SelectItem value="America/Phoenix">Arizona Time</SelectItem>
                          <SelectItem value="Europe/London">London (GMT/BST)</SelectItem>
                          <SelectItem value="Europe/Paris">Paris (CET/CEST)</SelectItem>
                          <SelectItem value="Europe/Berlin">Berlin (CET/CEST)</SelectItem>
                          <SelectItem value="Europe/Dublin">Dublin (IST)</SelectItem>
                          <SelectItem value="Asia/Kolkata">India (IST)</SelectItem>
                          <SelectItem value="Asia/Dubai">Dubai (GST)</SelectItem>
                          <SelectItem value="Asia/Singapore">Singapore (SGT)</SelectItem>
                          <SelectItem value="Asia/Tokyo">Tokyo (JST)</SelectItem>
                          <SelectItem value="Australia/Sydney">Sydney (AEST)</SelectItem>
                          <SelectItem value="Pacific/Auckland">Auckland (NZST)</SelectItem>
                          <SelectItem value="UTC">UTC</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <p className="text-xs text-slate-500 mt-3 flex items-center gap-1">
                      <Clock size={12} />
                      Campaign will be sent at the selected time in your chosen timezone
                    </p>
                  </motion.div>
                )}
              </div>

              {/* Rotation Info */}
              <div className="flex items-center gap-2 text-sm text-slate-500 py-3 border-t border-slate-100">
                <RotateCw size={16} />
                <span>
                  {formData.account_ids.length > 0 
                    ? `Will rotate across ${formData.account_ids.length} selected account${formData.account_ids.length > 1 ? "s" : ""}`
                    : `Will rotate across all ${accounts.length} account${accounts.length !== 1 ? "s" : ""}`
                  }
                </span>
              </div>

              {/* Primary Campaign Action Button - At Bottom */}
              <div className="pt-4 border-t border-slate-200">
                {view === "edit" && (
                  <Button
                    onClick={() => setStartDialogOpen(true)}
                    disabled={submitting || !formData.list_id || !hasAccounts || !hasLists || !formData.subject || !formData.body}
                    className={`w-full py-6 text-base font-semibold ${
                      sendOption === "schedule" 
                        ? "bg-blue-600 hover:bg-blue-700" 
                        : "bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600"
                    }`}
                    data-testid="primary-campaign-btn"
                    title={!hasAccounts || !hasLists ? "Complete setup to launch campaign" : ""}
                  >
                    {sendOption === "schedule" ? (
                      <>
                        <CalendarClock size={20} className="mr-2" />
                        Schedule Now
                      </>
                    ) : (
                      <>
                        <Send size={20} className="mr-2" />
                        Send Now
                      </>
                    )}
                  </Button>
                )}
                {view === "create" && (
                  <Button
                    onClick={handleSaveCampaign}
                    disabled={submitting}
                    className="w-full py-6 text-base font-semibold bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700"
                    data-testid="create-campaign-btn-bottom"
                  >
                    <Save size={20} className="mr-2" />
                    {submitting ? "Creating..." : "Create Campaign"}
                  </Button>
                )}
              </div>
            </div>
          </div>
        </main>

        {/* Send Test Email Dialog */}
        <AlertDialog open={testEmailDialogOpen} onOpenChange={setTestEmailDialogOpen}>
          <AlertDialogContent className="max-w-md">
            <AlertDialogHeader>
              <AlertDialogTitle className="flex items-center gap-2">
                <TestTube size={20} className="text-blue-600" />
                Send Test Email
              </AlertDialogTitle>
              <AlertDialogDescription>
                Send a preview of your email without affecting campaign stats.
              </AlertDialogDescription>
            </AlertDialogHeader>
            <div className="py-4 space-y-4">
              <div>
                <Label htmlFor="test-email-account">Send From Account</Label>
                <Select
                  value={testEmailAccountId}
                  onValueChange={setTestEmailAccountId}
                >
                  <SelectTrigger className="mt-1.5" data-testid="test-email-account-select">
                    <SelectValue placeholder="Select account" />
                  </SelectTrigger>
                  <SelectContent>
                    {accounts.map((acc) => (
                      <SelectItem key={acc.account_id} value={acc.account_id}>
                        {acc.email} ({acc.display_name || acc.smtp_host})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label htmlFor="test-email">Test Email Address</Label>
                <Input
                  id="test-email"
                  type="email"
                  placeholder="you@example.com"
                  value={testEmailAddress}
                  onChange={(e) => setTestEmailAddress(e.target.value)}
                  className="mt-1.5"
                  data-testid="test-email-input"
                />
              </div>
              <div>
                <Label htmlFor="test-recipient">Personalize with contact (optional)</Label>
                <Select
                  value={testRecipientId}
                  onValueChange={setTestRecipientId}
                  disabled={!selectedList?.emails?.length}
                >
                  <SelectTrigger className="mt-1.5" data-testid="test-email-recipient-select">
                    <SelectValue placeholder={
                      selectedList?.emails?.length
                        ? "Pick a contact to merge variables (optional)"
                        : "Select an email list first to enable personalization"
                    } />
                  </SelectTrigger>
                  <SelectContent>
                    {(selectedList?.emails || []).slice(0, 200).map((row, idx) => {
                      const label = [row.first_name, row.last_name].filter(Boolean).join(" ").trim();
                      return (
                        <SelectItem key={idx} value={String(idx)}>
                          {row.email}{label ? ` — ${label}` : ""}
                        </SelectItem>
                      );
                    })}
                  </SelectContent>
                </Select>
                {testRecipientId !== "" && selectedList?.emails?.[parseInt(testRecipientId, 10)] && (
                  <p className="text-xs text-emerald-700 mt-1.5" data-testid="test-recipient-preview">
                    Variables will be filled from: {selectedList.emails[parseInt(testRecipientId, 10)].email}
                  </p>
                )}
                {!selectedList?.emails?.length && (
                  <p className="text-xs text-amber-600 mt-1.5">
                    No contact selected — variables like {"{{first_name}}"} will be sent as-is.
                  </p>
                )}
              </div>
              <p className="text-xs text-slate-500">
                The test email will include a "[TEST]" prefix in the subject line.
              </p>
            </div>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={sendingTestEmail}>Cancel</AlertDialogCancel>
              <Button
                onClick={handleSendTestEmail}
                disabled={sendingTestEmail || !testEmailAddress || !testEmailAccountId}
                className="bg-blue-600 hover:bg-blue-700"
              >
                {sendingTestEmail ? (
                  <>
                    <RefreshCw size={16} className="mr-2 animate-spin" />
                    Sending...
                  </>
                ) : (
                  <>
                    <Send size={16} className="mr-2" />
                    Send Test
                  </>
                )}
              </Button>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

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
                  onClick={() => handleSendNow(editId)}
                  className="bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600"
                  data-testid="confirm-start-btn"
                >
                  <Send size={16} className="mr-2" />
                  Send Now
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
                          <>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => navigate(`/campaign/${campaign.campaign_id}/view`)}
                              data-testid={`view-campaign-${campaign.campaign_id}`}
                              className="text-slate-600 hover:text-violet-600"
                            >
                              <Eye size={14} className="mr-1" />
                              View
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => navigate(`/campaign/${campaign.campaign_id}/logs`)}
                              data-testid={`view-logs-${campaign.campaign_id}`}
                            >
                              <FileText size={14} className="mr-1" />
                              Logs
                            </Button>
                          </>
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
