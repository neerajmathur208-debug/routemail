import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import {
  Mail,
  Send,
  Workflow,
  Activity,
  Layers,
  BarChart3,
  Crown,
  Plus,
  Play,
  Pause,
  Eye,
  FileText,
  Edit,
  ArrowRight,
  CheckCircle2,
  Clock,
  Inbox,
  Calendar,
  TrendingUp,
} from "lucide-react";

/**
 * LiveDashboardDemo
 *
 * Frontend-only interactive preview of the RouteMail dashboard. Renders the
 * same visual language as the real product, but reads only from the SAMPLE
 * arrays defined below — never from an API. Any "action" button shows a
 * friendly toast: "This is a preview. Start your free trial to use RouteMail."
 *
 * Used in /app/frontend/src/pages/LandingPage.jsx#InteractiveDemo
 */

// ────────────────────────────────────────────────────────────────────────────
// SAMPLE DATA  (no real users, no API)
// ────────────────────────────────────────────────────────────────────────────
const SAMPLE = {
  user: { name: "Jordan Reyes", plan: "growth" },
  stats: {
    campaigns_sent: 12,
    contacts_used: 4235,
    contacts_limit: 10000,
    accounts_connected: 18,
    warmup_active: 9,
  },
  campaigns: [
    { id: "c1", name: "Product Launch Outreach",   status: "completed", sent: 1842, total: 1842, color: "emerald" },
    { id: "c2", name: "Recruiter Follow-up",       status: "running",   sent: 386,  total: 1200, color: "blue" },
    { id: "c3", name: "Agency Prospecting",        status: "scheduled", sent: 0,    total: 950,  color: "violet" },
    { id: "c4", name: "Demo Invite Sequence",      status: "draft",     sent: 0,    total: 220,  color: "slate" },
  ],
  accounts: [
    { id: "a1", email: "sales@sampledomain.com",    daily: 100, sent: 87, status: "connected",  warmup: true  },
    { id: "a2", email: "growth@sampledomain.com",   daily: 75,  sent: 41, status: "connected",  warmup: true  },
    { id: "a3", email: "outreach@sampledomain.com", daily: 50,  sent: 32, status: "connected",  warmup: false },
    { id: "a4", email: "founders@sampledomain.com", daily: 50,  sent: 18, status: "connected",  warmup: true  },
    { id: "a5", email: "team@sampledomain.com",     daily: 50,  sent: 26, status: "connected",  warmup: false },
  ],
  drips: [
    { id: "d1", name: "Agency Outreach Sequence",  steps: 4, contacts: 312, status: "running"  },
    { id: "d2", name: "Recruitment Follow-up",      steps: 3, contacts: 184, status: "running"  },
    { id: "d3", name: "Demo Booking Flow",          steps: 5, contacts: 96,  status: "scheduled"},
  ],
  warmup: [
    { email: "sales@sampledomain.com",    sent: 26, replies: 18, score: 92 },
    { email: "growth@sampledomain.com",   sent: 31, replies: 22, score: 88 },
    { email: "outreach@sampledomain.com", sent: 18, replies: 11, score: 76 },
    { email: "founders@sampledomain.com", sent: 21, replies: 14, score: 81 },
    { email: "team@sampledomain.com",     sent: 14, replies:  9, score: 68 },
  ],
  activity_bars: [38, 52, 41, 67, 73, 58, 81, 92, 64, 70, 88, 95],
};

// Generic preview-action handler
const previewClick = () =>
  toast("This is a preview. Start your free trial to use RouteMail.", {
    description: "Sign up free — no credit card required.",
  });

// ────────────────────────────────────────────────────────────────────────────
// Inner reusable atoms (kept small + colocated to avoid bloat)
// ────────────────────────────────────────────────────────────────────────────
const StatCard = ({ icon: Icon, label, value, accent = "blue" }) => (
  <div className="rounded-xl border border-slate-200 bg-white p-4">
    <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
      <Icon size={12} className={`text-${accent}-500`} />
      {label}
    </div>
    <div className="text-xl md:text-2xl font-bold text-slate-900 mt-1">{value}</div>
  </div>
);

const StatusPill = ({ status, color }) => {
  const cls = {
    completed: "bg-emerald-100 text-emerald-700",
    running: "bg-blue-100 text-blue-700",
    scheduled: "bg-violet-100 text-violet-700",
    paused: "bg-amber-100 text-amber-700",
    draft: "bg-slate-100 text-slate-600",
    failed: "bg-rose-100 text-rose-700",
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
// Panel: Dashboard
// ────────────────────────────────────────────────────────────────────────────
function Panel_Dashboard() {
  const pct = Math.round((SAMPLE.stats.contacts_used / SAMPLE.stats.contacts_limit) * 100);
  return (
    <div className="grid md:grid-cols-[1fr_300px] gap-4">
      <div className="space-y-4">
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatCard icon={Send}     label="Campaigns sent" value={SAMPLE.stats.campaigns_sent} accent="blue" />
          <StatCard icon={Inbox}    label="Accounts"        value={SAMPLE.stats.accounts_connected} accent="violet" />
          <StatCard icon={Activity} label="Warmup active"   value={SAMPLE.stats.warmup_active} accent="emerald" />
          <StatCard icon={TrendingUp} label="Delivery"     value="98.4%" accent="fuchsia" />
        </div>

        <div className="rounded-xl border border-slate-200 overflow-hidden bg-white">
          <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold text-slate-900">Campaign Activity</div>
              <div className="text-xs text-slate-500">Latest campaigns and their status</div>
            </div>
            <FauxBtn>
              View All <ArrowRight size={12} />
            </FauxBtn>
          </div>
          <div className="divide-y divide-slate-100">
            {SAMPLE.campaigns.map((c) => {
              const p = c.total > 0 ? Math.round((c.sent / c.total) * 100) : 0;
              return (
                <div key={c.id} className="px-4 py-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-sm font-medium text-slate-900 truncate">{c.name}</span>
                      <StatusPill status={c.status} />
                    </div>
                    <div className="flex items-center gap-1.5">
                      {c.status === "draft" && (
                        <FauxBtn>
                          <Edit size={12} />
                        </FauxBtn>
                      )}
                      {c.status === "running" && (
                        <FauxBtn>
                          <Pause size={12} /> Pause
                        </FauxBtn>
                      )}
                      {c.status === "scheduled" && (
                        <FauxBtn>
                          <Pause size={12} /> Pause
                        </FauxBtn>
                      )}
                      {(c.status === "completed" || c.status === "running" || c.status === "scheduled") && (
                        <>
                          <FauxBtn>
                            <Eye size={12} /> View
                          </FauxBtn>
                          <FauxBtn>
                            <FileText size={12} /> Logs
                          </FauxBtn>
                        </>
                      )}
                    </div>
                  </div>
                  {c.total > 0 && c.status !== "draft" && (
                    <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
                      <span>{c.total} recipients</span>
                      <span className="text-emerald-600 font-medium">{c.sent} sent</span>
                      <span>· {p}%</span>
                      <div className="ml-auto w-24 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                        <div className={`h-full bg-${c.color}-500`} style={{ width: `${p}%` }} />
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
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
          <div className="text-xs text-slate-500 mb-1">Contacts this month</div>
          <div className="text-base font-bold text-slate-900">
            {SAMPLE.stats.contacts_used.toLocaleString()}
            <span className="text-slate-400 font-medium"> / {SAMPLE.stats.contacts_limit.toLocaleString()}</span>
          </div>
          <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden mt-2">
            <div className="h-full bg-emerald-500" style={{ width: `${pct}%` }} />
          </div>
          <div className="mt-1 text-[10px] text-slate-500">{pct}% used</div>
        </div>
        <div className="rounded-xl border border-slate-200 p-4 bg-white">
          <div className="text-xs font-semibold text-slate-700 mb-2">Today</div>
          <div className="space-y-1.5 text-xs text-slate-600">
            <div className="flex justify-between"><span>Sent</span><strong className="text-slate-900">2,418</strong></div>
            <div className="flex justify-between"><span>Delivered</span><strong className="text-emerald-600">98.4%</strong></div>
            <div className="flex justify-between"><span>Bounces</span><strong className="text-rose-600">12</strong></div>
            <div className="flex justify-between"><span>Replies</span><strong className="text-violet-600">164</strong></div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Panel: Campaign Builder
// ────────────────────────────────────────────────────────────────────────────
function Panel_Campaign() {
  return (
    <div className="grid md:grid-cols-[1.1fr_1fr] gap-4">
      <div className="space-y-3">
        <Field label="Campaign Name *" value="Product Launch Outreach" accent="violet" />
        <Field label="From Name" value="Jordan at RouteMail" accent="indigo" />
        <Field label="Email Accounts (5 selected)" value="sales@sampledomain.com + 4 others" accent="blue">
          <div className="mt-2 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-[11px] font-medium">
            <Send size={11} /> Total Daily Sending Capacity: <strong>325 emails/day</strong>
          </div>
        </Field>
        <Field label="Email List *" value="Founders Q1 — 4,582 contacts" accent="emerald" />
        <Field label="Subject Line *" value='"Hi {{first_name}}, quick question about {{company}}"' accent="blue" />
        <div>
          <FauxLabel accent="violet">Email Body *</FauxLabel>
          <div className="mt-1 rounded-md border border-slate-200 bg-white p-3 text-sm text-slate-700 leading-relaxed">
            <p>Hi <span className="bg-amber-100 px-0.5 rounded">{"{{first_name}}"}</span>,</p>
            <p className="mt-1.5">Quick question about <span className="bg-amber-100 px-0.5 rounded">{"{{company}}"}</span> — we help founders like you keep deliverability high while scaling outreach.</p>
            <p className="mt-1.5 text-slate-400">— Jordan at RouteMail</p>
          </div>
        </div>
        <div className="flex gap-2 pt-1">
          <FauxBtn variant="primary">Save Draft</FauxBtn>
          <FauxBtn variant="outline">Send Test Email</FauxBtn>
          <FauxBtn variant="primary">
            Send Campaign <ArrowRight size={12} />
          </FauxBtn>
        </div>
      </div>
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 self-start">
        <div className="text-xs font-semibold text-slate-700 mb-3">Live Preview</div>
        <div className="rounded-md bg-white border border-slate-200 p-4 text-sm text-slate-700 leading-relaxed shadow-sm">
          <div className="text-[10px] text-slate-400 uppercase font-semibold tracking-wider mb-1">Subject</div>
          <div className="font-semibold text-slate-900 mb-3">"Hi Sara, quick question about Acme Corp"</div>
          <p>Hi <span className="bg-amber-100 px-0.5 rounded">Sara</span>,</p>
          <p className="mt-2">Quick question about <span className="bg-amber-100 px-0.5 rounded">Acme Corp</span> — we help founders like you keep deliverability high while scaling outreach.</p>
          <p className="mt-2 text-slate-400">— Jordan at RouteMail</p>
        </div>
        <div className="mt-3 flex items-center gap-2 text-xs text-emerald-700">
          <CheckCircle2 size={12} /> Suppression list checked · 0 conflicts
        </div>
      </div>
    </div>
  );
}

const Field = ({ label, value, accent = "slate", children }) => (
  <div>
    <FauxLabel accent={accent}>{label}</FauxLabel>
    <div className="mt-1 px-3 py-2 rounded-md border border-slate-200 bg-white text-sm text-slate-800">{value}</div>
    {children}
  </div>
);
const FauxLabel = ({ children, accent }) => (
  <div className={`text-xs font-medium text-${accent}-700`}>{children}</div>
);

// ────────────────────────────────────────────────────────────────────────────
// Panel: Drip Campaigns
// ────────────────────────────────────────────────────────────────────────────
function Panel_Drip() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-slate-900">Drip Campaigns</div>
          <div className="text-xs text-slate-500">{SAMPLE.drips.length} active sequences</div>
        </div>
        <FauxBtn variant="primary"><Plus size={12} /> New Drip</FauxBtn>
      </div>
      <div className="grid md:grid-cols-3 gap-3">
        {SAMPLE.drips.map((d) => (
          <div key={d.id} className="rounded-xl border border-slate-200 bg-white p-4 hover:border-violet-300 transition-colors">
            <div className="flex items-start justify-between mb-2">
              <div className="text-sm font-semibold text-slate-900">{d.name}</div>
              <StatusPill status={d.status} />
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="text-slate-500">Steps<div className="text-slate-900 font-bold text-base">{d.steps}</div></div>
              <div className="text-slate-500">Contacts<div className="text-slate-900 font-bold text-base">{d.contacts}</div></div>
            </div>
            <FauxBtn className="mt-3 w-full justify-center" variant="outline">Open</FauxBtn>
          </div>
        ))}
      </div>
      {/* Sequence preview */}
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="text-xs font-semibold text-slate-700 mb-3">Sequence — Agency Outreach</div>
        <div className="space-y-2.5">
          {[
            { n: 1, t: "Intro",      d: "Day 0",     c: "blue" },
            { n: 2, t: "Follow-up",  d: "+ 3 days",  c: "violet" },
            { n: 3, t: "Case study", d: "+ 7 days",  c: "fuchsia" },
            { n: 4, t: "Final nudge",d: "+ 14 days", c: "rose" },
          ].map((s) => (
            <div key={s.n} className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-md bg-${s.c}-100 text-${s.c}-700 flex items-center justify-center text-xs font-bold`}>
                {s.n}
              </div>
              <div className="flex-1">
                <div className="text-sm font-medium text-slate-900">{s.t}</div>
                <div className="text-xs text-slate-500">{s.d} · 09:00 – 17:00 ET</div>
              </div>
              <Clock size={12} className="text-slate-400" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Panel: Email Accounts
// ────────────────────────────────────────────────────────────────────────────
function Panel_Accounts() {
  const totalCap = SAMPLE.accounts.reduce((s, a) => s + a.daily, 0);
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-slate-900">Email Accounts</div>
          <div className="text-xs text-slate-500">{SAMPLE.accounts.length} connected</div>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs font-medium">
            <Send size={11} /> {totalCap.toLocaleString()} emails/day capacity
          </span>
          <FauxBtn variant="primary"><Plus size={12} /> Add Account</FauxBtn>
        </div>
      </div>
      <div className="rounded-xl border border-slate-200 overflow-hidden bg-white">
        <div className="px-4 py-2.5 bg-slate-50 border-b border-slate-200 grid grid-cols-[2fr_1fr_1fr_1fr_auto] gap-3 text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
          <span>Account</span><span>Daily limit</span><span>Sent today</span><span>Warmup</span><span></span>
        </div>
        <div className="divide-y divide-slate-100">
          {SAMPLE.accounts.map((a) => (
            <div key={a.id} className="px-4 py-3 grid grid-cols-[2fr_1fr_1fr_1fr_auto] gap-3 items-center">
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-7 h-7 rounded-full bg-slate-100 flex items-center justify-center text-xs font-bold text-slate-600">
                  {a.email[0].toUpperCase()}
                </div>
                <span className="text-sm text-slate-800 truncate">{a.email}</span>
                <span className="ml-1 inline-flex items-center gap-1 text-[10px] text-emerald-700">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" /> connected
                </span>
              </div>
              <span className="text-xs text-slate-500">{a.daily}/day</span>
              <span className="text-xs text-slate-700 font-medium">{a.sent}</span>
              <span className={`text-xs ${a.warmup ? "text-emerald-600" : "text-slate-400"}`}>
                {a.warmup ? "Active" : "Off"}
              </span>
              <div className="flex gap-1">
                <FauxBtn>Edit</FauxBtn>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Panel: Warmup
// ────────────────────────────────────────────────────────────────────────────
function Panel_Warmup() {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <StatCard icon={Activity}    label="Active warmup"    value={`${SAMPLE.stats.warmup_active} inboxes`} accent="emerald" />
        <StatCard icon={CheckCircle2} label="Avg reply rate" value="71%"   accent="blue" />
        <StatCard icon={TrendingUp}  label="RTM label hits"   value="0.8%" accent="violet" />
      </div>
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
        <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 text-xs font-semibold text-slate-700">
          Warmup pool
        </div>
        <div className="divide-y divide-slate-100">
          {SAMPLE.warmup.map((w) => (
            <div key={w.email} className="px-4 py-3 flex items-center gap-3">
              <div className="w-7 h-7 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-xs font-bold">
                {w.email[0].toUpperCase()}
              </div>
              <div className="flex-1 text-sm text-slate-800 truncate">{w.email}</div>
              <span className="text-xs text-slate-500">Sent {w.sent}</span>
              <span className="text-xs text-slate-500">Replies {w.replies}</span>
              <div className="flex items-center gap-2">
                <div className="w-20 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                  <div className="h-full bg-emerald-500" style={{ width: `${w.score}%` }} />
                </div>
                <span className="text-xs font-bold text-slate-900 w-6 text-right">{w.score}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Panel: Usage / Subscription
// ────────────────────────────────────────────────────────────────────────────
function Panel_Usage() {
  const used = SAMPLE.stats.contacts_used;
  const limit = SAMPLE.stats.contacts_limit;
  const pct = Math.round((used / limit) * 100);
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-blue-50 p-5">
        <div className="flex items-center justify-between mb-2">
          <div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">Contacts used this month</div>
            <div className="text-2xl md:text-3xl font-bold text-slate-900">
              {used.toLocaleString()} <span className="text-base font-medium text-slate-500">/ {limit.toLocaleString()}</span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] text-slate-500">Remaining</div>
            <div className="text-base md:text-lg font-semibold text-emerald-700">{(limit - used).toLocaleString()}</div>
          </div>
        </div>
        <div className="h-2.5 w-full bg-white rounded-full overflow-hidden border border-slate-200">
          <div className="h-full bg-emerald-500" style={{ width: `${pct}%` }} />
        </div>
        <div className="mt-2 text-[11px] text-slate-500">
          {pct}% used. Sending follow-ups to existing contacts does NOT count again.
        </div>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs font-semibold text-slate-700">Current plan</div>
            <div className="text-base font-bold text-slate-900 flex items-center gap-1.5">
              <Crown size={14} className="text-amber-500" /> Growth — $149/year
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs text-slate-500">Renews</div>
            <div className="text-sm font-semibold text-slate-900 inline-flex items-center gap-1.5">
              <Calendar size={12} className="text-slate-500" /> Mar 14, 2026
            </div>
          </div>
        </div>
      </div>
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="text-xs font-semibold text-slate-700 mb-3">Sends — last 12 weeks</div>
        <div className="flex items-end gap-2 h-28">
          {SAMPLE.activity_bars.map((b, i) => (
            <div
              key={i}
              className="flex-1 bg-gradient-to-t from-blue-500 to-violet-500 rounded-t-md"
              style={{ height: `${b}%` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Tab definitions + main component
// ────────────────────────────────────────────────────────────────────────────
const DEMO_TABS = [
  { id: "dashboard", label: "Dashboard",        icon: Layers,    Panel: Panel_Dashboard },
  { id: "campaign",  label: "Campaign Builder", icon: Send,      Panel: Panel_Campaign  },
  { id: "drip",      label: "Drip Campaigns",   icon: Workflow,  Panel: Panel_Drip      },
  { id: "accounts",  label: "Email Accounts",   icon: Mail,      Panel: Panel_Accounts  },
  { id: "warmup",    label: "Warmup",           icon: Activity,  Panel: Panel_Warmup    },
  { id: "usage",     label: "Usage",            icon: BarChart3, Panel: Panel_Usage     },
];

export default function LiveDashboardDemo() {
  const [active, setActive] = useState("dashboard");
  const current = DEMO_TABS.find((t) => t.id === active) || DEMO_TABS[0];
  const ActivePanel = current.Panel;

  return (
    <div data-testid="live-dashboard-demo">
      {/* Tabs */}
      <div className="flex flex-wrap justify-center gap-2 mb-8" data-testid="demo-tabs">
        {DEMO_TABS.map((t) => {
          const Icon = t.icon;
          const isActive = active === t.id;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => setActive(t.id)}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 border ${
                isActive
                  ? "bg-slate-900 text-white border-slate-900 shadow-lg"
                  : "bg-white text-slate-600 border-slate-200 hover:border-slate-300 hover:text-slate-900"
              }`}
              data-testid={`demo-tab-${t.id}`}
            >
              <Icon size={14} />
              {t.label}
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
              app.routemail.co{active === "dashboard" ? "/dashboard" : `/${active}`}
            </div>
            <div className="text-[10px] text-slate-400 hidden md:block">Live preview · sample data</div>
          </div>
          {/* App shell: faux sidebar + active panel */}
          <div className="grid md:grid-cols-[200px_1fr] bg-white">
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
                </div>
              </div>
            </div>
            <AnimatePresence mode="wait">
              <motion.div
                key={current.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
                className="p-5 md:p-7 min-h-[440px]"
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
