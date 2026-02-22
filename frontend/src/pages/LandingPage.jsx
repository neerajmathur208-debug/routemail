import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  Mail,
  Upload,
  RefreshCw,
  Shield,
  BarChart3,
  Check,
  ArrowRight,
  Users,
  Briefcase,
  Target,
  Calendar,
  MessageSquare,
  Building,
  Sparkles,
  Lock,
  Clock,
  TrendingUp,
  Inbox,
  Send,
  Layers,
} from "lucide-react";
import { Button } from "../components/ui/button";

export default function LandingPage() {
  const navigate = useNavigate();
  
  // "Start Free" button - redirects to register page
  const handleStartFree = () => {
    navigate("/register");
  };
  
  // Google OAuth direct login
  const handleGoogleLogin = () => {
    const redirectUrl = window.location.origin + "/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  const painPoints = [
    "Sending limits on a single email account",
    "Emails landing in spam",
    "Manual follow-ups taking hours",
    "Complicated cold email tools built for large teams",
    "Overpriced software with features you'll never use",
  ];

  const howItWorks = [
    {
      step: "01",
      icon: Mail,
      title: "Connect Multiple Email Accounts",
      description: "Gmail, Outlook, or custom domains — plug in as many as you want.",
    },
    {
      step: "02",
      icon: Upload,
      title: "Upload Your Prospect List",
      description: "CSV upload. Clean, simple, fast.",
    },
    {
      step: "03",
      icon: RefreshCw,
      title: "We Rotate & Send Automatically",
      description: "Emails are distributed across accounts to protect deliverability and increase inbox placement.",
    },
    {
      step: "04",
      icon: BarChart3,
      title: "Track Performance",
      description: "Monitor sends, opens, replies, and account health in one dashboard.",
    },
  ];

  const differentiators = [
    "Built specifically for small businesses",
    "Rotational sending protects domain reputation",
    "No unnecessary enterprise complexity",
    "Clean, intuitive dashboard",
    "Affordable pricing",
    "Scales as you grow",
  ];

  const useCases = [
    { icon: Building, text: "Agencies doing outbound prospecting" },
    { icon: Briefcase, text: "Local service businesses" },
    { icon: Users, text: "Recruiters" },
    { icon: Target, text: "B2B consultants" },
    { icon: Sparkles, text: "Founders doing manual outreach" },
    { icon: Calendar, text: "Businesses generating appointments via cold email" },
  ];

  const deliverabilityFeatures = [
    "Sending limits per account",
    "Natural sending rotation",
    "Warm-up readiness",
    "Clean sending patterns",
    "Spam-risk reduction",
  ];

  const dashboardSteps = [
    "Add accounts",
    "Upload leads",
    "Launch campaign",
    "Monitor replies",
  ];

  return (
    <div className="min-h-screen bg-[#faf9f7]">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-white/90 backdrop-blur-md border-b border-slate-100">
        <div className="max-w-[1300px] mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <img 
              src="/routemail-logo.png" 
              alt="RoutEmail" 
              className="h-9 w-auto object-contain"
            />
          </div>
          <div className="flex items-center gap-4">
            <Button
              onClick={() => navigate("/login")}
              variant="ghost"
              className="text-slate-600 hover:text-slate-900"
              data-testid="nav-login-btn"
            >
              Sign In
            </Button>
            <Button
              onClick={handleStartFree}
              className="bg-slate-900 hover:bg-slate-800 text-white rounded-full px-6"
              data-testid="nav-trial-btn"
            >
              Start Free
            </Button>
          </div>
        </div>
      </nav>

      {/* 1️⃣ HERO SECTION */}
      <section className="pt-32 pb-24 px-6">
        <div className="max-w-[1300px] mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="text-center max-w-4xl mx-auto"
          >
            <h1 className="font-heading font-extrabold text-4xl sm:text-5xl lg:text-6xl text-slate-900 leading-tight">
              Send Bulk Emails Safely
              <span className="block text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-violet-600">
                from Multiple Accounts.
              </span>
            </h1>
            <p className="mt-6 text-xl text-slate-600 font-medium">
              A simple rotational email tool built for SME businesses.
            </p>
            <p className="mt-4 text-lg text-slate-500 max-w-2xl mx-auto leading-relaxed">
              Connect multiple email accounts. Upload your list.
              We rotate, send, and optimise delivery — so your emails land in inboxes, not spam.
            </p>
            <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
              <Button
                onClick={handleStartFree}
                size="lg"
                className="bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700 text-white px-8 py-6 text-lg rounded-full shadow-lg shadow-blue-500/25"
                data-testid="hero-get-started-btn"
              >
                Start Free Trial
                <ArrowRight size={20} className="ml-2" />
              </Button>
              <Button
                variant="outline"
                size="lg"
                className="px-8 py-6 text-lg rounded-full border-2 border-slate-300 hover:border-slate-400"
                data-testid="hero-demo-btn"
              >
                Book a Demo
              </Button>
            </div>
          </motion.div>

          {/* Hero Video/Animation Preview */}
          <motion.div
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.3 }}
            className="mt-20"
          >
            <div className="relative bg-gradient-to-br from-slate-100 to-slate-50 rounded-[20px] p-2 shadow-2xl shadow-slate-300/50 max-w-[950px] mx-auto">
              <div className="bg-white rounded-[16px] overflow-hidden">
                {/* Browser Chrome */}
                <div className="flex items-center gap-2 px-4 py-3 bg-slate-50 border-b border-slate-100">
                  <div className="w-3 h-3 rounded-full bg-red-400" />
                  <div className="w-3 h-3 rounded-full bg-yellow-400" />
                  <div className="w-3 h-3 rounded-full bg-green-400" />
                  <div className="flex-1 flex justify-center">
                    <div className="bg-white rounded-md px-4 py-1 text-xs text-slate-400 border border-slate-200">
                      app.rotation.io/dashboard
                    </div>
                  </div>
                </div>
                {/* Video Container - Animated Product Demo */}
                <div className="aspect-[16/9] bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 relative overflow-hidden">
                  {/* Animated Dashboard Simulation */}
                  <div className="absolute inset-0 p-6">
                    {/* Sidebar */}
                    <div className="absolute left-0 top-0 bottom-0 w-16 bg-slate-800/50 flex flex-col items-center py-6 gap-4">
                      <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-500" />
                      <div className="w-8 h-8 rounded-lg bg-slate-700/50" />
                      <div className="w-8 h-8 rounded-lg bg-slate-700/50" />
                      <div className="w-8 h-8 rounded-lg bg-slate-700/50" />
                    </div>
                    {/* Main Content */}
                    <div className="ml-20 h-full flex flex-col">
                      {/* Stats Row */}
                      <div className="grid grid-cols-4 gap-3 mb-4">
                        <motion.div 
                          animate={{ opacity: [0.5, 1, 0.5] }}
                          transition={{ duration: 2, repeat: Infinity }}
                          className="bg-gradient-to-br from-blue-500/20 to-violet-500/20 rounded-xl p-3 border border-blue-500/30"
                        >
                          <p className="text-[10px] text-blue-300">Connected</p>
                          <p className="text-xl font-bold text-white">4</p>
                        </motion.div>
                        <div className="bg-slate-700/30 rounded-xl p-3 border border-slate-600/30">
                          <p className="text-[10px] text-slate-400">Contacts</p>
                          <p className="text-xl font-bold text-white">2.4k</p>
                        </div>
                        <motion.div 
                          animate={{ scale: [1, 1.02, 1] }}
                          transition={{ duration: 1.5, repeat: Infinity }}
                          className="bg-slate-700/30 rounded-xl p-3 border border-emerald-500/30"
                        >
                          <p className="text-[10px] text-emerald-400">Sent Today</p>
                          <p className="text-xl font-bold text-emerald-400">847</p>
                        </motion.div>
                        <div className="bg-slate-700/30 rounded-xl p-3 border border-slate-600/30">
                          <p className="text-[10px] text-slate-400">Campaigns</p>
                          <p className="text-xl font-bold text-white">8</p>
                        </div>
                      </div>
                      {/* Chart Area */}
                      <div className="flex-1 bg-slate-800/30 rounded-xl p-4 border border-slate-700/30">
                        <div className="flex items-center justify-between mb-3">
                          <span className="text-xs text-slate-400">Sending Activity</span>
                          <span className="text-[10px] text-slate-500">Last 7 days</span>
                        </div>
                        <div className="flex items-end gap-2 h-24">
                          {[40, 65, 45, 80, 55, 90, 70].map((h, i) => (
                            <motion.div
                              key={i}
                              initial={{ height: 0 }}
                              animate={{ height: `${h}%` }}
                              transition={{ duration: 0.5, delay: i * 0.1, repeat: Infinity, repeatDelay: 3 }}
                              className="flex-1 bg-gradient-to-t from-blue-500 to-violet-500 rounded-t opacity-80"
                            />
                          ))}
                        </div>
                      </div>
                      {/* Activity Row */}
                      <div className="mt-3 grid grid-cols-2 gap-3">
                        <div className="bg-slate-800/30 rounded-xl p-3 border border-slate-700/30">
                          <p className="text-[10px] text-slate-400 mb-2">Recent Campaigns</p>
                          <div className="space-y-2">
                            <motion.div 
                              animate={{ x: [0, 2, 0] }}
                              transition={{ duration: 2, repeat: Infinity }}
                              className="flex items-center gap-2"
                            >
                              <div className="w-2 h-2 rounded-full bg-emerald-400" />
                              <span className="text-[10px] text-slate-300">Q4 Outreach</span>
                              <span className="text-[10px] text-emerald-400 ml-auto">Running</span>
                            </motion.div>
                            <div className="flex items-center gap-2">
                              <div className="w-2 h-2 rounded-full bg-blue-400" />
                              <span className="text-[10px] text-slate-300">Holiday Promo</span>
                              <span className="text-[10px] text-blue-400 ml-auto">Scheduled</span>
                            </div>
                          </div>
                        </div>
                        <div className="bg-slate-800/30 rounded-xl p-3 border border-slate-700/30">
                          <p className="text-[10px] text-slate-400 mb-2">Account Rotation</p>
                          <div className="flex items-center gap-1">
                            {[1,2,3,4].map((_, i) => (
                              <motion.div
                                key={i}
                                animate={{ opacity: [0.3, 1, 0.3] }}
                                transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.3 }}
                                className="flex-1 h-2 rounded-full bg-gradient-to-r from-blue-500 to-violet-500"
                              />
                            ))}
                          </div>
                          <p className="text-[10px] text-slate-500 mt-2">Auto-rotating across 4 accounts</p>
                        </div>
                      </div>
                    </div>
                  </div>
                  {/* Play overlay hint */}
                  <div className="absolute bottom-4 right-4 flex items-center gap-2 bg-black/40 backdrop-blur-sm rounded-full px-3 py-1.5">
                    <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                    <span className="text-[10px] text-white/80">Live Preview</span>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* 2️⃣ DASHBOARD PREVIEW (Moved here - right after Hero) */}
      <section className="py-24 px-6 bg-gradient-to-br from-slate-50 to-slate-100">
        <div className="max-w-[1300px] mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            viewport={{ once: true }}
            className="text-center mb-14"
          >
            <h2 className="font-heading font-extrabold text-3xl sm:text-4xl text-slate-900 mb-6">
              Simple Dashboard. Zero Learning Curve.
            </h2>
            <div className="flex flex-wrap items-center justify-center gap-4 mt-8">
              {dashboardSteps.map((step, index) => (
                <div key={index} className="flex items-center gap-2">
                  <div className="w-9 h-9 bg-gradient-to-br from-blue-600 to-violet-600 text-white rounded-full flex items-center justify-center text-sm font-bold shadow-lg shadow-blue-500/25">
                    {index + 1}
                  </div>
                  <span className="text-slate-700 font-semibold">{step}</span>
                  {index < dashboardSteps.length - 1 && (
                    <ArrowRight size={18} className="text-slate-300 ml-2" />
                  )}
                </div>
              ))}
            </div>
            <p className="text-slate-500 mt-6 text-lg">No technical knowledge required.</p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.6 }}
            viewport={{ once: true }}
            className="relative max-w-5xl mx-auto"
          >
            <div className="bg-white rounded-[24px] shadow-2xl shadow-slate-300/60 overflow-hidden border border-slate-200">
              {/* Browser Chrome */}
              <div className="flex items-center gap-2 px-5 py-4 bg-slate-100 border-b border-slate-200">
                <div className="w-3 h-3 rounded-full bg-red-400" />
                <div className="w-3 h-3 rounded-full bg-yellow-400" />
                <div className="w-3 h-3 rounded-full bg-green-400" />
                <div className="flex-1 flex justify-center">
                  <div className="bg-white rounded-lg px-6 py-1.5 text-sm text-slate-500 border border-slate-200 shadow-sm">
                    app.rotation.io/dashboard
                  </div>
                </div>
              </div>
              
              {/* Dashboard Content */}
              <div className="p-6 sm:p-8 bg-slate-50">
                {/* Dashboard Header */}
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h3 className="text-xl font-bold text-slate-900">Welcome back, Sarah</h3>
                    <p className="text-sm text-slate-500">Here's what's happening with your campaigns</p>
                  </div>
                  <button className="bg-gradient-to-r from-blue-600 to-violet-600 text-white px-4 py-2 rounded-lg text-sm font-medium shadow-lg shadow-blue-500/25">
                    + New Campaign
                  </button>
                </div>
                
                {/* Stats Grid - 3 cards only (removed Open Rate) */}
                <div className="grid grid-cols-3 gap-4 mb-6">
                  <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm">
                    <div className="flex items-center gap-2 mb-2">
                      <Mail size={16} className="text-blue-600" />
                      <span className="text-xs text-slate-500 font-medium">Accounts</span>
                    </div>
                    <p className="text-2xl font-bold text-slate-900">4</p>
                    <p className="text-xs text-emerald-600 mt-1">All active</p>
                  </div>
                  <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm">
                    <div className="flex items-center gap-2 mb-2">
                      <Users size={16} className="text-violet-600" />
                      <span className="text-xs text-slate-500 font-medium">Contacts</span>
                    </div>
                    <p className="text-2xl font-bold text-slate-900">2,847</p>
                    <p className="text-xs text-slate-400 mt-1">Across 3 lists</p>
                  </div>
                  <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm">
                    <div className="flex items-center gap-2 mb-2">
                      <Send size={16} className="text-emerald-600" />
                      <span className="text-xs text-slate-500 font-medium">Sent Today</span>
                    </div>
                    <p className="text-2xl font-bold text-emerald-600">847</p>
                    <p className="text-xs text-slate-400 mt-1">+12% from yesterday</p>
                  </div>
                </div>
                
                {/* Chart and Campaign List */}
                <div className="grid lg:grid-cols-3 gap-4">
                  <div className="lg:col-span-2 bg-white rounded-xl p-5 border border-slate-200 shadow-sm">
                    <div className="flex items-center justify-between mb-4">
                      <span className="font-semibold text-slate-900">Sending Activity</span>
                      <span className="text-xs text-slate-400 bg-slate-100 px-2 py-1 rounded">Last 7 days</span>
                    </div>
                    <div className="flex items-end gap-3 h-32">
                      {[40, 65, 45, 80, 55, 90, 70].map((h, i) => (
                        <div key={i} className="flex-1 flex flex-col items-center gap-2">
                          <div
                            className="w-full bg-gradient-to-t from-blue-500 to-violet-500 rounded-t-lg"
                            style={{ height: `${h}%` }}
                          />
                          <span className="text-[10px] text-slate-400">
                            {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][i]}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-sm">
                    <span className="font-semibold text-slate-900">Active Campaigns</span>
                    <div className="mt-4 space-y-3">
                      <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg">
                        <div className="w-2 h-2 rounded-full bg-emerald-500" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-slate-900 truncate">Q4 Outreach</p>
                          <p className="text-xs text-slate-400">847/2000 sent</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg">
                        <div className="w-2 h-2 rounded-full bg-blue-500" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-slate-900 truncate">Holiday Promo</p>
                          <p className="text-xs text-slate-400">Scheduled for Dec 15</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg">
                        <div className="w-2 h-2 rounded-full bg-slate-300" />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium text-slate-900 truncate">Newsletter #12</p>
                          <p className="text-xs text-slate-400">Draft</p>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* 3️⃣ WHY THIS TOOL EXISTS */}
      <section className="py-28 px-6 bg-white">
        <div className="max-w-[1300px] mx-auto">
          <div className="grid lg:grid-cols-2 gap-20 items-start">
            <motion.div
              initial={{ opacity: 0, x: -20 }}
              whileInView={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.5 }}
              viewport={{ once: true }}
              className="lg:sticky lg:top-32"
            >
              <h2 className="font-heading font-extrabold text-4xl sm:text-5xl text-slate-900 leading-tight">
                Why This Tool
                <span className="block text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-violet-600 mt-2">
                  Exists
                </span>
              </h2>
              <p className="mt-6 text-slate-500 text-lg">
                Small businesses face unique challenges with email outreach. We built this to solve them.
              </p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 20 }}
              whileInView={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              viewport={{ once: true }}
              className="space-y-5"
            >
              {painPoints.map((point, index) => (
                <motion.div
                  key={index}
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4, delay: index * 0.1 }}
                  viewport={{ once: true }}
                  className="group flex items-start gap-5 p-6 bg-gradient-to-br from-slate-50 to-white rounded-[20px] border border-slate-100 shadow-sm hover:shadow-lg hover:border-slate-200 transition-all duration-300"
                >
                  <div className="w-3 h-3 rounded-full bg-gradient-to-br from-rose-500 to-orange-500 flex-shrink-0 mt-1.5 group-hover:scale-110 transition-transform" />
                  <span className="text-slate-700 text-base font-medium leading-relaxed">{point}</span>
                </motion.div>
              ))}
              
              <motion.div
                initial={{ opacity: 0 }}
                whileInView={{ opacity: 1 }}
                transition={{ duration: 0.5, delay: 0.6 }}
                viewport={{ once: true }}
                className="pt-8 border-t border-slate-100 mt-8"
              >
                <p className="text-xl font-bold text-slate-900 leading-relaxed">
                  This tool is built specifically for SMEs who just want results — without complexity.
                </p>
              </motion.div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* 3️⃣ HOW IT WORKS */}
      <section className="py-24 px-6 bg-gradient-to-br from-slate-50 to-slate-100">
        <div className="max-w-[1300px] mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="font-heading font-extrabold text-3xl sm:text-4xl text-slate-900">
              How It Works
            </h2>
          </motion.div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
            {howItWorks.map((item, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: index * 0.1 }}
                viewport={{ once: true }}
                className="bg-white rounded-[20px] p-6 shadow-sm hover:shadow-lg transition-all duration-300 group"
              >
                <div className="flex items-center gap-3 mb-4">
                  <span className="text-4xl font-extrabold text-slate-200 group-hover:text-blue-200 transition-colors">
                    {item.step}
                  </span>
                </div>
                <div className="w-12 h-12 bg-gradient-to-br from-blue-100 to-violet-100 rounded-2xl flex items-center justify-center mb-4">
                  <item.icon size={24} className="text-blue-600" />
                </div>
                <h3 className="font-heading font-semibold text-lg text-slate-900 mb-2">
                  {item.title}
                </h3>
                <p className="text-slate-500 text-sm leading-relaxed">
                  {item.description}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* 4️⃣ WHAT MAKES IT DIFFERENT */}
      <section className="py-24 px-6 bg-white">
        <div className="max-w-[1300px] mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="font-heading font-extrabold text-3xl sm:text-4xl text-slate-900">
              What Makes It Different?
            </h2>
          </motion.div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4 max-w-4xl mx-auto mb-12">
            {differentiators.map((item, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, scale: 0.95 }}
                whileInView={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.4, delay: index * 0.05 }}
                viewport={{ once: true }}
                className="flex items-center gap-3 p-4 bg-emerald-50 rounded-2xl"
              >
                <div className="w-6 h-6 bg-emerald-500 rounded-full flex items-center justify-center flex-shrink-0">
                  <Check size={14} className="text-white" />
                </div>
                <span className="text-slate-800 font-medium">{item}</span>
              </motion.div>
            ))}
          </div>

          <motion.p
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            viewport={{ once: true }}
            className="text-center text-xl max-w-2xl mx-auto"
          >
            <span className="font-semibold text-slate-900">Most tools are built for venture-backed startups.</span>
            <br />
            <span className="text-slate-600">This one is built for businesses that actually sell.</span>
          </motion.p>
        </div>
      </section>

      {/* 5️⃣ USE CASES */}
      <section className="py-24 px-6 bg-gradient-to-br from-slate-50 to-slate-100">
        <div className="max-w-[1300px] mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="font-heading font-extrabold text-3xl sm:text-4xl text-slate-900">
              Built for Real Use Cases
            </h2>
          </motion.div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {useCases.map((item, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: index * 0.05 }}
                viewport={{ once: true }}
                className="flex items-center gap-4 p-5 bg-white rounded-2xl shadow-sm hover:shadow-md transition-shadow"
              >
                <div className="w-12 h-12 bg-gradient-to-br from-blue-100 to-violet-100 rounded-xl flex items-center justify-center flex-shrink-0">
                  <item.icon size={22} className="text-blue-600" />
                </div>
                <span className="text-slate-700 font-medium">{item.text}</span>
              </motion.div>
            ))}
          </div>

          <motion.p
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.3 }}
            viewport={{ once: true }}
            className="text-center text-slate-600 mt-12 text-lg"
          >
            If outbound email is part of your growth strategy — this tool supports it properly.
          </motion.p>
        </div>
      </section>

      {/* 6️⃣ DELIVERABILITY SECTION */}
      <section className="py-32 px-6 bg-gradient-to-br from-blue-600 via-blue-700 to-violet-700">
        <div className="max-w-[1300px] mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <div className="inline-flex items-center gap-2 px-5 py-2.5 bg-white/20 backdrop-blur-sm rounded-full text-white text-sm font-semibold mb-8">
              <Lock size={18} />
              Deliverability First
            </div>
            <h2 className="font-heading font-black text-4xl sm:text-5xl lg:text-6xl text-white mb-6 leading-tight">
              Your Emails Actually Land
            </h2>
            <p className="text-blue-100 text-xl max-w-2xl mx-auto leading-relaxed">
              We prioritize inbox placement over volume. Every feature is designed to protect your sender reputation.
            </p>
          </motion.div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-5 max-w-5xl mx-auto mb-16">
            {deliverabilityFeatures.map((feature, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, scale: 0.95 }}
                whileInView={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.4, delay: index * 0.08 }}
                viewport={{ once: true }}
                className="flex items-center gap-3 p-5 bg-white/15 backdrop-blur-sm rounded-2xl text-white border border-white/20 hover:bg-white/25 transition-all duration-300"
              >
                <Shield size={20} className="text-blue-200 flex-shrink-0" />
                <span className="text-sm font-medium">{feature}</span>
              </motion.div>
            ))}
          </div>

          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.4 }}
            viewport={{ once: true }}
            className="text-center"
          >
            <p className="text-2xl sm:text-3xl text-white font-bold leading-relaxed max-w-3xl mx-auto">
              Because sending more emails is useless if they don't land in the inbox.
            </p>
          </motion.div>
        </div>
      </section>

      {/* 7️⃣ PRICING */}
      <section className="py-28 px-6 bg-white">
        <div className="max-w-[1300px] mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            viewport={{ once: true }}
            className="text-center mb-14"
          >
            <h2 className="font-heading font-extrabold text-3xl sm:text-4xl text-slate-900 mb-4">
              Simple, Transparent Pricing
            </h2>
            <p className="text-slate-600 text-lg max-w-2xl mx-auto">
              Choose the plan that fits your business. No hidden fees.
            </p>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-6 max-w-5xl mx-auto">
            {/* Free Plan */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0 }}
              viewport={{ once: true }}
              className="bg-slate-50 rounded-[24px] p-8 border border-slate-200"
            >
              <div className="inline-flex items-center gap-2 px-3 py-1 bg-emerald-100 text-emerald-700 rounded-full text-xs font-semibold mb-4">
                14-Day Trial
              </div>
              <h3 className="font-heading font-bold text-2xl text-slate-900 mb-2">Free</h3>
              <p className="text-slate-500 text-sm mb-6">Get started risk-free</p>
              
              <div className="space-y-4 mb-8">
                <div className="flex items-center gap-3">
                  <Check size={18} className="text-emerald-500 flex-shrink-0" />
                  <span className="text-slate-700">3 connected email accounts</span>
                </div>
                <div className="flex items-center gap-3">
                  <Check size={18} className="text-emerald-500 flex-shrink-0" />
                  <span className="text-slate-700">500 stored contacts</span>
                </div>
                <div className="flex items-center gap-3">
                  <Check size={18} className="text-emerald-500 flex-shrink-0" />
                  <span className="text-slate-700">Scheduler included</span>
                </div>
                <div className="flex items-center gap-3">
                  <Check size={18} className="text-emerald-500 flex-shrink-0" />
                  <span className="text-slate-700">Basic rotation</span>
                </div>
              </div>

              <Button
                onClick={handleStartFree}
                variant="outline"
                className="w-full rounded-full py-6"
                data-testid="pricing-free-btn"
              >
                Start Free Trial
              </Button>
            </motion.div>

            {/* Starter Plan - Most Popular */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1 }}
              viewport={{ once: true }}
              className="bg-gradient-to-br from-blue-600 to-violet-600 rounded-[24px] p-8 text-white relative shadow-xl shadow-blue-500/25 ring-4 ring-blue-500/20"
            >
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <span className="px-4 py-1.5 bg-amber-400 text-amber-900 rounded-full text-xs font-bold shadow-lg">
                  Most Popular
                </span>
              </div>
              <h3 className="font-heading font-bold text-2xl mb-2 mt-2">Starter</h3>
              <div className="flex items-baseline gap-2 mb-6">
                <span className="text-4xl font-extrabold">$99</span>
                <span className="text-blue-200">/year</span>
              </div>
              
              <div className="space-y-4 mb-8">
                <div className="flex items-center gap-3">
                  <Check size={18} className="text-blue-200 flex-shrink-0" />
                  <span className="text-white/90">10 connected email accounts</span>
                </div>
                <div className="flex items-center gap-3">
                  <Check size={18} className="text-blue-200 flex-shrink-0" />
                  <span className="text-white/90">7,000 stored contacts</span>
                </div>
                <div className="flex items-center gap-3">
                  <Check size={18} className="text-blue-200 flex-shrink-0" />
                  <span className="text-white/90">Full rotation engine</span>
                </div>
                <div className="flex items-center gap-3">
                  <Check size={18} className="text-blue-200 flex-shrink-0" />
                  <span className="text-white/90">Scheduler included</span>
                </div>
                <div className="flex items-center gap-3">
                  <Check size={18} className="text-blue-200 flex-shrink-0" />
                  <span className="text-white/90">Unlimited campaigns</span>
                </div>
              </div>

              <Button
                onClick={handleLogin}
                className="w-full bg-white text-blue-600 hover:bg-blue-50 rounded-full py-6 font-semibold"
                data-testid="pricing-starter-btn"
              >
                Get Started
              </Button>
            </motion.div>

            {/* Growth Plan */}
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
              viewport={{ once: true }}
              className="bg-slate-50 rounded-[24px] p-8 border border-slate-200"
            >
              <h3 className="font-heading font-bold text-2xl text-slate-900 mb-2">Growth</h3>
              <div className="flex items-baseline gap-2 mb-6">
                <span className="text-4xl font-extrabold text-slate-900">$149</span>
                <span className="text-slate-500">/year</span>
              </div>
              
              <div className="space-y-4 mb-8">
                <div className="flex items-center gap-3">
                  <Check size={18} className="text-emerald-500 flex-shrink-0" />
                  <span className="text-slate-700">15 connected email accounts</span>
                </div>
                <div className="flex items-center gap-3">
                  <Check size={18} className="text-emerald-500 flex-shrink-0" />
                  <span className="text-slate-700">10,000 stored contacts</span>
                </div>
                <div className="flex items-center gap-3">
                  <Check size={18} className="text-emerald-500 flex-shrink-0" />
                  <span className="text-slate-700">Full rotation engine</span>
                </div>
                <div className="flex items-center gap-3">
                  <Check size={18} className="text-emerald-500 flex-shrink-0" />
                  <span className="text-slate-700">Scheduler included</span>
                </div>
                <div className="flex items-center gap-3">
                  <Check size={18} className="text-emerald-500 flex-shrink-0" />
                  <span className="text-slate-700">Unlimited campaigns</span>
                </div>
              </div>

              <Button
                onClick={handleLogin}
                variant="outline"
                className="w-full rounded-full py-6"
                data-testid="pricing-growth-btn"
              >
                Get Started
              </Button>
            </motion.div>
          </div>
        </div>
      </section>

      {/* 8️⃣ BUILT FOR OWNERS */}
      <section className="py-24 px-6 bg-white">
        <div className="max-w-[1300px] mx-auto">
          <div className="max-w-2xl mx-auto text-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5 }}
              viewport={{ once: true }}
            >
              <h2 className="font-heading font-extrabold text-3xl sm:text-4xl text-slate-900 mb-8">
                Built for Owners, Not Just Marketers
              </h2>
              <div className="grid sm:grid-cols-2 gap-4 text-left mb-8">
                <div className="p-5 bg-slate-50 rounded-2xl">
                  <TrendingUp size={24} className="text-blue-600 mb-3" />
                  <p className="font-semibold text-slate-900">Reliable sending</p>
                </div>
                <div className="p-5 bg-slate-50 rounded-2xl">
                  <Shield size={24} className="text-blue-600 mb-3" />
                  <p className="font-semibold text-slate-900">Protected domains</p>
                </div>
                <div className="p-5 bg-slate-50 rounded-2xl">
                  <Inbox size={24} className="text-blue-600 mb-3" />
                  <p className="font-semibold text-slate-900">Better inbox rate</p>
                </div>
                <div className="p-5 bg-slate-50 rounded-2xl">
                  <MessageSquare size={24} className="text-blue-600 mb-3" />
                  <p className="font-semibold text-slate-900">Consistent lead flow</p>
                </div>
              </div>
              <p className="text-xl font-semibold text-slate-900">
                That's what this does.
              </p>
            </motion.div>
          </div>
        </div>
      </section>

      {/* 🔟 FINAL CTA */}
      <section className="py-24 px-6 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <div className="max-w-[1300px] mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            viewport={{ once: true }}
            className="text-center max-w-3xl mx-auto"
          >
            <h2 className="font-heading font-extrabold text-3xl sm:text-4xl lg:text-5xl text-white mb-6">
              Ready to Send Smarter?
            </h2>
            <div className="space-y-2 text-slate-400 text-lg mb-10">
              <p>Stop risking your main domain.</p>
              <p>Stop hitting sending limits.</p>
              <p>Stop losing leads to spam folders.</p>
            </div>
            <p className="text-white text-xl font-medium mb-10">
              Start sending professionally — across multiple accounts — today.
            </p>
            <div className="flex flex-wrap items-center justify-center gap-4">
              <Button
                onClick={handleLogin}
                size="lg"
                className="bg-gradient-to-r from-blue-500 to-violet-500 hover:from-blue-600 hover:to-violet-600 text-white px-10 py-6 text-lg rounded-full shadow-lg shadow-blue-500/30"
                data-testid="final-cta-btn"
              >
                Start Free Trial
                <ArrowRight size={20} className="ml-2" />
              </Button>
              <Button
                variant="outline"
                size="lg"
                className="px-10 py-6 text-lg rounded-full border-2 border-slate-600 text-white hover:bg-slate-800"
                data-testid="final-demo-btn"
              >
                Schedule Demo
              </Button>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-6 bg-slate-900 border-t border-slate-800">
        <div className="max-w-[1300px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2">
            <img 
              src="/routemail-logo.png" 
              alt="RoutEmail" 
              className="h-8 w-auto object-contain brightness-0 invert"
            />
          </div>
          <div className="flex flex-col sm:flex-row items-center gap-4 sm:gap-8">
            <a 
              href="mailto:support@routemail.co" 
              className="text-sm text-slate-400 hover:text-slate-300 transition-colors"
            >
              support@routemail.co
            </a>
            <p className="text-sm text-slate-500">
              &copy; {new Date().getFullYear()} RoutEmail. All rights reserved.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
