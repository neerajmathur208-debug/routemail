import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate, Link } from "react-router-dom";
import {
  Mail,
  ArrowRight,
  Play,
  Check,
  Crown,
  Send,
  Workflow,
  Activity,
  ShieldCheck,
  Layers,
  Users,
  Briefcase,
  Building2,
  Target,
  UserPlus,
  Sparkles,
  Plus,
  Minus,
  Clock,
  Repeat,
  Zap,
  Shield,
  TrendingUp,
  CheckCircle2,
  XCircle,
  ChevronDown,
  BarChart3,
} from "lucide-react";
import { Button } from "../components/ui/button";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../components/ui/accordion";
import CustomPlanCard from "../components/CustomPlanCard";
import LiveDashboardDemo from "../components/landing/LiveDashboardDemo";

// ────────────────────────────────────────────────────────────────────────────
// Animation tokens
// ────────────────────────────────────────────────────────────────────────────
const fadeUp = {
  initial: { opacity: 0, y: 20 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-50px" },
  transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1] },
};

// ────────────────────────────────────────────────────────────────────────────
// Header
// ────────────────────────────────────────────────────────────────────────────
function Header({ onCtaClick, navigate }) {
  return (
    <header
      className="sticky top-0 z-50 bg-white/70 backdrop-blur-xl border-b border-slate-200/60"
      data-testid="landing-header"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 group" data-testid="landing-logo">
          <img
            src="/routemail-logo.png"
            alt="RouteMail"
            className="h-9 md:h-10 w-auto object-contain group-hover:scale-105 transition-transform"
          />
        </Link>

        <nav className="hidden md:flex items-center gap-8 text-sm text-slate-600">
          <a href="#features" className="hover:text-slate-900 transition-colors">Features</a>
          <a href="#demo" className="hover:text-slate-900 transition-colors">Demo</a>
          <a href="#pricing" className="hover:text-slate-900 transition-colors">Pricing</a>
          <a href="#faq" className="hover:text-slate-900 transition-colors">FAQ</a>
          <Link to="/blog" className="hover:text-slate-900 transition-colors">Blog</Link>
        </nav>

        <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
          <Button
            variant="ghost"
            onClick={() => navigate("/login")}
            className="text-slate-600 hover:text-slate-900 px-2.5 sm:px-4 text-sm"
            data-testid="header-login-btn"
          >
            Sign in
          </Button>
          <Button
            onClick={onCtaClick}
            className="bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700 text-white px-3 sm:px-4 text-sm whitespace-nowrap"
            data-testid="header-start-free-btn"
          >
            <span className="sm:hidden">Get Started</span>
            <span className="hidden sm:inline">Start Free</span>
          </Button>
        </div>
      </div>
    </header>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Hero
// ────────────────────────────────────────────────────────────────────────────
function Hero({ onPrimary, onSecondary }) {
  return (
    <section
      className="relative overflow-hidden border-b border-slate-200/60"
      data-testid="hero-section"
    >
      {/* Background grid + radial glow */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(99,102,241,0.10),transparent_55%),radial-gradient(ellipse_at_bottom,rgba(59,130,246,0.08),transparent_50%)] pointer-events-none" />
      <div className="absolute inset-0 [background-image:linear-gradient(to_right,rgba(15,23,42,0.04)_1px,transparent_1px),linear-gradient(to_bottom,rgba(15,23,42,0.04)_1px,transparent_1px)] [background-size:32px_32px] [mask-image:radial-gradient(ellipse_at_center,black_40%,transparent_75%)] pointer-events-none" />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-16 pb-20 md:pt-24 md:pb-28">
        <motion.div
          initial="initial"
          animate="whileInView"
          variants={{
            whileInView: { transition: { staggerChildren: 0.08 } },
          }}
          className="max-w-3xl"
        >
          <motion.div variants={fadeUp}>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-50 border border-blue-100 text-blue-700 text-xs font-semibold tracking-wide mb-6">
              <Sparkles size={12} />
              Multi-account email outreach, finally safe
            </div>
          </motion.div>

          <motion.h1
            variants={fadeUp}
            className="text-4xl sm:text-5xl lg:text-6xl tracking-tighter font-bold text-slate-900 leading-[1.05]"
            data-testid="hero-headline"
          >
            Send Bulk Emails Safely from{" "}
            <span className="bg-clip-text text-transparent bg-gradient-to-r from-blue-600 to-violet-600">
              Multiple Accounts
            </span>
          </motion.h1>

          <motion.p
            variants={fadeUp}
            className="mt-6 text-base sm:text-lg text-slate-600 leading-relaxed max-w-2xl"
            data-testid="hero-subhead"
          >
            RouteMail helps SMEs, agencies, recruiters, and consultants send outreach
            campaigns through multiple connected email accounts with smart rotation,
            scheduling, drip campaigns, warmup, and deliverability controls.
          </motion.p>

          <motion.div variants={fadeUp} className="mt-8 flex flex-col sm:flex-row gap-3">
            <Button
              size="lg"
              onClick={onPrimary}
              className="bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700 text-white h-12 px-6 text-base"
              data-testid="hero-start-free-btn"
            >
              Start Free
              <ArrowRight size={18} className="ml-1.5" />
            </Button>
            <Button
              size="lg"
              variant="outline"
              onClick={onSecondary}
              className="h-12 px-6 text-base border-slate-300"
              data-testid="hero-watch-demo-btn"
            >
              <Play size={16} className="mr-2" />
              Watch Demo
            </Button>
          </motion.div>

          <motion.div
            variants={fadeUp}
            className="mt-6 flex items-center gap-4 text-xs text-slate-500"
          >
            <span className="inline-flex items-center gap-1">
              <Check size={14} className="text-emerald-500" />
              No credit card required
            </span>
            <span className="inline-flex items-center gap-1">
              <Check size={14} className="text-emerald-500" />
              Free forever
            </span>
          </motion.div>
        </motion.div>

        {/* Dashboard mockup + floating stat cards */}
        <motion.div
          {...fadeUp}
          transition={{ delay: 0.25, duration: 0.6 }}
          className="relative mt-14 md:mt-20"
        >
          <DashboardMockup />

          {/* Floating stat cards */}
          <motion.div
            initial={{ opacity: 0, y: 20, x: -20 }}
            whileInView={{ opacity: 1, y: 0, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.5, duration: 0.5 }}
            className="hidden md:flex absolute -left-4 lg:-left-10 top-16 items-center gap-3 px-4 py-3 rounded-2xl bg-white/80 backdrop-blur-xl shadow-lg border border-white/60"
            data-testid="hero-stat-1"
          >
            <div className="w-9 h-9 rounded-xl bg-emerald-100 flex items-center justify-center">
              <TrendingUp size={18} className="text-emerald-600" />
            </div>
            <div>
              <div className="text-xs text-slate-500">Deliverability</div>
              <div className="text-base font-bold text-slate-900">98.4%</div>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 20, x: 20 }}
            whileInView={{ opacity: 1, y: 0, x: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.65, duration: 0.5 }}
            className="hidden md:flex absolute -right-2 lg:-right-6 bottom-12 items-center gap-3 px-4 py-3 rounded-2xl bg-white/80 backdrop-blur-xl shadow-lg border border-white/60"
            data-testid="hero-stat-2"
          >
            <div className="w-9 h-9 rounded-xl bg-violet-100 flex items-center justify-center">
              <Repeat size={18} className="text-violet-600" />
            </div>
            <div>
              <div className="text-xs text-slate-500">Accounts rotating</div>
              <div className="text-base font-bold text-slate-900">12 inboxes</div>
            </div>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Hero Mockup (HTML/Tailwind dashboard preview)
// ────────────────────────────────────────────────────────────────────────────
function DashboardMockup() {
  return (
    <div className="relative rounded-2xl border border-slate-200 bg-white shadow-2xl shadow-blue-500/10 overflow-hidden">
      {/* Browser chrome */}
      <div className="flex items-center gap-2 px-4 py-3 bg-slate-50 border-b border-slate-200">
        <div className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-red-400" />
          <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
        </div>
        <div className="ml-3 px-3 py-1 rounded-md bg-white border border-slate-200 text-xs text-slate-500 font-mono">
          app.routemail.co/dashboard
        </div>
      </div>
      {/* Body */}
      <div className="grid md:grid-cols-[200px_1fr]">
        {/* Sidebar */}
        <div className="hidden md:block bg-slate-50 border-r border-slate-200 p-4">
          <div className="flex items-center gap-2 mb-6">
            <div className="w-6 h-6 rounded bg-gradient-to-br from-blue-600 to-violet-600" />
            <span className="text-sm font-bold text-slate-900">RouteMail</span>
          </div>
          {[
            { label: "Dashboard", active: true },
            { label: "Campaigns" },
            { label: "Drip Campaigns" },
            { label: "Email Accounts" },
            { label: "Unibox" },
            { label: "Responses / Leads" },
            { label: "Do Not Email" },
            { label: "Subscription" },
          ].map((item) => (
            <div
              key={item.label}
              className={`flex items-center gap-2 px-2 py-1.5 rounded text-xs mb-1 ${
                item.active
                  ? "bg-blue-50 text-blue-700 font-semibold"
                  : "text-slate-500"
              }`}
            >
              <span className="w-1 h-1 rounded-full bg-current" />
              {item.label}
            </div>
          ))}
        </div>
        {/* Main */}
        <div className="p-5 md:p-6">
          {/* Stat strip */}
          <div className="grid grid-cols-3 gap-3 mb-5">
            {[
              { label: "Total Contacts", value: "12,450", color: "blue" },
              { label: "Open Rate", value: "42%", color: "emerald" },
              { label: "Replies (mo)", value: "186", color: "violet" },
            ].map((s) => (
              <div
                key={s.label}
                className="rounded-xl border border-slate-200 p-3"
              >
                <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">
                  {s.label}
                </div>
                <div className="text-lg md:text-xl font-bold text-slate-900 mt-0.5">
                  {s.value}
                </div>
              </div>
            ))}
          </div>

          {/* Campaign rows */}
          <div className="rounded-xl border border-slate-200 overflow-hidden">
            <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <div className="text-xs font-semibold text-slate-700">Campaign Activity</div>
              <div className="text-[10px] text-slate-500">Latest 4</div>
            </div>
            <div className="divide-y divide-slate-100">
              {[
                { name: "UK Law Firms Outreach", status: "running",   color: "blue",    pct: 78 },
                { name: "SaaS Outreach Q3",       status: "running",   color: "violet",  pct: 64 },
                { name: "Real Estate Ireland",   status: "scheduled", color: "amber",   pct: 0  },
                { name: "Recruitment Campaign",  status: "completed", color: "emerald", pct: 100 },
              ].map((c) => (
                <div key={c.name} className="px-4 py-2.5 flex items-center justify-between">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="text-xs font-medium text-slate-900 truncate w-40">
                      {c.name}
                    </div>
                    <span
                      className={`px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-${c.color}-100 text-${c.color}-700`}
                    >
                      {c.status}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-slate-500">
                    <span>{c.pct}%</span>
                    <div className="w-16 h-1.5 rounded-full bg-slate-100 overflow-hidden">
                      <div
                        className={`h-full bg-${c.color}-500`}
                        style={{ width: `${c.pct}%` }}
                      />
                    </div>
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

// ────────────────────────────────────────────────────────────────────────────
// Trust strip (micro stats / social proof)
// ────────────────────────────────────────────────────────────────────────────
function TrustStrip() {
  const stats = [
    { v: "12M+", l: "Emails routed/year" },
    { v: "98.4%", l: "Avg deliverability" },
    { v: "1.5k+", l: "Inboxes warmed" },
    { v: "47", l: "Countries" },
  ];
  return (
    <section className="border-b border-slate-200/60 bg-slate-50/50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
        {stats.map((s) => (
          <div key={s.l}>
            <div className="text-2xl md:text-3xl font-bold text-slate-900 tracking-tight">
              {s.v}
            </div>
            <div className="text-xs text-slate-500 mt-1">{s.l}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Interactive Demo (live React UI, sample data, no API calls)
// ────────────────────────────────────────────────────────────────────────────
function InteractiveDemo() {
  return (
    <section
      id="demo"
      className="border-b border-slate-200/60 py-20 md:py-28 bg-gradient-to-b from-white to-slate-50/60"
      data-testid="interactive-demo-section"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div {...fadeUp} className="text-center max-w-2xl mx-auto mb-10">
          <p className="text-xs font-bold tracking-[0.2em] uppercase text-blue-600 mb-3">
            Interactive Tour
          </p>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl tracking-tight font-semibold text-slate-900">
            Explore the actual RouteMail platform
          </h2>
          <p className="mt-3 text-base sm:text-lg text-slate-600 leading-relaxed">
            A live, interactive preview built from the same UI. Click any tab — sample data only, nothing leaves your browser.
          </p>
        </motion.div>
        <LiveDashboardDemo />
      </div>
    </section>
  );
}


// ────────────────────────────────────────────────────────────────────────────
// Feature Sections
// ────────────────────────────────────────────────────────────────────────────
const FEATURES = [
  {
    eyebrow: "Multi-Account Sending",
    title: "Send from multiple accounts without manual rotation.",
    desc: "Connect any number of inboxes and let RouteMail spread sends across them with smart per-account daily limits.",
    bullets: ["Per-account daily limits", "Smart rotation engine", "Live capacity tracker"],
    icon: Repeat,
    accent: "blue",
    Mock: () => (
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-lg">
        <div className="text-xs font-semibold text-slate-700 mb-3">Connected Accounts</div>
        <div className="space-y-2">
          {[
            { e: "maya@routemail.co", limit: "50/day", sent: 32, color: "emerald" },
            { e: "sales@routemail.co", limit: "100/day", sent: 87, color: "blue" },
            { e: "alex@routemail.co", limit: "75/day", sent: 41, color: "violet" },
          ].map((a) => (
            <div key={a.e} className="flex items-center gap-3">
              <div className={`w-2 h-2 rounded-full bg-${a.color}-500`} />
              <div className="flex-1 text-sm text-slate-800">{a.e}</div>
              <div className="text-xs text-slate-500">{a.sent} / {a.limit}</div>
            </div>
          ))}
        </div>
        <div className="mt-4 pt-4 border-t border-slate-100 text-xs text-slate-500 flex items-center gap-1.5">
          <Zap size={12} className="text-amber-500" />
          Total daily capacity: <strong className="text-slate-900">225 emails/day</strong>
        </div>
      </div>
    ),
  },
  {
    eyebrow: "Campaign Builder",
    title: "Personalize at scale with confidence.",
    desc: "Bring your CSV/Excel, map columns, insert variables, schedule — and never email anyone on your suppression list.",
    bullets: ["Variables & merge tags", "CSV/Excel import", "Suppression checks"],
    icon: Send,
    accent: "violet",
    Mock: () => (
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-lg space-y-3">
        <div className="rounded-lg bg-slate-50 border border-slate-200 p-3 text-xs">
          <div className="text-slate-400 font-semibold uppercase text-[10px] mb-1">Subject</div>
          <div className="text-slate-800">"Hi <span className="bg-amber-100 px-0.5 rounded">{"{{first_name}}"}</span>, about <span className="bg-amber-100 px-0.5 rounded">{"{{company}}"}</span>..."</div>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="px-2 py-1 rounded-md bg-blue-50 text-blue-700 font-mono">{"{{first_name}}"}</span>
          <span className="px-2 py-1 rounded-md bg-blue-50 text-blue-700 font-mono">{"{{company}}"}</span>
          <span className="px-2 py-1 rounded-md bg-blue-50 text-blue-700 font-mono">{"{{role}}"}</span>
        </div>
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-xs flex items-center gap-2">
          <Check size={14} className="text-emerald-600" />
          <span className="text-emerald-800">CSV uploaded — 4,582 contacts ready</span>
        </div>
      </div>
    ),
  },
  {
    eyebrow: "Drip Campaigns",
    title: "Multi-step sequences that respect human inboxes.",
    desc: "Compose N emails, choose delays, randomize send timing, set per-timezone working hours.",
    bullets: ["Multi-step flows", "Randomized send timing", "Timezone scheduling"],
    icon: Workflow,
    accent: "fuchsia",
    Mock: () => (
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-lg">
        <div className="space-y-3">
          {[
            { n: 1, t: "Intro", d: "Day 0", c: "blue" },
            { n: 2, t: "Follow-up", d: "+3 days", c: "violet" },
            { n: 3, t: "Case study", d: "+7 days", c: "fuchsia" },
          ].map((s) => (
            <div key={s.n} className="flex items-center gap-3">
              <div className={`w-8 h-8 rounded-md bg-${s.c}-100 text-${s.c}-700 flex items-center justify-center text-xs font-bold`}>
                {s.n}
              </div>
              <div className="flex-1">
                <div className="text-sm font-medium text-slate-900">{s.t}</div>
                <div className="text-xs text-slate-500">{s.d} · 09:00 – 17:00 ET</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    ),
  },
  {
    eyebrow: "Email Warmup",
    title: "Warm up new accounts before scaling outreach.",
    desc: "Automated reply patterns + RTM warmup labels build sender reputation safely so your real sends actually land.",
    bullets: ["Automated warmup interactions", "Per-account health score", "RTM warmup labels"],
    icon: Activity,
    accent: "emerald",
    Mock: () => (
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-lg space-y-3">
        {["maya@…", "sales@…", "alex@…"].map((e, i) => (
          <div key={e} className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-xs font-bold">
              {e[0].toUpperCase()}
            </div>
            <div className="flex-1 text-sm text-slate-800">{e}</div>
            <div className="w-24 h-1.5 rounded-full bg-slate-100 overflow-hidden">
              <div className="h-full bg-emerald-500" style={{ width: `${[92, 88, 76][i]}%` }} />
            </div>
            <span className="text-xs font-bold text-slate-900">{[92, 88, 76][i]}</span>
          </div>
        ))}
      </div>
    ),
  },
  {
    eyebrow: "Suppression & Compliance",
    title: "Never email anyone you shouldn't.",
    desc: "Global Do-Not-Email lists, per-campaign suppression, automatic unsubscribe handling. CAN-SPAM and GDPR friendly.",
    bullets: ["Global Do Not Email list", "Per-campaign suppression", "Automatic unsubscribe handling"],
    icon: ShieldCheck,
    accent: "rose",
    Mock: () => (
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-lg space-y-2">
        {[
          { e: "j.smith@example.com", state: "blocked", reason: "Suppression list" },
          { e: "amy@acme.io", state: "blocked", reason: "Unsubscribed" },
          { e: "bob@globex.io", state: "ok" },
          { e: "dana@initech.io", state: "ok" },
        ].map((r) => (
          <div key={r.e} className="flex items-center gap-3 text-xs">
            {r.state === "blocked" ? (
              <XCircle size={14} className="text-rose-500" />
            ) : (
              <CheckCircle2 size={14} className="text-emerald-500" />
            )}
            <span className="flex-1 text-slate-800">{r.e}</span>
            <span className="text-slate-400">{r.reason || "Will send"}</span>
          </div>
        ))}
      </div>
    ),
  },
];

function FeatureSections() {
  return (
    <section
      id="features"
      className="border-b border-slate-200/60 py-20 md:py-28 bg-white"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-24 md:space-y-32">
        {FEATURES.map((f, i) => {
          const Icon = f.icon;
          const Mock = f.Mock;
          const reverse = i % 2 === 1;
          return (
            <motion.div
              key={f.title}
              {...fadeUp}
              className={`grid md:grid-cols-2 gap-10 md:gap-16 items-center ${
                reverse ? "md:[&>*:first-child]:order-2" : ""
              }`}
              data-testid={`feature-${i}`}
            >
              <div>
                <div className="inline-flex items-center gap-2 mb-3">
                  <div className={`w-8 h-8 rounded-lg bg-${f.accent}-100 text-${f.accent}-700 flex items-center justify-center`}>
                    <Icon size={16} />
                  </div>
                  <p className={`text-xs font-bold tracking-[0.2em] uppercase text-${f.accent}-700`}>
                    {f.eyebrow}
                  </p>
                </div>
                <h3 className="text-2xl sm:text-3xl tracking-tight font-semibold text-slate-900 leading-snug">
                  {f.title}
                </h3>
                <p className="mt-3 text-base text-slate-600 leading-relaxed">{f.desc}</p>
                <ul className="mt-5 space-y-2">
                  {f.bullets.map((b) => (
                    <li key={b} className="flex items-center gap-2 text-sm text-slate-700">
                      <Check size={16} className={`text-${f.accent}-500`} />
                      {b}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <Mock />
              </div>
            </motion.div>
          );
        })}
      </div>
    </section>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Use Cases
// ────────────────────────────────────────────────────────────────────────────
const PERSONAS = [
  { icon: Briefcase,  title: "Agencies",   desc: "Run client outreach across many sender personas in parallel." },
  { icon: UserPlus,   title: "Recruiters", desc: "Reach candidates without your domain getting blacklisted." },
  { icon: Users,      title: "Consultants",desc: "Stay top-of-mind with founders and execs at your own pace." },
  { icon: Building2,  title: "Founders",   desc: "Talk to investors, partners and early customers at scale." },
  { icon: Target,     title: "Sales Teams",desc: "Pipeline coverage that doesn't burn your sender domain." },
];

function UseCases() {
  return (
    <section className="border-b border-slate-200/60 py-20 md:py-28 bg-slate-50/50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div {...fadeUp} className="text-center max-w-2xl mx-auto mb-12">
          <p className="text-xs font-bold tracking-[0.2em] uppercase text-blue-600 mb-3">
            Use cases
          </p>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl tracking-tight font-semibold text-slate-900">
            Built for teams who live in the inbox.
          </h2>
        </motion.div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {PERSONAS.map((p, i) => {
            const Icon = p.icon;
            return (
              <motion.div
                key={p.title}
                {...fadeUp}
                transition={{ ...fadeUp.transition, delay: i * 0.05 }}
                className="rounded-xl bg-white border border-slate-200 p-5 hover:-translate-y-1 hover:shadow-xl transition-all duration-300"
                data-testid={`persona-${p.title.toLowerCase()}`}
              >
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-100 to-violet-100 text-violet-700 flex items-center justify-center">
                  <Icon size={18} />
                </div>
                <h4 className="mt-4 text-base font-semibold text-slate-900">{p.title}</h4>
                <p className="mt-1 text-xs text-slate-500 leading-relaxed">{p.desc}</p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Why RouteMail
// ────────────────────────────────────────────────────────────────────────────
const WHY = [
  { icon: Repeat,       title: "Smart rotation",          desc: "Spread sends across inboxes automatically." },
  { icon: Activity,     title: "Built-in warmup",         desc: "Reputation grows in the background." },
  { icon: Workflow,     title: "Drip campaigns",          desc: "Multi-step sequences with timezone smarts." },
  { icon: Shield,       title: "Deliverability controls", desc: "Suppression, throttling, RTM labels." },
  { icon: Crown,        title: "Affordable annual pricing", desc: "Pay for the people you reach, not the inboxes." },
];

function WhyRouteMail() {
  return (
    <section className="border-b border-slate-200/60 py-20 md:py-28 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div {...fadeUp} className="text-center max-w-2xl mx-auto mb-12">
          <p className="text-xs font-bold tracking-[0.2em] uppercase text-blue-600 mb-3">
            Why RouteMail
          </p>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl tracking-tight font-semibold text-slate-900">
            Everything you need, nothing you don't.
          </h2>
        </motion.div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {WHY.map((w, i) => {
            const Icon = w.icon;
            return (
              <motion.div
                key={w.title}
                {...fadeUp}
                transition={{ ...fadeUp.transition, delay: i * 0.05 }}
                className="rounded-xl border border-slate-200 p-5 bg-slate-50/40"
              >
                <Icon size={20} className="text-blue-600" />
                <h4 className="mt-3 font-semibold text-slate-900">{w.title}</h4>
                <p className="mt-1 text-xs text-slate-500 leading-relaxed">{w.desc}</p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Pricing
// ────────────────────────────────────────────────────────────────────────────
function PricingCard({ name, contacts, price, period, accent = "slate", featured = false, ctaLabel, onCta, testId, footnote }) {
  return (
    <motion.div
      {...fadeUp}
      className={`relative rounded-2xl p-6 md:p-8 border-2 hover:-translate-y-1 hover:shadow-xl transition-all duration-300 ${
        featured
          ? "border-blue-500 bg-gradient-to-br from-blue-600 to-violet-600 text-white shadow-xl"
          : "border-slate-200 bg-white"
      }`}
      data-testid={testId}
    >
      {featured && (
        <div className="absolute -top-3 left-6">
          <span className="inline-flex items-center gap-1 px-3 py-1 bg-amber-400 text-amber-900 rounded-full text-xs font-bold">
            <Crown size={12} />
            MOST POPULAR
          </span>
        </div>
      )}
      <h3 className={`text-2xl font-bold ${featured ? "text-white" : "text-slate-900"}`}>{name}</h3>
      <p className={`text-sm mt-1 ${featured ? "text-white/80" : "text-slate-500"}`}>
        {contacts} unique contacts/month
      </p>
      <div className="mt-5 flex items-baseline gap-2">
        <span className={`text-4xl md:text-5xl font-bold ${featured ? "text-white" : "text-slate-900"}`}>{price}</span>
        <span className={`text-base ${featured ? "text-white/80" : "text-slate-500"}`}>{period}</span>
      </div>
      <ul className={`mt-5 space-y-2.5 ${featured ? "text-white/95" : "text-slate-700"}`}>
        <li className="flex items-start gap-2 text-sm">
          <Check size={16} className={featured ? "text-white mt-0.5 shrink-0" : `text-${accent}-500 mt-0.5 shrink-0`} />
          <span><strong>{contacts}</strong> unique contacts/month</span>
        </li>
        <li className="flex items-start gap-2 text-sm">
          <Check size={16} className={featured ? "text-white mt-0.5 shrink-0" : `text-${accent}-500 mt-0.5 shrink-0`} />
          Unlimited follow-ups
        </li>
        <li className="flex items-start gap-2 text-sm">
          <Check size={16} className={featured ? "text-white mt-0.5 shrink-0" : `text-${accent}-500 mt-0.5 shrink-0`} />
          Smart rotation, drip campaigns, warmup
        </li>
        <li className="flex items-start gap-2 text-sm">
          <Check size={16} className={featured ? "text-white mt-0.5 shrink-0" : `text-${accent}-500 mt-0.5 shrink-0`} />
          Suppression &amp; deliverability controls
        </li>
      </ul>
      <Button
        onClick={onCta}
        className={`mt-6 w-full h-11 ${
          featured
            ? "bg-white text-blue-700 hover:bg-blue-50"
            : "bg-slate-900 text-white hover:bg-slate-800"
        }`}
      >
        {ctaLabel}
      </Button>
      {footnote && (
        <p className={`mt-3 text-center text-[11px] ${featured ? "text-white/80" : "text-slate-500"}`}>
          {footnote}
        </p>
      )}
    </motion.div>
  );
}

function PricingSection({ navigate, onPrimary }) {
  return (
    <section id="pricing" className="border-b border-slate-200/60 py-20 md:py-28 bg-white">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div {...fadeUp} className="text-center max-w-2xl mx-auto mb-10">
          <p className="text-xs font-bold tracking-[0.2em] uppercase text-blue-600 mb-3">
            Pricing
          </p>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl tracking-tight font-semibold text-slate-900">
            Pay for the people you reach.
          </h2>
          <p className="mt-3 text-base sm:text-lg text-slate-600 leading-relaxed">
            Plans are based on monthly <strong>unique contacts</strong> contacted, not total emails sent.
          </p>
          <div className="mt-4 inline-flex flex-col sm:flex-row gap-2 sm:gap-4 px-4 py-3 rounded-xl bg-blue-50 border border-blue-100 text-xs text-blue-800 max-w-2xl">
            <span className="inline-flex items-center gap-1.5">
              <Check size={12} className="text-emerald-500" />
              Unlimited follow-ups to the same contact
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Check size={12} className="text-emerald-500" />
              Only <em>new</em> unique recipients count
            </span>
          </div>
        </motion.div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6" data-testid="pricing-grid">
          <PricingCard
            name="Free"
            contacts="500"
            price="$0"
            period="/year"
            accent="slate"
            ctaLabel="Start Free"
            onCta={onPrimary}
            testId="pricing-card-free"
            footnote="Free forever — no credit card"
          />
          <PricingCard
            name="Starter"
            contacts="4,000"
            price="$99"
            period="/year"
            accent="blue"
            ctaLabel="Choose Starter"
            onCta={onPrimary}
            testId="pricing-card-starter"
          />
          <PricingCard
            name="Growth"
            contacts="10,000"
            price="$149"
            period="/year"
            accent="emerald"
            featured
            ctaLabel="Choose Growth"
            onCta={onPrimary}
            testId="pricing-card-growth"
          />
          <CustomPlanCard variant="public" navigate={navigate} />
        </div>

        <p className="mt-8 text-center text-xs text-slate-500 max-w-xl mx-auto">
          Need an enterprise rollout? Email{" "}
          <a href="mailto:support@routemail.co" className="text-blue-600 underline">support@routemail.co</a>.
        </p>
      </div>
    </section>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// FAQ
// ────────────────────────────────────────────────────────────────────────────
const FAQS = [
  {
    q: "What is RouteMail?",
    a: "RouteMail is a multi-account email outreach platform for SMEs, agencies, recruiters, founders, and sales teams. Connect multiple inboxes, build campaigns and drip sequences, warm up new accounts, and protect your sender reputation — all from one place.",
  },
  {
    q: "How do contact limits work?",
    a: "Plans are priced by the number of unique people you contact in a calendar month. A contact is counted once the first time you email them in a month. Every follow-up to the same person — across the same month or any campaign — is free and does not count again.",
  },
  {
    q: "Can I connect multiple email accounts?",
    a: "Yes. RouteMail is built around safe multi-account sending. You can connect any number of SMTP inboxes, set per-account daily limits, and let our smart rotation engine spread sends across them.",
  },
  {
    q: "Does RouteMail support drip campaigns?",
    a: "Yes — multi-step drip sequences with per-step delays, timezone-aware schedules, randomized send timing, and easy step duplication.",
  },
  {
    q: "Is there a free plan?",
    a: "Yes — RouteMail has a Free Plan that's free forever. You get 500 unique contacts/month and up to 3 connected accounts, with no credit card and no expiry. Upgrade any time you need more monthly contacts.",
  },
];

function FAQ() {
  return (
    <section
      id="faq"
      className="border-b border-slate-200/60 py-20 md:py-28 bg-slate-50/50"
    >
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div {...fadeUp} className="text-center mb-10">
          <p className="text-xs font-bold tracking-[0.2em] uppercase text-blue-600 mb-3">
            FAQ
          </p>
          <h2 className="text-3xl sm:text-4xl lg:text-5xl tracking-tight font-semibold text-slate-900">
            Questions, answered.
          </h2>
        </motion.div>
        <Accordion type="single" collapsible className="w-full" data-testid="faq-accordion">
          {FAQS.map((f, i) => (
            <AccordionItem
              key={i}
              value={`faq-${i}`}
              className="border-b border-slate-200"
            >
              <AccordionTrigger
                className="text-left text-base font-semibold text-slate-900 hover:no-underline"
                data-testid={`faq-q-${i}`}
              >
                {f.q}
              </AccordionTrigger>
              <AccordionContent className="text-sm text-slate-600 leading-relaxed">
                {f.a}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </section>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// CTA banner
// ────────────────────────────────────────────────────────────────────────────
function CtaBanner({ onPrimary }) {
  return (
    <section className="py-20 md:py-24 bg-white">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        <motion.div
          {...fadeUp}
          className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-blue-600 to-violet-600 p-10 md:p-14 text-center text-white"
        >
          <div className="absolute inset-0 [background-image:linear-gradient(to_right,rgba(255,255,255,0.08)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.08)_1px,transparent_1px)] [background-size:32px_32px] [mask-image:radial-gradient(ellipse_at_center,black_30%,transparent_70%)] pointer-events-none" />
          <div className="relative">
            <h3 className="text-3xl md:text-4xl font-semibold tracking-tight">
              Stop burning domains. Start landing in inboxes.
            </h3>
            <p className="mt-3 text-white/85 max-w-xl mx-auto">
              Start free forever. Upgrade when you need more monthly contacts.
            </p>
            <Button
              size="lg"
              onClick={onPrimary}
              className="mt-7 bg-white text-blue-700 hover:bg-blue-50 h-12 px-7"
              data-testid="cta-banner-btn"
            >
              Start Free
              <ArrowRight size={18} className="ml-1.5" />
            </Button>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Footer
// ────────────────────────────────────────────────────────────────────────────
function Footer() {
  return (
    <footer className="bg-slate-50 border-t border-slate-200" data-testid="landing-footer">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid md:grid-cols-[2fr_1fr_1fr] gap-8">
          <div>
            <Link to="/" className="flex items-center gap-2">
              <img
                src="/routemail-logo.png"
                alt="RouteMail"
                className="h-10 w-auto object-contain"
              />
            </Link>
            <p className="mt-3 text-sm text-slate-500 max-w-sm leading-relaxed">
              Send bulk email safely from multiple accounts — built for SMEs, agencies, recruiters, and consultants.
            </p>
            <p className="mt-4 text-sm">
              <a
                href="mailto:support@routemail.co"
                className="text-blue-600 hover:underline"
                data-testid="footer-support-email"
              >
                support@routemail.co
              </a>
            </p>
          </div>
          <div>
            <h5 className="text-xs font-bold tracking-[0.2em] uppercase text-slate-400 mb-3">
              Product
            </h5>
            <ul className="space-y-2 text-sm">
              <li><Link to="/blog" className="text-slate-600 hover:text-slate-900">Blog</Link></li>
              <li><a href="#features" className="text-slate-600 hover:text-slate-900">Features</a></li>
              <li><a href="#pricing" className="text-slate-600 hover:text-slate-900">Pricing</a></li>
              <li><a href="#faq" className="text-slate-600 hover:text-slate-900">FAQ</a></li>
            </ul>
          </div>
          <div>
            <h5 className="text-xs font-bold tracking-[0.2em] uppercase text-slate-400 mb-3">
              Legal
            </h5>
            <ul className="space-y-2 text-sm">
              <li><Link to="/privacy-policy" className="text-slate-600 hover:text-slate-900">Privacy Policy</Link></li>
              <li><Link to="/terms-and-conditions" className="text-slate-600 hover:text-slate-900">Terms</Link></li>
              <li><Link to="/anti-spam-policy" className="text-slate-600 hover:text-slate-900">Anti-Spam Policy</Link></li>
              <li><Link to="/gdpr-compliance" className="text-slate-600 hover:text-slate-900">GDPR</Link></li>
            </ul>
          </div>
        </div>
        <div className="mt-10 pt-6 border-t border-slate-200 text-xs text-slate-500 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <span>© {new Date().getFullYear()} RouteMail. All rights reserved.</span>
          <span>Made with care for safe sending.</span>
        </div>
      </div>
    </footer>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// Page entry
// ────────────────────────────────────────────────────────────────────────────
export default function LandingPage() {
  const navigate = useNavigate();
  const onPrimary = () => navigate("/register");
  const onWatchDemo = () => {
    const el = document.getElementById("demo");
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="min-h-screen bg-white text-slate-900 antialiased">
      <Header onCtaClick={onPrimary} navigate={navigate} />
      <Hero onPrimary={onPrimary} onSecondary={onWatchDemo} />
      <TrustStrip />
      <InteractiveDemo />
      <FeatureSections />
      <UseCases />
      <PricingSection navigate={navigate} onPrimary={onPrimary} />
      <WhyRouteMail />
      <FAQ />
      <CtaBanner onPrimary={onPrimary} />
      <Footer />
    </div>
  );
}
