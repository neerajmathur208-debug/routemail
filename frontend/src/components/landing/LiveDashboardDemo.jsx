import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import {
  LayoutDashboard,
  Mail,
  FileText,
  Send,
  Workflow,
  Inbox,
  Star,
  ShieldOff,
  Archive,
  CreditCard,
  Activity,
  Plus,
  Play,
  Pause,
  Eye,
  Edit,
  ArrowRight,
  CheckCircle2,
  Clock,
  Calendar,
  TrendingUp,
  Crown,
  Globe,
  Folder,
  Download,
  Upload,
  Reply as ReplyIcon,
  Shield,
  ChevronDown,
} from "lucide-react";

/**
 * LiveDashboardDemo
 *
 * Interactive, frontend-only preview of the RouteMail dashboard. The structure,
 * sidebar items and feature surface mirrors the production app exactly — but
 * every value comes from the SAMPLE constant below (no API calls). Any action
 * button shows a friendly toast: "This is a preview. Sign up for the Free Plan."
 */

// Generic preview-action handler
const previewClick = () =>
  toast("This is a preview. Sign up for the Free Plan to use RouteMail.", {
    description: "It's free forever — no credit card required.",
  });

// ────────────────────────────────────────────────────────────────────────────
// SAMPLE DATA (realistic, no real users, no API)
// ────────────────────────────────────────────────────────────────────────────
const SAMPLE = {
  user: { name: "Alex Morgan", plan: "growth" },

  dashboard: {
    total_contacts: 12450,
    contacts_limit: 10000,
    active_campaigns: 8,
    active_drips: 5,
    accounts_connected: 24,
    warmup_active: 16,
    replies_received: 186,
    open_rate: 42,
    reply_rate: 8.4,
    sent_today: 2418,
    activity_weeks: [38, 52, 41, 67, 73, 58, 81, 92, 64, 70, 88, 95],
  },

  campaigns: [
    {
      id: "c1",
      name: "UK Law Firms Outreach",
      status: "running",
      contacts: 1842,
      opens: 779,
      replies: 156,
      accounts: 6,
      color: "blue",
    },
    {
      id: "c2",
      name: "SaaS Outreach Q3",
      status: "running",
      contacts: 2415,
      opens: 1023,
      replies: 218,
      accounts: 8,
      color: "violet",
    },
    {
      id: "c3",
      name: "Real Estate Ireland",
      status: "scheduled",
      contacts: 950,
      opens: 0,
      replies: 0,
      accounts: 4,
      color: "amber",
    },
    {
      id: "c4",
      name: "Recruitment Campaign",
      status: "completed",
      contacts: 1320,
      opens: 612,
      replies: 94,
      accounts: 5,
      color: "emerald",
    },
    {
      id: "c5",
      name: "Agency Prospecting Q4",
      status: "draft",
      contacts: 0,
      opens: 0,
      replies: 0,
      accounts: 0,
      color: "slate",
    },
  ],

  drips: [
    {
      id: "d1",
      name: "Law Firm 4-Touch Sequence",
      steps: 4,
      contacts: 412,
      timezone: "Europe/London",
      randomize: true,
      tracking: true,
      dne_list: "Global DNE",
      status: "running",
    },
    {
      id: "d2",
      name: "SaaS Founder Follow-up",
      steps: 5,
      contacts: 286,
      timezone: "America/New_York",
      randomize: true,
      tracking: true,
      dne_list: "Global DNE + Competitors",
      status: "running",
    },
    {
      id: "d3",
      name: "Real Estate Nurture",
      steps: 3,
      contacts: 184,
      timezone: "Europe/Dublin",
      randomize: false,
      tracking: true,
      dne_list: "Global DNE",
      status: "running",
    },
    {
      id: "d4",
      name: "Recruiter Cold Outreach",
      steps: 4,
      contacts: 142,
      timezone: "Europe/London",
      randomize: true,
      tracking: false,
      dne_list: "Global DNE",
      status: "paused",
    },
    {
      id: "d5",
      name: "Demo Booking Flow",
      steps: 5,
      contacts: 96,
      timezone: "America/Los_Angeles",
      randomize: true,
      tracking: true,
      dne_list: "Global DNE",
      status: "scheduled",
    },
  ],

  drip_sequence_preview: [
    { n: 1, t: "Cold intro — Partner-led",   d: "Day 0",     c: "blue" },
    { n: 2, t: "Follow-up + value add",      d: "+ 3 days",  c: "violet" },
    { n: 3, t: "Case study from peer firm",  d: "+ 7 days",  c: "fuchsia" },
    { n: 4, t: "Final nudge — break-up",     d: "+ 14 days", c: "rose" },
  ],

  email_lists: [
    { id: "l1", name: "UK Law Firms — Founders",  contacts: 2150, columns: 6 },
    { id: "l2", name: "SaaS Founders <$5M ARR",   contacts: 4820, columns: 7 },
    { id: "l3", name: "Irish Real Estate Brokers", contacts: 1240, columns: 5 },
    { id: "l4", name: "Recruitment Agencies UK",  contacts: 1750, columns: 6 },
  ],

  accounts: [
    { id: "a1", email: "alex@perfectoutreach.co",     daily_limit: 100, sent_today: 87, smtp: true, imap: true, warmup: true,  health: 96, status: "Healthy" },
    { id: "a2", email: "growth@perfectoutreach.co",   daily_limit: 100, sent_today: 91, smtp: true, imap: true, warmup: true,  health: 94, status: "Healthy" },
    { id: "a3", email: "sales@perfectoutreach.co",    daily_limit: 75,  sent_today: 41, smtp: true, imap: true, warmup: true,  health: 91, status: "Healthy" },
    { id: "a4", email: "team@routemail-demo.io",      daily_limit: 75,  sent_today: 32, smtp: true, imap: true, warmup: true,  health: 88, status: "Healthy" },
    { id: "a5", email: "founders@routemail-demo.io",  daily_limit: 50,  sent_today: 18, smtp: true, imap: true, warmup: true,  health: 82, status: "Monitor" },
    { id: "a6", email: "partners@routemail-demo.io",  daily_limit: 50,  sent_today: 26, smtp: true, imap: true, warmup: false, health: 71, status: "Monitor" },
    { id: "a7", email: "outreach@yourbiz.io",         daily_limit: 50,  sent_today: 12, smtp: true, imap: false, warmup: true,  health: 64, status: "Monitor" },
    { id: "a8", email: "hello@yourbiz.io",            daily_limit: 50,  sent_today: 5,  smtp: true, imap: true, warmup: true,  health: 48, status: "Risky" },
  ],

  warmup_accounts: [
    { email: "alex@perfectoutreach.co",     sent: 42, replies: 31, score: 96, status: "Healthy" },
    { email: "growth@perfectoutreach.co",   sent: 40, replies: 28, score: 94, status: "Healthy" },
    { email: "sales@perfectoutreach.co",    sent: 38, replies: 24, score: 91, status: "Healthy" },
    { email: "team@routemail-demo.io",      sent: 36, replies: 22, score: 88, status: "Healthy" },
    { email: "founders@routemail-demo.io",  sent: 32, replies: 18, score: 82, status: "Monitor" },
    { email: "outreach@yourbiz.io",         sent: 28, replies: 14, score: 64, status: "Monitor" },
    { email: "hello@yourbiz.io",            sent: 21, replies:  8, score: 48, status: "Risky" },
  ],

  warmup_summary: {
    total_active: 16,
    avg_health: 84,
    daily_emails: 538,
    replies_received: 282,
  },

  unibox_replies: [
    {
      id: "r1",
      from: "michael.peterson@millerlawllp.co.uk",
      campaign: "UK Law Firms Outreach",
      account: "alex@perfectoutreach.co",
      preview: "Hi Alex, thanks for reaching out — happy to chat. Could you share a few times Thursday next week?",
      timestamp: "2h ago",
      tag: "positive",
    },
    {
      id: "r2",
      from: "sarah.kim@cloudops.ai",
      campaign: "SaaS Outreach Q3",
      account: "growth@perfectoutreach.co",
      preview: "Looks interesting. Send over a one-pager and I'll forward internally to our growth lead.",
      timestamp: "4h ago",
      tag: "info-requested",
    },
    {
      id: "r3",
      from: "j.oconnor@dublinhomes.ie",
      campaign: "Real Estate Ireland",
      account: "sales@perfectoutreach.co",
      preview: "Not the right fit for us at the moment, but please keep me on your list for next year.",
      timestamp: "Yesterday",
      tag: "soft-no",
    },
    {
      id: "r4",
      from: "ops@brightpath-recruit.com",
      campaign: "Recruitment Campaign",
      account: "team@routemail-demo.io",
      preview: "Already working with another vendor — please remove me from any future campaigns.",
      timestamp: "Yesterday",
      tag: "unsubscribe-request",
    },
    {
      id: "r5",
      from: "leah.foster@northstarcap.com",
      campaign: "SaaS Outreach Q3",
      account: "growth@perfectoutreach.co",
      preview: "Booked a slot via the link. Looking forward to Thursday.",
      timestamp: "2 days ago",
      tag: "booked",
    },
  ],

  lead_folders: [
    { id: "f1", name: "Perfect Digitals",    leads: 42, color: "blue" },
    { id: "f2", name: "Real Estate Leads",   leads: 31, color: "emerald" },
    { id: "f3", name: "Law Firms",           leads: 56, color: "violet" },
    { id: "f4", name: "SaaS Prospects",      leads: 73, color: "fuchsia" },
  ],

  leads_sample: [
    { id: "ld1", email: "michael.peterson@millerlawllp.co.uk", campaign: "UK Law Firms Outreach", summary: "Interested — wants Thursday call",    added: "2h ago", folder: "Law Firms" },
    { id: "ld2", email: "leah.foster@northstarcap.com",        campaign: "SaaS Outreach Q3",       summary: "Booked demo via calendar",          added: "2 days ago", folder: "SaaS Prospects" },
    { id: "ld3", email: "sarah.kim@cloudops.ai",               campaign: "SaaS Outreach Q3",       summary: "Asked for one-pager",                added: "4h ago", folder: "SaaS Prospects" },
    { id: "ld4", email: "j.oconnor@dublinhomes.ie",            campaign: "Real Estate Ireland",    summary: "Not now — re-engage Q1",            added: "Yesterday", folder: "Real Estate Leads" },
  ],

  dne: {
    emails_blocked: 1245,
    domains_blocked: 187,
    lists: [
      { id: "g", name: "Global DNE",                  is_global: true,  emails: 845, domains: 142 },
      { id: "n", name: "Known Competitors",           is_global: false, emails: 18,  domains: 12 },
      { id: "u", name: "Unsubscribed Q3",             is_global: false, emails: 312, domains: 26 },
      { id: "p", name: "Partner / Internal blocklist", is_global: false, emails: 70, domains: 7 },
    ],
    sample_entries: [
      { type: "email",  value: "michael.peterson@millerlawllp.co.uk", source: "unsubscribe", added: "2h ago"  },
      { type: "domain", value: "competitor-saas.io",                  source: "manual",      added: "Yesterday" },
      { type: "email",  value: "ops@brightpath-recruit.com",          source: "unsubscribe", added: "Yesterday" },
      { type: "domain", value: "junkmail-domain.biz",                 source: "imported",    added: "3 days ago" },
      { type: "email",  value: "do-not-email@example.com",            source: "manual",      added: "Last week"  },
    ],
  },

  backup_history: [
    { id: "b1", type: "Full backup",  size: "8.4 MB",  date: "Today, 09:14" },
    { id: "b2", type: "DNE export",   size: "164 KB",  date: "Yesterday, 18:02" },
    { id: "b3", type: "Leads export", size: "92 KB",   date: "3 days ago" },
  ],

  plans: [
    { id: "starter",  name: "Starter",  price_yr: 99,  contacts: "4,000",  highlighted: false },
    { id: "growth",   name: "Growth",   price_yr: 149, contacts: "10,000", highlighted: true  },
    { id: "custom",   name: "Custom",   price_yr: 199, contacts: "15,000+", highlighted: false },
  ],

  custom_plan_slabs: [
    { slug: "custom_15k",  price: 199, label: "15,000 contacts / mo" },
    { slug: "custom_20k",  price: 249, label: "20,000 contacts / mo" },
    { slug: "custom_30k",  price: 349, label: "30,000 contacts / mo" },
    { slug: "custom_50k",  price: 499, label: "50,000 contacts / mo" },
    { slug: "custom_75k",  price: 699, label: "75,000 contacts / mo" },
    { slug: "custom_100k", price: 899, label: "100,000 contacts / mo" },
  ],
};

// ────────────────────────────────────────────────────────────────────────────
// Atoms
// ────────────────────────────────────────────────────────────────────────────
const StatCard = ({ icon: Icon, label, value, accent = "blue", sub }) => (
  <div className="rounded-xl border border-slate-200 bg-white p-4">
    <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
      <Icon size={12} className={`text-${accent}-500`} />
      {label}
    </div>
    <div className="text-xl md:text-2xl font-bold text-slate-900 mt-1">{value}</div>
    {sub && <div className="text-[11px] text-slate-500 mt-0.5">{sub}</div>}
  </div>
);

const StatusPill = ({ status }) => {
  const cls = {
    completed: "bg-emerald-100 text-emerald-700",
    running: "bg-blue-100 text-blue-700",
    scheduled: "bg-violet-100 text-violet-700",
    paused: "bg-amber-100 text-amber-700",
    draft: "bg-slate-100 text-slate-600",
    failed: "bg-rose-100 text-rose-700",
    Healthy: "bg-emerald-100 text-emerald-700",
    Monitor: "bg-amber-100 text-amber-700",
    Risky: "bg-rose-100 text-rose-700",
  }[status] || "bg-slate-100 text-slate-600";
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${cls}`}>
      {status}
    </span>
  );
};

const FauxBtn = ({ children, variant = "ghost", className = "" }) => {
  const base =
    variant === "primary"
      ? "bg-gradient-to-r from-blue-600 to-violet-600 text-white hover:from-blue-700 hover:to-violet-700"
      : variant === "outline"
      ? "border border-slate-200 text-slate-700 hover:bg-slate-50"
      : variant === "danger"
      ? "border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100"
      : "text-slate-500 hover:text-slate-900 hover:bg-slate-50";
  return (
    <button
      type="button"
      onClick={previewClick}
      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-medium transition-colors ${base} ${className}`}
    >
      {children}
    </button>
  );
};

// ────────────────────────────────────────────────────────────────────────────
// Panels
// ────────────────────────────────────────────────────────────────────────────
function Panel_Dashboard() {
  const d = SAMPLE.dashboard;
  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-4">
      <div className="space-y-4">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatCard icon={Mail}        label="Total Contacts"    value={d.total_contacts.toLocaleString()} accent="blue"    sub="across all lists" />
          <StatCard icon={Send}        label="Active Campaigns"  value={d.active_campaigns}                accent="violet"  sub="running + scheduled" />
          <StatCard icon={Workflow}    label="Active Drips"      value={d.active_drips}                    accent="fuchsia" sub="multi-step sequences" />
          <StatCard icon={Inbox}       label="Connected Accounts" value={d.accounts_connected}              accent="emerald" sub={`${d.warmup_active} warming`} />
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatCard icon={Activity}    label="Warmup Accounts"   value={d.warmup_active}                   accent="emerald" />
          <StatCard icon={ReplyIcon}   label="Replies Received"  value={d.replies_received}                accent="violet"  sub="this month" />
          <StatCard icon={Eye}         label="Open Rate"         value={`${d.open_rate}%`}                 accent="blue"    sub="last 30 days" />
          <StatCard icon={TrendingUp}  label="Reply Rate"        value={`${d.reply_rate}%`}                accent="fuchsia" sub="last 30 days" />
        </div>

        <div className="rounded-xl border border-slate-200 overflow-hidden bg-white">
          <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-slate-900">Sends — last 12 weeks</div>
              <div className="text-xs text-slate-500">Total volume across all accounts</div>
            </div>
            <FauxBtn>
              View All <ArrowRight size={12} />
            </FauxBtn>
          </div>
          <div className="px-4 py-4">
            <div className="flex items-end gap-2 h-28">
              {d.activity_weeks.map((b, i) => (
                <div
                  key={i}
                  className="flex-1 bg-gradient-to-t from-blue-500 to-violet-500 rounded-t-md"
                  style={{ height: `${b}%` }}
                />
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Side rail */}
      <div className="space-y-3">
        <div className="rounded-xl border border-slate-200 p-4 bg-white">
          <div className="flex items-center justify-between mb-2">
            <div className="text-xs font-semibold text-slate-700">Plan & Usage</div>
            <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-100 text-amber-700 rounded text-[10px] font-bold">
              <Crown size={10} /> Growth
            </span>
          </div>
          <div className="text-xs text-slate-500 mb-1">Unique recipients this month</div>
          <div className="text-base font-bold text-slate-900">
            {Math.min(d.total_contacts, d.contacts_limit).toLocaleString()}
            <span className="text-slate-400 font-medium"> / {d.contacts_limit.toLocaleString()}</span>
          </div>
          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden mt-2">
            <div className="h-full bg-emerald-500" style={{ width: "82%" }} />
          </div>
          <div className="mt-1 text-[10px] text-slate-500">82% used. Follow-ups don&apos;t count again.</div>
        </div>
        <div className="rounded-xl border border-slate-200 p-4 bg-white">
          <div className="text-xs font-semibold text-slate-700 mb-2">Today</div>
          <div className="space-y-1.5 text-xs text-slate-600">
            <div className="flex justify-between"><span>Sent</span><strong className="text-slate-900">{d.sent_today.toLocaleString()}</strong></div>
            <div className="flex justify-between"><span>Delivered</span><strong className="text-emerald-600">98.6%</strong></div>
            <div className="flex justify-between"><span>Bounces</span><strong className="text-rose-600">14</strong></div>
            <div className="flex justify-between"><span>Replies</span><strong className="text-violet-600">42</strong></div>
          </div>
        </div>
        <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-4">
          <div className="text-xs font-semibold text-emerald-700 mb-1">Deliverability</div>
          <div className="text-base font-bold text-emerald-700">Healthy</div>
          <div className="text-[11px] text-emerald-700/80 mt-1">16 of 24 inboxes warming · 0 RTM hits today</div>
        </div>
      </div>
    </div>
  );
}

function Panel_Campaigns() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-slate-900">Campaigns</div>
          <div className="text-xs text-slate-500">
            {SAMPLE.campaigns.filter((c) => c.status !== "draft").length} active · {SAMPLE.campaigns.length} total
          </div>
        </div>
        <FauxBtn variant="primary"><Plus size={12} /> New Campaign</FauxBtn>
      </div>
      <div className="rounded-xl border border-slate-200 overflow-hidden bg-white">
        <div className="overflow-x-auto">
          <div className="min-w-[720px]">
            <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-200 grid grid-cols-[2fr_1fr_1fr_1fr_1fr_1fr_auto] gap-3 text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
              <span>Campaign</span><span>Status</span><span>Contacts</span><span>Opens</span><span>Replies</span><span>Accounts</span><span></span>
            </div>
            <div className="divide-y divide-slate-100">
              {SAMPLE.campaigns.map((c) => (
                <div key={c.id} className="px-4 py-3 grid grid-cols-[2fr_1fr_1fr_1fr_1fr_1fr_auto] gap-3 items-center">
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-slate-900 truncate">{c.name}</div>
                    <div className="text-[10px] text-slate-400 mt-0.5">ID: {c.id} · created Feb 2026</div>
                  </div>
                  <div><StatusPill status={c.status} /></div>
                  <span className="text-xs text-slate-700 font-medium">{c.contacts.toLocaleString()}</span>
                  <span className="text-xs text-slate-700">{c.opens.toLocaleString()}</span>
                  <span className="text-xs text-violet-700 font-semibold">{c.replies.toLocaleString()}</span>
                  <span className="text-xs text-slate-500">{c.accounts}</span>
                  <div className="flex gap-1">
                    {c.status === "draft" && <FauxBtn><Edit size={12} /></FauxBtn>}
                    {c.status === "running" && <FauxBtn><Pause size={12} /></FauxBtn>}
                    {c.status === "paused" && <FauxBtn><Play size={12} /></FauxBtn>}
                    {c.status === "scheduled" && <FauxBtn><Pause size={12} /></FauxBtn>}
                    <FauxBtn><Eye size={12} /></FauxBtn>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Composer preview */}
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="text-xs font-semibold text-slate-700">Compose preview — UK Law Firms Outreach</div>
          <span className="text-[10px] text-slate-500">From: alex@perfectoutreach.co · 6 sender accounts</span>
        </div>
        <div className="space-y-2 text-sm">
          <div className="text-[10px] uppercase font-semibold text-slate-400">Subject</div>
          <div className="font-semibold text-slate-900">
            &ldquo;Quick question about <span className="bg-amber-100 px-0.5 rounded">{"{{firm_name}}"}</span>&apos;s litigation pipeline&rdquo;
          </div>
          <div className="text-[10px] uppercase font-semibold text-slate-400 mt-2">Body</div>
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-slate-700 leading-relaxed">
            <p>Hi <span className="bg-amber-100 px-0.5 rounded">{"{{first_name}}"}</span>,</p>
            <p className="mt-1.5">Saw the recent expansion at <span className="bg-amber-100 px-0.5 rounded">{"{{firm_name}}"}</span> — congrats on the new partner hires. We help UK litigation firms keep cold-outreach deliverability healthy across multiple inboxes.</p>
            <p className="mt-1.5 text-slate-400">— Alex at RouteMail</p>
          </div>
          <div className="flex items-center gap-2 text-[11px] text-emerald-700">
            <CheckCircle2 size={12} /> Suppression list checked · 0 domain conflicts · 0 unsubscribed conflicts
          </div>
        </div>
      </div>
    </div>
  );
}

function Panel_Drip() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-slate-900">Drip Campaigns</div>
          <div className="text-xs text-slate-500">{SAMPLE.drips.length} sequences · multi-step automation</div>
        </div>
        <FauxBtn variant="primary"><Plus size={12} /> New Drip</FauxBtn>
      </div>
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
        {SAMPLE.drips.map((d) => (
          <div key={d.id} className="rounded-xl border border-slate-200 bg-white p-4 hover:border-violet-300 transition-colors">
            <div className="flex items-start justify-between mb-2">
              <div className="text-sm font-semibold text-slate-900 line-clamp-2">{d.name}</div>
              <StatusPill status={d.status} />
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs mb-2">
              <div className="text-slate-500">Steps<div className="text-slate-900 font-bold text-base">{d.steps}</div></div>
              <div className="text-slate-500">Contacts<div className="text-slate-900 font-bold text-base">{d.contacts}</div></div>
            </div>
            <div className="space-y-1 text-[11px] text-slate-500">
              <div className="flex items-center gap-1.5"><Globe size={10} /> {d.timezone}</div>
              <div className="flex items-center gap-1.5"><Clock size={10} /> {d.randomize ? "Randomize send time" : "Fixed schedule"}</div>
              <div className="flex items-center gap-1.5"><ShieldOff size={10} /> DNE: {d.dne_list}</div>
              <div className="flex items-center gap-1.5"><Eye size={10} /> {d.tracking ? "Open + reply tracking" : "Tracking off"}</div>
            </div>
          </div>
        ))}
      </div>
      {/* Sequence preview */}
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="text-xs font-semibold text-slate-700">Sequence preview — Law Firm 4-Touch</div>
          <div className="flex items-center gap-2 text-[10px] text-slate-500">
            <span className="inline-flex items-center gap-1"><Globe size={10} /> Europe/London</span>
            <span className="inline-flex items-center gap-1"><Clock size={10} /> 09:00 – 17:00</span>
            <span className="inline-flex items-center gap-1"><Shield size={10} /> Stop on reply</span>
          </div>
        </div>
        <div className="space-y-2.5">
          {SAMPLE.drip_sequence_preview.map((s) => (
            <div key={s.n} className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-md bg-${s.c}-100 text-${s.c}-700 flex items-center justify-center text-xs font-bold`}>
                {s.n}
              </div>
              <div className="flex-1">
                <div className="text-sm font-medium text-slate-900">{s.t}</div>
                <div className="text-xs text-slate-500">{s.d} · sent between 09:00–17:00 with randomization</div>
              </div>
              <Clock size={12} className="text-slate-400" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Panel_Lists() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-slate-900">Email Lists</div>
          <div className="text-xs text-slate-500">{SAMPLE.email_lists.length} lists · CSV import supported</div>
        </div>
        <FauxBtn variant="primary"><Upload size={12} /> Import CSV</FauxBtn>
      </div>
      <div className="grid md:grid-cols-2 gap-3">
        {SAMPLE.email_lists.map((l) => (
          <div key={l.id} className="rounded-xl border border-slate-200 bg-white p-4 flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="text-sm font-semibold text-slate-900 truncate">{l.name}</div>
              <div className="text-xs text-slate-500 mt-0.5">{l.contacts.toLocaleString()} contacts · {l.columns} columns</div>
            </div>
            <div className="flex gap-1.5">
              <FauxBtn><Eye size={12} /> Open</FauxBtn>
              <FauxBtn><Download size={12} /></FauxBtn>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Panel_Accounts() {
  const totalCap = SAMPLE.accounts.reduce((s, a) => s + a.daily_limit, 0);
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-slate-900">Email Accounts</div>
          <div className="text-xs text-slate-500">{SAMPLE.accounts.length} of 24 connected</div>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-medium">
            <Send size={11} /> {totalCap.toLocaleString()} emails/day capacity
          </span>
          <FauxBtn variant="primary"><Plus size={12} /> Add Account</FauxBtn>
        </div>
      </div>
      <div className="rounded-xl border border-slate-200 overflow-hidden bg-white">
        <div className="overflow-x-auto">
          <div className="min-w-[760px]">
            <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-200 grid grid-cols-[2fr_70px_90px_70px_70px_90px_80px] gap-3 text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
              <span>Account</span><span>Daily</span><span>Sent today</span><span>SMTP</span><span>IMAP</span><span>Warmup</span><span>Health</span>
            </div>
            <div className="divide-y divide-slate-100">
              {SAMPLE.accounts.map((a) => (
                <div key={a.id} className="px-4 py-3 grid grid-cols-[2fr_70px_90px_70px_70px_90px_80px] gap-3 items-center">
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center text-xs font-bold text-slate-600">
                      {a.email[0].toUpperCase()}
                    </div>
                    <span className="text-sm text-slate-800 truncate">{a.email}</span>
                  </div>
                  <span className="text-xs text-slate-500">{a.daily_limit}</span>
                  <span className="text-xs text-slate-700 font-medium">{a.sent_today}</span>
                  <span className="text-xs">
                    {a.smtp ? <CheckCircle2 size={12} className="text-emerald-500 inline" /> : <span className="text-slate-300">—</span>}
                  </span>
                  <span className="text-xs">
                    {a.imap ? <CheckCircle2 size={12} className="text-emerald-500 inline" /> : <span className="text-slate-300">—</span>}
                  </span>
                  <span className={`text-xs ${a.warmup ? "text-emerald-600 font-medium" : "text-slate-400"}`}>
                    {a.warmup ? "Active" : "Off"}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <div className="w-10 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                      <div
                        className={`h-full ${a.health >= 80 ? "bg-emerald-500" : a.health >= 60 ? "bg-amber-500" : "bg-rose-500"}`}
                        style={{ width: `${a.health}%` }}
                      />
                    </div>
                    <span className="text-[10px] font-bold text-slate-900">{a.health}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Panel_Warmup() {
  const w = SAMPLE.warmup_summary;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatCard icon={Activity}     label="Active Warmup"    value={w.total_active}            accent="emerald" sub="inboxes warming" />
        <StatCard icon={TrendingUp}   label="Avg Health"       value={`${w.avg_health}/100`}     accent="blue"    sub="across pool" />
        <StatCard icon={Send}         label="Daily Warmup"     value={w.daily_emails}            accent="violet"  sub="emails / day" />
        <StatCard icon={ReplyIcon}    label="Replies Received" value={w.replies_received}        accent="fuchsia" sub="last 7 days" />
      </div>
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
          <div className="text-xs font-semibold text-slate-700">Warmup pool — health, conversational replies & deliverability</div>
          <FauxBtn variant="outline">Bulk settings</FauxBtn>
        </div>
        <div className="overflow-x-auto">
          <div className="min-w-[620px] divide-y divide-slate-100">
            {SAMPLE.warmup_accounts.map((wa) => (
              <div key={wa.email} className="px-4 py-3 grid grid-cols-[2fr_80px_90px_120px_90px] gap-3 items-center">
                <div className="flex items-center gap-2 min-w-0">
                  <div className="w-7 h-7 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-xs font-bold">
                    {wa.email[0].toUpperCase()}
                  </div>
                  <span className="text-sm text-slate-800 truncate">{wa.email}</span>
                </div>
                <span className="text-xs text-slate-500">Sent {wa.sent}</span>
                <span className="text-xs text-slate-500">Replies {wa.replies}</span>
                <div className="flex items-center gap-2">
                  <div className="w-20 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className={`h-full ${wa.score >= 80 ? "bg-emerald-500" : wa.score >= 60 ? "bg-amber-500" : "bg-rose-500"}`}
                      style={{ width: `${wa.score}%` }}
                    />
                  </div>
                  <span className="text-[10px] font-bold text-slate-900 w-6 text-right">{wa.score}</span>
                </div>
                <StatusPill status={wa.status} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function Panel_Unibox() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-slate-900">Unibox — centralized replies</div>
          <div className="text-xs text-slate-500">{SAMPLE.unibox_replies.length} new replies across 8 inboxes</div>
        </div>
        <div className="flex gap-2">
          <FauxBtn variant="outline">Filter: All</FauxBtn>
          <FauxBtn variant="outline">Sync now</FauxBtn>
        </div>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden divide-y divide-slate-100">
        {SAMPLE.unibox_replies.map((r) => (
          <div key={r.id} className="px-4 py-3 hover:bg-slate-50">
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-full bg-violet-100 text-violet-700 flex items-center justify-center text-xs font-bold flex-shrink-0">
                {r.from[0].toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-slate-900 truncate">{r.from}</span>
                  <span className="text-[10px] px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded-full">
                    {r.campaign}
                  </span>
                  <span className="text-[10px] text-slate-400">→ {r.account}</span>
                  <span className="ml-auto text-[11px] text-slate-400 whitespace-nowrap">{r.timestamp}</span>
                </div>
                <p className="text-xs text-slate-600 mt-1 line-clamp-2">{r.preview}</p>
                <div className="flex gap-1.5 mt-2">
                  <FauxBtn variant="outline"><Star size={11} /> Add to Responses/Leads</FauxBtn>
                  <FauxBtn variant="danger"><ShieldOff size={11} /> Add to Global DNE</FauxBtn>
                  <FauxBtn><ReplyIcon size={11} /> Reply</FauxBtn>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Panel_Leads() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-slate-900">Responses / Leads</div>
          <div className="text-xs text-slate-500">Organise replies into folders · {SAMPLE.lead_folders.reduce((s, f) => s + f.leads, 0)} saved leads</div>
        </div>
        <FauxBtn variant="primary"><Plus size={12} /> New Folder</FauxBtn>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {SAMPLE.lead_folders.map((f) => (
          <div key={f.id} className={`rounded-xl border border-${f.color}-200 bg-${f.color}-50/40 p-4 hover:border-${f.color}-300 transition-colors`}>
            <div className="flex items-center gap-2 mb-2">
              <Folder size={16} className={`text-${f.color}-600`} />
              <span className="text-sm font-semibold text-slate-900">{f.name}</span>
            </div>
            <div className="text-2xl font-bold text-slate-900">{f.leads}</div>
            <div className="text-[11px] text-slate-500">leads saved</div>
          </div>
        ))}
      </div>
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        <div className="overflow-x-auto">
          <div className="min-w-[680px]">
            <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-200 grid grid-cols-[2fr_1.4fr_2fr_1fr_1fr] gap-3 text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
              <span>Contact</span><span>Campaign</span><span>Summary</span><span>Folder</span><span>Added</span>
            </div>
            <div className="divide-y divide-slate-100">
              {SAMPLE.leads_sample.map((l) => (
                <div key={l.id} className="px-4 py-3 grid grid-cols-[2fr_1.4fr_2fr_1fr_1fr] gap-3 items-center text-xs">
                  <span className="text-slate-900 truncate font-medium">{l.email}</span>
                  <span className="text-slate-600 truncate">{l.campaign}</span>
                  <span className="text-slate-500 truncate">{l.summary}</span>
                  <span className="text-violet-700 font-medium">{l.folder}</span>
                  <span className="text-slate-400">{l.added}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Panel_DNE() {
  const dne = SAMPLE.dne;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-sky-200 bg-white p-4">
          <div className="text-[10px] uppercase tracking-wider text-sky-600 font-semibold mb-1">Emails Blocked</div>
          <div className="text-2xl font-bold text-slate-900">{dne.emails_blocked.toLocaleString()}</div>
          <div className="text-[11px] text-slate-500 mt-0.5">across {dne.lists.length} suppression lists</div>
        </div>
        <div className="rounded-xl border border-violet-200 bg-white p-4">
          <div className="text-[10px] uppercase tracking-wider text-violet-600 font-semibold mb-1">Domains Blocked</div>
          <div className="text-2xl font-bold text-slate-900">{dne.domains_blocked.toLocaleString()}</div>
          <div className="text-[11px] text-slate-500 mt-0.5">blocks every recipient on these domains</div>
        </div>
      </div>
      <div className="flex items-center justify-between">
        <div className="text-xs font-semibold text-slate-700">Suppression lists</div>
        <FauxBtn variant="primary"><Plus size={12} /> New list</FauxBtn>
      </div>
      <div className="grid md:grid-cols-2 gap-3">
        {dne.lists.map((l) => (
          <div key={l.id} className="rounded-xl border border-slate-200 bg-white p-4 flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-slate-900 flex items-center gap-1.5">
                {l.is_global && <Shield size={12} className="text-rose-500" />}
                {l.name}
              </div>
              <div className="text-[11px] text-slate-500 mt-0.5">
                {l.emails.toLocaleString()} emails · {l.domains.toLocaleString()} domains
              </div>
            </div>
            <FauxBtn><Eye size={11} /> Open</FauxBtn>
          </div>
        ))}
      </div>
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        <div className="overflow-x-auto">
          <div className="min-w-[520px]">
            <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-200 grid grid-cols-[80px_2fr_1fr_1fr] gap-3 text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
              <span>Type</span><span>Value</span><span>Source</span><span>Added</span>
            </div>
            <div className="divide-y divide-slate-100">
              {dne.sample_entries.map((e, i) => (
                <div key={i} className="px-4 py-3 grid grid-cols-[80px_2fr_1fr_1fr] gap-3 items-center text-xs">
                  <span
                    className={`inline-block px-2 py-0.5 text-[10px] uppercase tracking-wide rounded-full w-fit ${
                      e.type === "domain"
                        ? "bg-violet-100 text-violet-700"
                        : "bg-sky-100 text-sky-700"
                    }`}
                  >
                    {e.type}
                  </span>
                  <span className="text-slate-900 font-mono truncate">
                    {e.type === "domain" ? `@${e.value}` : e.value}
                  </span>
                  <span className="text-slate-500">{e.source}</span>
                  <span className="text-slate-400">{e.added}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Panel_Backup() {
  const exportOpts = [
    "Export Campaigns",
    "Export Drip Campaigns",
    "Export Email Lists",
    "Export Email Accounts",
    "Export Responses / Leads",
    "Export Do Not Email Lists",
    "Export Full Backup (ZIP)",
  ];
  const importOpts = [
    "Import Campaigns",
    "Import Drip Campaigns",
    "Import Email Lists",
    "Import Responses / Leads",
    "Import Do Not Email Lists",
    "Restore Full Backup (ZIP)",
  ];
  return (
    <div className="space-y-4">
      <div className="grid md:grid-cols-2 gap-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex items-center gap-2 mb-3">
            <Download size={16} className="text-emerald-600" />
            <span className="text-sm font-semibold text-slate-900">Export</span>
          </div>
          <div className="space-y-1.5">
            {exportOpts.map((o) => (
              <button
                key={o}
                type="button"
                onClick={previewClick}
                className="w-full flex items-center justify-between px-3 py-2 rounded-md border border-slate-200 text-xs text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition-colors text-left"
              >
                <span>{o}</span>
                <Download size={12} className="text-slate-400" />
              </button>
            ))}
          </div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <div className="flex items-center gap-2 mb-3">
            <Upload size={16} className="text-violet-600" />
            <span className="text-sm font-semibold text-slate-900">Import</span>
          </div>
          <div className="space-y-1.5">
            {importOpts.map((o) => (
              <button
                key={o}
                type="button"
                onClick={previewClick}
                className="w-full flex items-center justify-between px-3 py-2 rounded-md border border-slate-200 text-xs text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition-colors text-left"
              >
                <span>{o}</span>
                <Upload size={12} className="text-slate-400" />
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-700">
          Backup history
        </div>
        <div className="divide-y divide-slate-100">
          {SAMPLE.backup_history.map((h) => (
            <div key={h.id} className="px-4 py-3 flex items-center justify-between">
              <div>
                <div className="text-sm font-medium text-slate-900">{h.type}</div>
                <div className="text-[11px] text-slate-500">{h.date} · {h.size}</div>
              </div>
              <FauxBtn variant="outline"><Download size={11} /> Download</FauxBtn>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Panel_Subscription() {
  const [showCustom, setShowCustom] = useState(false);
  const [customSlab, setCustomSlab] = useState(SAMPLE.custom_plan_slabs[0]);
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-blue-50 p-5">
        <div className="flex items-center justify-between mb-2">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
              Unique contacts this month
            </div>
            <div className="text-2xl md:text-3xl font-bold text-slate-900">
              8,210 <span className="text-base font-medium text-slate-500">/ 10,000</span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] text-slate-500">Plan renews</div>
            <div className="text-sm font-semibold text-slate-900 inline-flex items-center gap-1.5">
              <Calendar size={12} className="text-slate-500" /> Mar 14, 2026
            </div>
          </div>
        </div>
        <div className="h-2.5 w-full bg-white rounded-full overflow-hidden border border-slate-200">
          <div className="h-full bg-emerald-500" style={{ width: "82%" }} />
        </div>
        <div className="mt-2 text-[11px] text-slate-500">
          82% used. Re-sending to an existing contact does NOT count again.
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-3">
        {SAMPLE.plans.map((p) => (
          <div
            key={p.id}
            className={`rounded-xl border p-4 flex flex-col ${
              p.highlighted
                ? "border-blue-400 ring-2 ring-blue-100 bg-white"
                : "border-slate-200 bg-white"
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold text-slate-900">{p.name}</span>
              {p.highlighted && (
                <span className="text-[10px] font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">
                  CURRENT
                </span>
              )}
            </div>
            <div className="flex items-baseline gap-1 mb-1">
              <span className="text-2xl font-bold text-slate-900">
                ${p.id === "custom" ? customSlab.price : p.price_yr}
              </span>
              <span className="text-xs text-slate-500">/year</span>
            </div>
            <div className="text-xs text-slate-500 mb-3">
              {p.id === "custom" ? customSlab.label : `${p.contacts} contacts / month`}
            </div>
            {p.id === "custom" && (
              <div className="relative mb-3">
                <button
                  type="button"
                  onClick={() => setShowCustom((v) => !v)}
                  className="w-full px-3 py-2 rounded-md border border-slate-200 text-xs text-slate-700 hover:bg-slate-50 flex items-center justify-between"
                >
                  <span>{customSlab.label}</span>
                  <ChevronDown size={12} className={`transition-transform ${showCustom ? "rotate-180" : ""}`} />
                </button>
                {showCustom && (
                  <div className="absolute z-10 mt-1 w-full rounded-md border border-slate-200 bg-white shadow-lg overflow-hidden">
                    {SAMPLE.custom_plan_slabs.map((s) => (
                      <button
                        key={s.slug}
                        type="button"
                        onClick={() => { setCustomSlab(s); setShowCustom(false); }}
                        className={`w-full text-left px-3 py-2 text-xs hover:bg-slate-50 flex items-center justify-between ${
                          customSlab.slug === s.slug ? "bg-blue-50 text-blue-700 font-semibold" : "text-slate-700"
                        }`}
                      >
                        <span>{s.label}</span>
                        <span className="font-mono">${s.price}/yr</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
            <ul className="space-y-1.5 text-[11px] text-slate-600 flex-1">
              <li className="flex items-center gap-1.5">
                <CheckCircle2 size={11} className="text-emerald-500" />
                Unlimited campaigns & drips
              </li>
              <li className="flex items-center gap-1.5">
                <CheckCircle2 size={11} className="text-emerald-500" />
                Unlimited email accounts
              </li>
              <li className="flex items-center gap-1.5">
                <CheckCircle2 size={11} className="text-emerald-500" />
                Warmup & deliverability
              </li>
              <li className="flex items-center gap-1.5">
                <CheckCircle2 size={11} className="text-emerald-500" />
                Unibox, Leads & DNE lists
              </li>
            </ul>
            <FauxBtn
              variant={p.highlighted ? "outline" : "primary"}
              className="mt-3 justify-center"
            >
              {p.highlighted ? "Current plan" : `Choose ${p.name}`}
            </FauxBtn>
          </div>
        ))}
      </div>
      <p className="text-[11px] text-slate-500 text-center">
        Pricing is based on <strong className="text-slate-700">monthly unique recipients</strong>.
        Email accounts are unlimited on all plans.
      </p>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Tab definitions (mirrors the production Sidebar exactly, plus Warmup)
// ────────────────────────────────────────────────────────────────────────────
const DEMO_TABS = [
  { id: "dashboard",   label: "Dashboard",          path: "/dashboard",      icon: LayoutDashboard, Panel: Panel_Dashboard    },
  { id: "campaigns",   label: "Campaigns",          path: "/campaign",       icon: Send,            Panel: Panel_Campaigns    },
  { id: "drip",        label: "Drip Campaigns",     path: "/drip-campaigns", icon: Workflow,        Panel: Panel_Drip         },
  { id: "lists",       label: "Email Lists",        path: "/email-lists",    icon: FileText,        Panel: Panel_Lists        },
  { id: "accounts",    label: "Email Accounts",     path: "/accounts",       icon: Mail,            Panel: Panel_Accounts     },
  { id: "warmup",      label: "Warmup",             path: "/accounts/warmup",icon: Activity,        Panel: Panel_Warmup       },
  { id: "unibox",      label: "Unibox",             path: "/unibox",         icon: Inbox,           Panel: Panel_Unibox       },
  { id: "leads",       label: "Responses / Leads",  path: "/leads",          icon: Star,            Panel: Panel_Leads        },
  { id: "dne",         label: "Do Not Email",       path: "/do-not-email",   icon: ShieldOff,       Panel: Panel_DNE          },
  { id: "backup",      label: "Backup & Restore",   path: "/backup",         icon: Archive,         Panel: Panel_Backup       },
  { id: "subscription", label: "Subscription",      path: "/subscription",   icon: CreditCard,      Panel: Panel_Subscription },
];

export default function LiveDashboardDemo() {
  const [active, setActive] = useState("dashboard");
  const current = DEMO_TABS.find((t) => t.id === active) || DEMO_TABS[0];
  const ActivePanel = current.Panel;

  return (
    <div data-testid="live-dashboard-demo" className="w-full max-w-full overflow-x-hidden">
      {/* Tabs — horizontal scroll on mobile to avoid stacking too tall */}
      <div
        className="flex md:flex-wrap md:justify-center gap-2 mb-6 md:mb-8 overflow-x-auto md:overflow-x-visible pb-2 md:pb-0 -mx-3 px-3 md:mx-0 md:px-0 snap-x"
        data-testid="demo-tabs"
      >
        {DEMO_TABS.map((t) => {
          const Icon = t.icon;
          const isActive = active === t.id;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => setActive(t.id)}
              className={`shrink-0 snap-start inline-flex items-center gap-2 px-3 py-2 rounded-full text-xs font-medium transition-all duration-200 border ${
                isActive
                  ? "bg-slate-900 text-white border-slate-900 shadow-lg"
                  : "bg-white text-slate-600 border-slate-200 hover:border-slate-300 hover:text-slate-900"
              }`}
              data-testid={`demo-tab-${t.id}`}
            >
              <Icon size={13} />
              <span className="whitespace-nowrap">{t.label}</span>
            </button>
          );
        })}
      </div>

      {/* Browser-chrome frame */}
      <div className="relative">
        <div
          className="absolute inset-x-0 -top-6 -bottom-6 bg-[radial-gradient(ellipse_at_center,rgba(99,102,241,0.18),transparent_60%)] pointer-events-none"
          aria-hidden
        />
        <div className="relative rounded-2xl border border-slate-200 bg-white shadow-2xl shadow-blue-500/10 overflow-hidden">
          {/* Browser chrome */}
          <div className="flex items-center gap-2 px-4 py-3 bg-slate-50 border-b border-slate-200">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-red-400" />
              <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
            </div>
            <div className="ml-3 flex-1 max-w-md mx-auto px-3 py-1 rounded-md bg-white border border-slate-200 text-xs text-slate-500 font-mono text-center truncate">
              app.routemail.co{current.path}
            </div>
            <div className="text-[10px] text-slate-400 hidden md:block">Live preview · sample data</div>
          </div>
          {/* App shell: faux sidebar (desktop) + active panel */}
          <div className="grid md:grid-cols-[220px_1fr] bg-white">
            <div className="hidden md:flex flex-col bg-slate-50 border-r border-slate-200 p-3">
              <div className="flex items-center gap-2 px-2 py-2 mb-3">
                <img src="/routemail-logo.png" alt="RouteMail" className="h-7 w-auto" />
              </div>
              {DEMO_TABS.map((t) => {
                const Icon = t.icon;
                const isActive = active === t.id;
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setActive(t.id)}
                    className={`flex items-center gap-2 px-2 py-1.5 rounded-md text-xs mb-0.5 transition-colors text-left ${
                      isActive
                        ? "bg-blue-50 text-blue-700 font-semibold"
                        : "text-slate-500 hover:bg-slate-100 hover:text-slate-900"
                    }`}
                  >
                    <Icon size={13} />
                    {t.label}
                  </button>
                );
              })}
              <div className="mt-auto pt-3 border-t border-slate-200">
                <div className="px-2 py-2">
                  <div className="text-[10px] text-slate-500">Signed in as</div>
                  <div className="text-xs font-semibold text-slate-900 truncate">{SAMPLE.user.name}</div>
                  <div className="text-[10px] text-amber-600 font-semibold mt-0.5 inline-flex items-center gap-1">
                    <Crown size={10} /> Growth plan
                  </div>
                </div>
              </div>
            </div>
            {/* Mobile section header — replaces the desktop sidebar */}
            <div className="md:hidden px-4 py-2.5 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                {(() => {
                  const Icon = current.icon;
                  return <Icon size={14} className="text-blue-600 shrink-0" />;
                })()}
                <span className="text-xs font-semibold text-slate-900 truncate">
                  {current.label}
                </span>
              </div>
              <span className="text-[10px] text-amber-600 font-semibold inline-flex items-center gap-1 shrink-0">
                <Crown size={10} /> Growth
              </span>
            </div>
            <AnimatePresence mode="wait">
              <motion.div
                key={current.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
                className="p-3 sm:p-5 md:p-7 min-h-[480px] max-h-[640px] overflow-y-auto overflow-x-hidden w-full max-w-full"
                data-testid={`demo-panel-${current.id}`}
              >
                <ActivePanel />
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </div>
      <p className="mt-4 text-center text-xs text-slate-500" data-testid="demo-preview-note">
        Interactive preview — clicking actions shows a tooltip; no real data is touched.
      </p>
    </div>
  );
}
