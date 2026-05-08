import { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Plus,
  Trash2,
  Save,
  Play,
  Pause,
  Users,
  Workflow,
  Clock,
  Download,
  AlertCircle,
  CheckCircle2,
  Mail,
  Settings,
  Copy,
  TestTube,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Checkbox } from "../components/ui/checkbox";
import { Switch } from "../components/ui/switch";
import RichTextEditor from "../components/RichTextEditor";
import AccountMultiSelect from "../components/AccountMultiSelect";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import {
  Tabs,
  TabsList,
  TabsTrigger,
  TabsContent,
} from "../components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "../components/ui/dialog";
import Sidebar from "../components/Sidebar";
import { api, API } from "../App";
import { toast } from "sonner";

const COMMON_TIMEZONES = [
  "UTC",
  "America/Los_Angeles",
  "America/Denver",
  "America/Chicago",
  "America/New_York",
  "America/Sao_Paulo",
  "Europe/London",
  "Europe/Berlin",
  "Europe/Paris",
  "Europe/Madrid",
  "Asia/Dubai",
  "Asia/Kolkata",
  "Asia/Singapore",
  "Asia/Tokyo",
  "Australia/Sydney",
];

const DAYS = [
  { id: 0, label: "Mon" },
  { id: 1, label: "Tue" },
  { id: 2, label: "Wed" },
  { id: 3, label: "Thu" },
  { id: 4, label: "Fri" },
  { id: 5, label: "Sat" },
  { id: 6, label: "Sun" },
];

const STATUS_STYLES = {
  draft: "bg-slate-100 text-slate-700",
  running: "bg-emerald-100 text-emerald-700",
  paused: "bg-amber-100 text-amber-700",
  completed: "bg-blue-100 text-blue-700",
};

export default function DripCampaignView({ user, setUser }) {
  const { dripId } = useParams();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [campaign, setCampaign] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [lists, setLists] = useState([]);
  const [tab, setTab] = useState("contacts");

  // Drip step Test-Mail dialog state
  const [stepTestOpen, setStepTestOpen] = useState(false);
  const [stepTestIdx, setStepTestIdx] = useState(null);
  const [stepTestEmail, setStepTestEmail] = useState("");
  const [stepTestAccountId, setStepTestAccountId] = useState("");
  const [stepTestRecipientIdx, setStepTestRecipientIdx] = useState("");
  const [stepTestListId, setStepTestListId] = useState("");
  const [stepTestListData, setStepTestListData] = useState(null);
  const [sendingStepTest, setSendingStepTest] = useState(false);

  // Editable state
  const [form, setForm] = useState({
    name: "",
    from_name: "",
    account_ids: [],
    steps: [],
    schedule: {
      timezone: "UTC",
      sending_days: [0, 1, 2, 3, 4],
      start_time: "09:00",
      end_time: "18:00",
      randomize_time: false,
    },
    stop_on_reply: true,
    stop_on_bounce: true,
    suppression_list_ids: [],
  });

  const [dneLists, setDneLists] = useState([]);

  // Contacts/logs
  const [contacts, setContacts] = useState([]);
  const [logs, setLogs] = useState([]);
  const [addContactsOpen, setAddContactsOpen] = useState(false);
  const [selectedList, setSelectedList] = useState("");
  const [addingContacts, setAddingContacts] = useState(false);
  const [sendRangeMode, setSendRangeMode] = useState("all");
  const [sendRangeStart, setSendRangeStart] = useState(1);
  const [sendRangeEnd, setSendRangeEnd] = useState(100);

  const loadAll = useCallback(async () => {
    try {
      const [campRes, accRes, listsRes, contactsRes, logsRes, dneRes] = await Promise.all([
        api.get(`/drip-campaigns/${dripId}`),
        api.get("/accounts"),
        api.get("/lists"),
        api.get(`/drip-campaigns/${dripId}/contacts?limit=100`),
        api.get(`/drip-campaigns/${dripId}/logs?limit=100`),
        api.get("/dne-lists"),
      ]);
      const camp = campRes.data;
      setCampaign(camp);
      setForm({
        name: camp.name || "",
        from_name: camp.from_name || "",
        account_ids: camp.account_ids || [],
        steps: camp.steps || [],
        schedule: {
          timezone: camp.schedule?.timezone || "UTC",
          sending_days: camp.schedule?.sending_days || [0, 1, 2, 3, 4],
          start_time: camp.schedule?.start_time || "09:00",
          end_time: camp.schedule?.end_time || "18:00",
          randomize_time: camp.schedule?.randomize_time || false,
        },
        stop_on_reply: camp.stop_on_reply !== false,
        stop_on_bounce: camp.stop_on_bounce !== false,
        suppression_list_ids: camp.suppression_list_ids || [],
      });
      const accountsData = accRes.data?.accounts || accRes.data || [];
      setAccounts(Array.isArray(accountsData) ? accountsData : []);
      setLists(listsRes.data || []);
      setContacts(contactsRes.data?.contacts || []);
      setLogs(logsRes.data?.logs || []);
      setDneLists(dneRes.data || []);
    } catch (e) {
      console.error(e);
      toast.error("Failed to load drip campaign");
      navigate("/drip-campaigns");
    } finally {
      setLoading(false);
    }
  }, [dripId, navigate]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const isRunning = campaign?.status === "running";
  const canEdit = !isRunning;

  // Variables available to merge into subject/body — derived from enrolled contact fields
  const availableVariables = (() => {
    const set = new Set(["email"]);
    for (const c of contacts) {
      const data = c?.data || {};
      Object.keys(data).forEach((k) => k && set.add(k));
    }
    return Array.from(set);
  })();

  const addStep = () => {
    setForm((prev) => ({
      ...prev,
      steps: [
        ...prev.steps,
        {
          step_number: prev.steps.length + 1,
          subject: "",
          body: "",
          delay_days: prev.steps.length === 0 ? 0 : 2,
          delay_hours: 0,
        },
      ],
    }));
  };

  const updateStep = (idx, field, value) => {
    setForm((prev) => {
      const steps = [...prev.steps];
      steps[idx] = { ...steps[idx], [field]: value };
      return { ...prev, steps };
    });
  };

  const removeStep = (idx) => {
    setForm((prev) => ({
      ...prev,
      steps: prev.steps.filter((_, i) => i !== idx),
    }));
  };

  const duplicateStep = (idx) => {
    setForm((prev) => {
      const src = prev.steps[idx];
      if (!src) return prev;
      const copy = {
        ...src,
        step_number: idx + 2,
        // Default delay for the duplicate (1 day after the previous step). Users can edit.
        delay_days: src.delay_days ?? 1,
        delay_hours: src.delay_hours ?? 0,
      };
      const newSteps = [...prev.steps];
      newSteps.splice(idx + 1, 0, copy);
      // Re-number steps
      return {
        ...prev,
        steps: newSteps.map((s, i) => ({ ...s, step_number: i + 1 })),
      };
    });
    toast.success("Step duplicated");
  };

  const openStepTest = async (idx) => {
    setStepTestIdx(idx);
    setStepTestEmail("");
    setStepTestRecipientIdx("");
    // Default to first connected account
    const firstAcc = (accounts || []).find((a) => !a.status || a.status === "connected");
    setStepTestAccountId(firstAcc?.account_id || "");
    // Default to first email list
    const firstList = (lists || [])[0];
    if (firstList) {
      setStepTestListId(firstList.list_id);
      try {
        const res = await api.get(`/lists/${firstList.list_id}`);
        setStepTestListData(res.data);
      } catch (err) {
        setStepTestListData(null);
      }
    } else {
      setStepTestListId("");
      setStepTestListData(null);
    }
    setStepTestOpen(true);
  };

  const onStepTestListChange = async (listId) => {
    setStepTestListId(listId);
    setStepTestRecipientIdx("");
    if (!listId) {
      setStepTestListData(null);
      return;
    }
    try {
      const res = await api.get(`/lists/${listId}`);
      setStepTestListData(res.data);
    } catch (err) {
      setStepTestListData(null);
    }
  };

  const handleSendStepTest = async () => {
    const step = form.steps[stepTestIdx];
    if (!step) {
      toast.error("Step not found");
      return;
    }
    if (!stepTestEmail) {
      toast.error("Enter a test email address");
      return;
    }
    if (!stepTestAccountId) {
      toast.error("Select an account to send from");
      return;
    }
    if (!step.subject || !step.body) {
      toast.error("Step subject and body are required");
      return;
    }
    let recipientData = null;
    if (stepTestRecipientIdx !== "" && stepTestListData?.emails) {
      const i = parseInt(stepTestRecipientIdx, 10);
      if (!Number.isNaN(i) && stepTestListData.emails[i]) {
        recipientData = stepTestListData.emails[i];
      }
    }
    setSendingStepTest(true);
    try {
      await api.post("/campaigns/send-test", {
        test_email: stepTestEmail,
        subject: step.subject,
        body: step.body,
        from_name: form.from_name || null,
        account_id: stepTestAccountId,
        recipient_data: recipientData,
      });
      toast.success(`Test email sent to ${stepTestEmail}`);
      setStepTestOpen(false);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to send test email");
    } finally {
      setSendingStepTest(false);
    }
  };

  const toggleAccount = (id) => {
    setForm((prev) => ({
      ...prev,
      account_ids: prev.account_ids.includes(id)
        ? prev.account_ids.filter((a) => a !== id)
        : [...prev.account_ids, id],
    }));
  };

  const toggleDay = (dayId) => {
    setForm((prev) => {
      const days = prev.schedule.sending_days.includes(dayId)
        ? prev.schedule.sending_days.filter((d) => d !== dayId)
        : [...prev.schedule.sending_days, dayId].sort((a, b) => a - b);
      return { ...prev, schedule: { ...prev.schedule, sending_days: days } };
    });
  };

  const handleSave = async () => {
    if (!form.name.trim()) {
      toast.error("Name is required");
      return;
    }
    for (let i = 0; i < form.steps.length; i++) {
      const s = form.steps[i];
      if (!s.subject?.trim() || !s.body?.trim()) {
        toast.error(`Step ${i + 1}: subject and body are required`);
        return;
      }
    }
    setSaving(true);
    try {
      await api.put(`/drip-campaigns/${dripId}`, form);
      toast.success("Saved");
      loadAll();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  // Silent auto-save on back/leave. Only runs when editing is allowed AND there's a name.
  const autoSaveDraft = useCallback(async () => {
    if (!campaign || !canEdit) return;
    if (!form.name?.trim()) return;
    // Skip if any step is missing required fields — backend will reject.
    for (const s of form.steps || []) {
      if (!s.subject?.trim() || !s.body?.trim()) return;
    }
    try {
      await api.put(`/drip-campaigns/${dripId}`, form);
      toast.success("Draft saved automatically");
    } catch (err) {
      // Non-fatal — user can manually save later
      console.error("Drip auto-save failed:", err);
    }
  }, [campaign, canEdit, form, dripId]);

  const handleStartPauseResume = async () => {
    try {
      if (campaign.status === "running") {
        await api.post(`/drip-campaigns/${dripId}/pause`);
        toast.success("Paused");
      } else if (campaign.status === "paused") {
        await api.post(`/drip-campaigns/${dripId}/resume`);
        toast.success("Resumed");
      } else {
        await api.post(`/drip-campaigns/${dripId}/start`);
        toast.success("Campaign started");
      }
      loadAll();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Action failed");
    }
  };

  const handleAddContacts = async () => {
    if (!selectedList) {
      toast.error("Select a list");
      return;
    }
    setAddingContacts(true);
    try {
      const payload = { list_id: selectedList };
      if (sendRangeMode === "range") {
        payload.send_range_mode = "range";
        payload.send_range_start = Math.max(1, parseInt(sendRangeStart, 10) || 1);
        payload.send_range_end = Math.max(1, parseInt(sendRangeEnd, 10) || 1);
      }
      const res = await api.post(`/drip-campaigns/${dripId}/contacts`, payload);
      toast.success(
        `Added ${res.data.added} contacts${res.data.skipped_duplicates ? ` (${res.data.skipped_duplicates} duplicates skipped)` : ""}`
      );
      setAddContactsOpen(false);
      setSelectedList("");
      setSendRangeMode("all");
      loadAll();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Failed to add contacts");
    } finally {
      setAddingContacts(false);
    }
  };

  const handleExportLogs = () => {
    window.open(`${API}/drip-campaigns/${dripId}/logs/export`, "_blank");
  };

  if (loading || !campaign) {
    return (
      <div className="min-h-screen bg-slate-50 flex">
        <Sidebar user={user} setUser={setUser} />
        <main className="flex-1 flex items-center justify-center">
          <div className="animate-pulse text-slate-500">Loading…</div>
        </main>
      </div>
    );
  }

  const stats = campaign.stats || {};

  return (
    <div className="min-h-screen bg-slate-50 flex">
      <Sidebar user={user} setUser={setUser} />
      <main className="flex-1 p-6 lg:p-10 max-w-[1400px]">
        <Button
          variant="ghost"
          onClick={async () => {
            await autoSaveDraft();
            navigate("/drip-campaigns");
          }}
          className="mb-4"
          data-testid="drip-back-btn"
        >
          <ArrowLeft size={16} className="mr-2" /> Back to drip campaigns
        </Button>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-6"
        >
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 mb-2">
              <Workflow className="text-violet-600" size={26} strokeWidth={1.5} />
              <Input
                data-testid="drip-name-field"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                disabled={!canEdit}
                className="text-2xl font-bold border-0 shadow-none px-0 focus-visible:ring-0 disabled:opacity-80 disabled:cursor-default"
              />
              <span
                className={`px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  STATUS_STYLES[campaign.status]
                }`}
              >
                {campaign.status}
              </span>
            </div>
            <p className="text-sm text-slate-500">
              Sequence with {form.steps.length} step{form.steps.length === 1 ? "" : "s"} •{" "}
              {stats.total_contacts || 0} contacts
            </p>
          </div>
          <div className="flex gap-2">
            {canEdit && (
              <Button
                onClick={handleSave}
                disabled={saving}
                variant="outline"
                data-testid="drip-save-btn"
              >
                <Save size={16} className="mr-2" /> {saving ? "Saving…" : "Save"}
              </Button>
            )}
            <Button
              onClick={handleStartPauseResume}
              className={
                campaign.status === "running"
                  ? "bg-amber-500 hover:bg-amber-600 text-white"
                  : "bg-violet-600 hover:bg-violet-700 text-white"
              }
              data-testid="drip-control-btn"
            >
              {campaign.status === "running" ? (
                <><Pause size={16} className="mr-2" /> Pause</>
              ) : campaign.status === "paused" ? (
                <><Play size={16} className="mr-2" /> Resume</>
              ) : (
                <><Play size={16} className="mr-2" /> Start campaign</>
              )}
            </Button>
          </div>
        </motion.div>

        {/* Stats strip */}
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-6">
          <StatBlock label="Contacts" value={stats.total_contacts || 0} />
          <StatBlock label="Active" value={stats.active || 0} color="text-emerald-600" />
          <StatBlock label="Completed" value={stats.completed || 0} color="text-blue-600" />
          <StatBlock label="Replied" value={stats.replied || 0} color="text-violet-600" />
          <StatBlock label="Suppressed" value={stats.suppressed || 0} color="text-rose-600" />
          <StatBlock label="Sent" value={stats.emails_sent || 0} color="text-slate-900" />
        </div>

        <Tabs value={tab} onValueChange={setTab} className="w-full">
          <TabsList className="mb-6">
            <TabsTrigger value="contacts" data-testid="tab-contacts">
              Select List ({stats.total_contacts || 0})
            </TabsTrigger>
            <TabsTrigger value="settings" data-testid="tab-settings">Settings</TabsTrigger>
            <TabsTrigger value="sequence" data-testid="tab-sequence">Sequence</TabsTrigger>
            <TabsTrigger value="schedule" data-testid="tab-schedule">Schedule</TabsTrigger>
            <TabsTrigger value="logs" data-testid="tab-logs">Logs</TabsTrigger>
          </TabsList>

          {/* SEQUENCE */}
          <TabsContent value="sequence" className="space-y-4">
            {form.steps.length === 0 && (
              <div className="bg-white border border-dashed border-slate-300 rounded-2xl p-10 text-center">
                <Mail className="mx-auto text-slate-400 mb-3" size={40} strokeWidth={1.2} />
                <h3 className="text-lg font-semibold text-slate-900 mb-1">Build your sequence</h3>
                <p className="text-slate-500 mb-5">
                  Add the first email — step 1 is sent as soon as a contact is enrolled.
                </p>
                <Button
                  onClick={addStep}
                  disabled={!canEdit}
                  className="bg-violet-600 hover:bg-violet-700 text-white"
                  data-testid="drip-add-first-step-btn"
                >
                  <Plus size={16} className="mr-2" /> Add step 1
                </Button>
              </div>
            )}

            {form.steps.map((step, idx) => (
              <div
                key={idx}
                data-testid={`drip-step-${idx}`}
                className="bg-white border border-slate-200 rounded-2xl p-5"
              >
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-violet-100 text-violet-700 font-bold flex items-center justify-center">
                      {idx + 1}
                    </div>
                    <div>
                      <div className="font-semibold text-slate-900">
                        {idx === 0 ? "First email" : `Step ${idx + 1}`}
                      </div>
                      <div className="text-xs text-slate-500">
                        {idx === 0
                          ? "Sends when contact is enrolled"
                          : `Sends ${step.delay_days || 0}d ${step.delay_hours || 0}h after previous step`}
                      </div>
                    </div>
                  </div>
                  {canEdit && (
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-blue-600 hover:text-blue-700 hover:bg-blue-50"
                        onClick={() => openStepTest(idx)}
                        data-testid={`drip-step-${idx}-test-btn`}
                      >
                        <TestTube size={14} className="mr-1" /> Test
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-violet-600 hover:text-violet-700 hover:bg-violet-50"
                        onClick={() => duplicateStep(idx)}
                        data-testid={`drip-step-${idx}-duplicate-btn`}
                      >
                        <Copy size={14} className="mr-1" /> Duplicate
                      </Button>
                      {form.steps.length > 1 && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-red-500 hover:text-red-600 hover:bg-red-50"
                          onClick={() => removeStep(idx)}
                          data-testid={`drip-remove-step-${idx}`}
                        >
                          <Trash2 size={14} />
                        </Button>
                      )}
                    </div>
                  )}
                </div>

                {idx > 0 && (
                  <div className="grid grid-cols-2 gap-3 mb-4">
                    <div>
                      <Label className="text-xs">Delay (days)</Label>
                      <Input
                        type="number"
                        min="0"
                        value={step.delay_days || 0}
                        onChange={(e) => updateStep(idx, "delay_days", parseInt(e.target.value || "0"))}
                        disabled={!canEdit}
                        data-testid={`drip-step-${idx}-days`}
                      />
                    </div>
                    <div>
                      <Label className="text-xs">Delay (hours)</Label>
                      <Input
                        type="number"
                        min="0"
                        max="23"
                        value={step.delay_hours || 0}
                        onChange={(e) => updateStep(idx, "delay_hours", parseInt(e.target.value || "0"))}
                        disabled={!canEdit}
                        data-testid={`drip-step-${idx}-hours`}
                      />
                    </div>
                  </div>
                )}

                <div className="space-y-3">
                  <div>
                    <Label className="text-xs">Subject</Label>
                    <Input
                      value={step.subject || ""}
                      onChange={(e) => updateStep(idx, "subject", e.target.value)}
                      placeholder="Quick question, {first_name}?"
                      disabled={!canEdit}
                      data-testid={`drip-step-${idx}-subject`}
                    />
                  </div>
                  <div>
                    <Label className="text-xs">Body</Label>
                    <RichTextEditor
                      value={step.body || ""}
                      onChange={(value) => updateStep(idx, "body", value)}
                      placeholder={"Hi {first_name},\n\nQuick thought…\n\nBest regards"}
                      variables={availableVariables}
                    />
                    <p className="text-xs text-slate-500 mt-1">
                      Use {"{column_name}"} to merge contact fields from your list (e.g. {"{first_name}"}).
                    </p>
                  </div>
                </div>
              </div>
            ))}

            {form.steps.length > 0 && canEdit && (
              <Button
                onClick={addStep}
                variant="outline"
                className="w-full border-dashed"
                data-testid="drip-add-step-btn"
              >
                <Plus size={16} className="mr-2" /> Add step {form.steps.length + 1}
              </Button>
            )}
          </TabsContent>

          {/* SCHEDULE */}
          <TabsContent value="schedule">
            <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-6">
              <div>
                <Label>Timezone</Label>
                <Select
                  value={form.schedule.timezone}
                  onValueChange={(v) =>
                    setForm({ ...form, schedule: { ...form.schedule, timezone: v } })
                  }
                  disabled={!canEdit}
                >
                  <SelectTrigger data-testid="drip-tz-select" className="mt-1.5">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {COMMON_TIMEZONES.map((tz) => (
                      <SelectItem key={tz} value={tz}>{tz}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label>Sending days</Label>
                <div className="flex gap-2 mt-2 flex-wrap">
                  {DAYS.map((d) => {
                    const active = form.schedule.sending_days.includes(d.id);
                    return (
                      <button
                        key={d.id}
                        type="button"
                        onClick={() => canEdit && toggleDay(d.id)}
                        disabled={!canEdit}
                        data-testid={`drip-day-${d.id}`}
                        className={`px-3 py-1.5 rounded-full text-sm border transition-colors ${
                          active
                            ? "bg-violet-600 text-white border-violet-600"
                            : "bg-white text-slate-600 border-slate-300 hover:border-violet-400"
                        } ${!canEdit && "opacity-60 cursor-not-allowed"}`}
                      >
                        {d.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Sending window starts</Label>
                  <Input
                    type="time"
                    value={form.schedule.start_time}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        schedule: { ...form.schedule, start_time: e.target.value },
                      })
                    }
                    disabled={!canEdit}
                    data-testid="drip-start-time"
                    className="mt-1.5"
                  />
                </div>
                <div>
                  <Label>Sending window ends</Label>
                  <Input
                    type="time"
                    value={form.schedule.end_time}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        schedule: { ...form.schedule, end_time: e.target.value },
                      })
                    }
                    disabled={!canEdit}
                    data-testid="drip-end-time"
                    className="mt-1.5"
                  />
                </div>
              </div>

              <div className="flex items-center justify-between border-t border-slate-200 pt-4">
                <div>
                  <div className="font-medium text-slate-900">Randomize send time</div>
                  <p className="text-sm text-slate-500">
                    Adds a small random offset so sends look more natural
                  </p>
                </div>
                <Switch
                  checked={form.schedule.randomize_time}
                  onCheckedChange={(v) =>
                    setForm({ ...form, schedule: { ...form.schedule, randomize_time: v } })
                  }
                  disabled={!canEdit}
                  data-testid="drip-randomize-switch"
                />
              </div>
            </div>
          </TabsContent>

          {/* CONTACTS */}
          <TabsContent value="contacts">
            <div className="bg-white border border-slate-200 rounded-2xl p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-semibold text-slate-900">Enrolled contacts</h3>
                  <p className="text-sm text-slate-500">
                    Contacts advance through each step automatically.
                  </p>
                </div>
                <Button
                  onClick={() => setAddContactsOpen(true)}
                  className="bg-violet-600 hover:bg-violet-700 text-white"
                  data-testid="drip-add-contacts-btn"
                >
                  <Plus size={16} className="mr-2" /> Add from list
                </Button>
              </div>

              {contacts.length === 0 ? (
                <div className="text-center py-10 text-slate-500">
                  <Users className="mx-auto mb-2 text-slate-400" size={36} strokeWidth={1.2} />
                  No contacts yet. Enroll an email list to begin.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 text-left text-slate-500">
                        <th className="py-2 px-3">Email</th>
                        <th className="py-2 px-3">Current step</th>
                        <th className="py-2 px-3">Status</th>
                        <th className="py-2 px-3">Next send</th>
                      </tr>
                    </thead>
                    <tbody>
                      {contacts.map((c) => (
                        <tr key={c.contact_id} className="border-b border-slate-100">
                          <td className="py-2 px-3 text-slate-900">{c.email}</td>
                          <td className="py-2 px-3">
                            {(c.current_step || 0) + 1} / {form.steps.length || "?"}
                          </td>
                          <td className="py-2 px-3">
                            <span
                              className={`px-2 py-0.5 rounded-full text-xs ${
                                c.status === "active"
                                  ? "bg-emerald-50 text-emerald-700"
                                  : c.status === "completed"
                                  ? "bg-blue-50 text-blue-700"
                                  : c.status === "replied"
                                  ? "bg-violet-50 text-violet-700"
                                  : c.status === "suppressed"
                                  ? "bg-rose-50 text-rose-700"
                                  : "bg-red-50 text-red-700"
                              }`}
                            >
                              {c.status}
                            </span>
                          </td>
                          <td className="py-2 px-3 text-slate-500 text-xs">
                            {c.next_send_at ? new Date(c.next_send_at).toLocaleString() : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </TabsContent>

          {/* LOGS */}
          <TabsContent value="logs">
            <div className="bg-white border border-slate-200 rounded-2xl p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h3 className="font-semibold text-slate-900">Send logs</h3>
                  <p className="text-sm text-slate-500">
                    Every email the sequence sends is logged here.
                  </p>
                </div>
                <Button
                  variant="outline"
                  onClick={handleExportLogs}
                  data-testid="drip-export-logs-btn"
                >
                  <Download size={16} className="mr-2" /> Export CSV
                </Button>
              </div>

              {logs.length === 0 ? (
                <div className="text-center py-10 text-slate-500">No send activity yet.</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 text-left text-slate-500">
                        <th className="py-2 px-3">Recipient</th>
                        <th className="py-2 px-3">Step</th>
                        <th className="py-2 px-3">Subject</th>
                        <th className="py-2 px-3">From</th>
                        <th className="py-2 px-3">Status</th>
                        <th className="py-2 px-3">Sent at</th>
                      </tr>
                    </thead>
                    <tbody>
                      {logs.map((l) => (
                        <tr key={l.log_id} className="border-b border-slate-100">
                          <td className="py-2 px-3 text-slate-900">{l.contact_email}</td>
                          <td className="py-2 px-3">{(l.step || 0) + 1}</td>
                          <td className="py-2 px-3 truncate max-w-[240px]">{l.subject}</td>
                          <td className="py-2 px-3 text-slate-500">{l.account_email}</td>
                          <td className="py-2 px-3">
                            {l.status === "sent" ? (
                              <span className="inline-flex items-center text-emerald-700 text-xs">
                                <CheckCircle2 size={12} className="mr-1" /> sent
                              </span>
                            ) : l.status === "suppressed" ? (
                              <span className="inline-flex items-center text-rose-700 text-xs">
                                <AlertCircle size={12} className="mr-1" /> suppressed
                              </span>
                            ) : (
                              <span className="inline-flex items-center text-red-700 text-xs">
                                <AlertCircle size={12} className="mr-1" /> failed
                              </span>
                            )}
                          </td>
                          <td className="py-2 px-3 text-slate-500 text-xs">
                            {l.sent_at ? new Date(l.sent_at).toLocaleString() : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </TabsContent>

          {/* SETTINGS */}
          <TabsContent value="settings">
            <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-6">
              <div>
                <Label>From name (optional)</Label>
                <Input
                  value={form.from_name}
                  onChange={(e) => setForm({ ...form, from_name: e.target.value })}
                  placeholder="Alex from RouteMail"
                  disabled={!canEdit}
                  data-testid="drip-from-name"
                  className="mt-1.5"
                />
              </div>

              <div>
                <Label>Sending accounts (rotation)</Label>
                <p className="text-xs text-slate-500 mb-2">
                  Pick one or more connected accounts. Emails are rotated across them.
                </p>
                {accounts.length === 0 ? (
                  <p className="text-sm text-slate-500">
                    No email accounts connected.{" "}
                    <button
                      type="button"
                      className="text-violet-600 underline"
                      onClick={() => navigate("/accounts")}
                    >
                      Connect one
                    </button>
                  </p>
                ) : (
                  <>
                    <AccountMultiSelect
                      accounts={accounts}
                      value={form.account_ids}
                      onChange={(next) => canEdit && setForm({ ...form, account_ids: next })}
                      disabled={!canEdit}
                      testIdPrefix="drip-accounts"
                      placeholder="Select sending accounts"
                    />
                    {(() => {
                      const connected = accounts.filter((a) => !a.status || a.status === "connected");
                      const pool =
                        form.account_ids?.length > 0
                          ? connected.filter((a) => form.account_ids.includes(a.account_id))
                          : connected;
                      const total = pool.reduce((s, a) => s + (parseInt(a.daily_limit, 10) || 0), 0);
                      const count = form.account_ids?.length > 0 ? form.account_ids.length : connected.length;
                      return (
                        <div
                          className="mt-2 inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-medium"
                          data-testid="drip-total-daily-capacity"
                        >
                          <Mail size={12} />
                          Total Daily Sending Capacity:&nbsp;
                          <span className="font-bold">{total.toLocaleString()}</span>
                          &nbsp;emails/day
                          <span className="text-emerald-600 font-normal ml-1">
                            ({count} account{count === 1 ? "" : "s"})
                          </span>
                        </div>
                      );
                    })()}
                  </>
                )}
              </div>

              <div className="border-t border-slate-200 pt-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium text-slate-900">Stop sequence on reply</div>
                    <p className="text-sm text-slate-500">
                      When a contact replies, future steps are skipped
                    </p>
                  </div>
                  <Switch
                    checked={form.stop_on_reply}
                    onCheckedChange={(v) => setForm({ ...form, stop_on_reply: v })}
                    disabled={!canEdit}
                    data-testid="drip-stop-reply-switch"
                  />
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium text-slate-900">Stop sequence on bounce</div>
                    <p className="text-sm text-slate-500">Bounced contacts won't receive more emails</p>
                  </div>
                  <Switch
                    checked={form.stop_on_bounce}
                    onCheckedChange={(v) => setForm({ ...form, stop_on_bounce: v })}
                    disabled={!canEdit}
                    data-testid="drip-stop-bounce-switch"
                  />
                </div>
              </div>

              <div className="border-t border-slate-200 pt-4">
                <Label>Do Not Email Lists</Label>
                <p className="text-xs text-slate-500 mb-3">
                  Pick the lists this drip should be checked against before every step.
                  Permanent unsubscribes are always blocked regardless.
                </p>
                {dneLists.length === 0 ? (
                  <p className="text-sm text-slate-500">
                    No Do Not Email lists yet.{" "}
                    <button
                      type="button"
                      onClick={() => navigate("/do-not-email")}
                      className="text-violet-600 underline"
                    >
                      Create one
                    </button>
                  </p>
                ) : (
                  <div className="space-y-2">
                    {dneLists.map((dne) => (
                      <label
                        key={dne.list_id}
                        className={`flex items-center gap-3 p-3 border rounded-lg cursor-pointer ${
                          dne.is_global
                            ? "border-rose-200 bg-rose-50/30"
                            : "border-slate-200 hover:bg-slate-50"
                        }`}
                      >
                        <Checkbox
                          checked={(form.suppression_list_ids || []).includes(dne.list_id)}
                          onCheckedChange={() => {
                            if (!canEdit) return;
                            const cur = form.suppression_list_ids || [];
                            const next = cur.includes(dne.list_id)
                              ? cur.filter((id) => id !== dne.list_id)
                              : [...cur, dne.list_id];
                            setForm({ ...form, suppression_list_ids: next });
                          }}
                          disabled={!canEdit}
                          data-testid={`drip-dne-${dne.list_id}`}
                        />
                        <div className="flex-1">
                          <div className="text-sm font-medium text-slate-900 flex items-center gap-2">
                            {dne.name}
                            {dne.is_global && (
                              <span className="text-[10px] uppercase tracking-wide bg-rose-100 text-rose-700 px-2 py-0.5 rounded-full">
                                Global
                              </span>
                            )}
                          </div>
                          <div className="text-xs text-slate-500">
                            {dne.email_count || 0} suppressed email
                            {dne.email_count === 1 ? "" : "s"}
                          </div>
                        </div>
                      </label>
                    ))}
                  </div>
                )}
                {dneLists.length > 0 && (form.suppression_list_ids || []).length === 0 && (
                  <div
                    className="mt-2 flex items-start gap-2 p-3 border border-amber-200 bg-amber-50 rounded-md text-amber-800 text-sm"
                    data-testid="drip-dne-no-selection-warning"
                  >
                    <AlertCircle size={16} className="mt-0.5 shrink-0" />
                    <span>
                      No unsubscribe list selected. Steps will not be checked against any
                      suppression lists (permanent unsubscribes are always blocked).
                    </span>
                  </div>
                )}
              </div>
            </div>
          </TabsContent>
        </Tabs>

        {/* Add contacts dialog */}
        <Dialog open={addContactsOpen} onOpenChange={setAddContactsOpen}>
          <DialogContent data-testid="drip-add-contacts-dialog">
            <DialogHeader>
              <DialogTitle>Add contacts from an email list</DialogTitle>
              <DialogDescription>
                Choose to enroll all valid emails in the list, or only a subset by row range. Duplicates are automatically skipped.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <Label>Email list</Label>
                <Select value={selectedList} onValueChange={setSelectedList}>
                  <SelectTrigger data-testid="drip-list-select" className="mt-1.5">
                    <SelectValue placeholder="Select a list" />
                  </SelectTrigger>
                  <SelectContent>
                    {lists.length === 0 ? (
                      <div className="px-3 py-2 text-sm text-slate-500">
                        No email lists yet. Upload one from Email Lists.
                      </div>
                    ) : (
                      lists.map((l) => (
                        <SelectItem key={l.list_id} value={l.list_id}>
                          {l.name} ({l.valid_emails || 0})
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>

              <div data-testid="drip-send-range-section">
                <Label>Send Range</Label>
                <div className="flex items-center gap-4 mt-1.5 mb-1">
                  <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                    <input
                      type="radio"
                      name="drip_send_range_mode"
                      value="all"
                      checked={sendRangeMode === "all"}
                      onChange={() => setSendRangeMode("all")}
                      data-testid="drip-send-range-all-radio"
                    />
                    <span>All contacts</span>
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                    <input
                      type="radio"
                      name="drip_send_range_mode"
                      value="range"
                      checked={sendRangeMode === "range"}
                      onChange={() => setSendRangeMode("range")}
                      data-testid="drip-send-range-range-radio"
                    />
                    <span>Custom range</span>
                  </label>
                </div>
                {sendRangeMode === "range" && (
                  <div className="flex items-center gap-3 mt-2">
                    <div className="flex items-center gap-2">
                      <Label className="text-xs text-slate-500">From</Label>
                      <Input
                        type="number"
                        min={1}
                        value={sendRangeStart}
                        onChange={(e) => setSendRangeStart(e.target.value)}
                        className="w-24"
                        data-testid="drip-send-range-start-input"
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <Label className="text-xs text-slate-500">To</Label>
                      <Input
                        type="number"
                        min={1}
                        value={sendRangeEnd}
                        onChange={(e) => setSendRangeEnd(e.target.value)}
                        className="w-24"
                        data-testid="drip-send-range-end-input"
                      />
                    </div>
                    <span className="text-xs text-slate-400">1-based, inclusive</span>
                  </div>
                )}
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setAddContactsOpen(false)}>
                Cancel
              </Button>
              <Button
                onClick={handleAddContacts}
                disabled={addingContacts || !selectedList}
                className="bg-violet-600 hover:bg-violet-700 text-white"
                data-testid="drip-add-contacts-confirm-btn"
              >
                {addingContacts ? "Adding…" : "Enroll contacts"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Drip Step — Test Mail Dialog */}
        <Dialog open={stepTestOpen} onOpenChange={setStepTestOpen}>
          <DialogContent data-testid="drip-step-test-dialog">
            <DialogHeader>
              <DialogTitle className="flex items-center gap-2">
                <TestTube size={18} className="text-blue-600" />
                Send Test Mail — Step {stepTestIdx !== null ? stepTestIdx + 1 : ""}
              </DialogTitle>
              <DialogDescription>
                Test emails do NOT count toward the campaign sending limit and are not recorded in stats.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <Label>Send From Account</Label>
                <Select value={stepTestAccountId} onValueChange={setStepTestAccountId}>
                  <SelectTrigger className="mt-1.5" data-testid="drip-step-test-account">
                    <SelectValue placeholder="Select account" />
                  </SelectTrigger>
                  <SelectContent>
                    {(accounts || []).map((acc) => (
                      <SelectItem key={acc.account_id} value={acc.account_id}>
                        {acc.email}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Test Email Address</Label>
                <Input
                  type="email"
                  placeholder="you@example.com"
                  value={stepTestEmail}
                  onChange={(e) => setStepTestEmail(e.target.value)}
                  className="mt-1.5"
                  data-testid="drip-step-test-email"
                />
              </div>
              <div>
                <Label>Email list</Label>
                <Select value={stepTestListId} onValueChange={onStepTestListChange}>
                  <SelectTrigger className="mt-1.5" data-testid="drip-step-test-list">
                    <SelectValue placeholder="Select an email list" />
                  </SelectTrigger>
                  <SelectContent>
                    {(lists || []).map((l) => (
                      <SelectItem key={l.list_id} value={l.list_id}>
                        {l.name} ({l.valid_emails || 0})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>Personalize with contact (optional)</Label>
                <Select
                  value={stepTestRecipientIdx}
                  onValueChange={setStepTestRecipientIdx}
                  disabled={!stepTestListData?.emails?.length}
                >
                  <SelectTrigger className="mt-1.5" data-testid="drip-step-test-recipient">
                    <SelectValue placeholder={
                      stepTestListData?.emails?.length
                        ? "Pick a contact to merge variables (optional)"
                        : "Select an email list first"
                    } />
                  </SelectTrigger>
                  <SelectContent>
                    {(stepTestListData?.emails || []).slice(0, 200).map((row, idx) => (
                      <SelectItem key={idx} value={String(idx)}>
                        {row.email}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {!stepTestListData?.emails?.length && (
                  <p className="text-xs text-amber-600 mt-1.5">
                    No contact selected — variables like {"{{first_name}}"} will be sent as-is.
                  </p>
                )}
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setStepTestOpen(false)} disabled={sendingStepTest}>
                Cancel
              </Button>
              <Button
                onClick={handleSendStepTest}
                disabled={sendingStepTest || !stepTestEmail || !stepTestAccountId}
                className="bg-blue-600 hover:bg-blue-700 text-white"
                data-testid="drip-step-test-send-btn"
              >
                {sendingStepTest ? "Sending…" : "Send Test"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
}

function StatBlock({ label, value, color = "text-slate-900" }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500 mb-1">{label}</div>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
    </div>
  );
}
