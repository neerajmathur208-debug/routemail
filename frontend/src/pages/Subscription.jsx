import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Check, Zap, Crown, Shield, CreditCard, Loader2, Clock, AlertTriangle, Calendar, ArrowLeft } from "lucide-react";
import { Button } from "../components/ui/button";
import Sidebar from "../components/Sidebar";
import CustomPlanCard from "../components/CustomPlanCard";
import { api } from "../App";
import { toast } from "sonner";

export default function Subscription({ user, setUser }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState(null);
  const [subscriptionData, setSubscriptionData] = useState(null);
  const [currency, setCurrency] = useState("usd");
  const [countryDetected, setCountryDetected] = useState(false);
  const [customSlabs, setCustomSlabs] = useState([]);
  const [selectedCustomSlab, setSelectedCustomSlab] = useState("custom_15k");

  useEffect(() => {
    fetchSubscriptionStatus();
    fetchPrices();
    detectCountry();
  }, []);

  const fetchPrices = async () => {
    try {
      const res = await api.get("/subscription/prices");
      const slabs = res.data?.custom_plan?.slabs || [];
      setCustomSlabs(slabs);
    } catch (err) {
      console.error("Failed to load prices:", err);
    }
  };

  const detectCountry = async () => {
    try {
      const response = await fetch("https://ipapi.co/json/");
      const data = await response.json();
      if (data.country_code === "IN") {
        setCurrency("inr");
      }
      setCountryDetected(true);
    } catch (error) {
      console.log("Could not detect country, defaulting to USD");
      setCountryDetected(true);
    }
  };

  const fetchSubscriptionStatus = async () => {
    try {
      const response = await api.get("/subscription/status");
      setSubscriptionData(response.data);
    } catch (error) {
      console.error("Failed to fetch subscription:", error);
      toast.error("Failed to load subscription data");
    } finally {
      setLoading(false);
    }
  };

  const handleUpgrade = async (plan) => {
    setCheckoutLoading(plan);
    try {
      let priceId = null;
      if (plan.startsWith("custom_")) {
        const slab = customSlabs.find((s) => s.slug === plan);
        if (!slab || !slab.available || !slab.price_id) {
          toast.error("This Custom plan is not yet active. Please contact support@routemail.co.");
          return;
        }
        priceId = slab.price_id;
      } else {
        const priceKey = `${plan}_${currency}`;
        const priceIds = {
          starter_usd: "price_1T3JubD2HZgi5NSCVPybSMdk",
          growth_usd: "price_1T3Jv7D2HZgi5NSCTvsCbPBi",
          starter_inr: "price_1T3xeED2HZgi5NSCTsHhLaVL",
          growth_inr: "price_1T3xecD2HZgi5NSC84ntUhgG",
        };
        priceId = priceIds[priceKey];
      }
      if (!priceId) {
        toast.error("Plan unavailable. Please contact support@routemail.co.");
        return;
      }
      const response = await api.post("/subscription/create-checkout", {
        price_id: priceId,
        success_url: `${window.location.origin}/dashboard?subscription=success`,
        cancel_url: `${window.location.origin}/subscription?canceled=true`,
      });
      window.location.href = response.data.checkout_url;
    } catch (error) {
      console.error("Checkout error:", error);
      toast.error(error.response?.data?.detail || "Failed to start checkout");
    } finally {
      setCheckoutLoading(null);
    }
  };

  const handleManageSubscription = async () => {
    try {
      const response = await api.post("/subscription/create-portal");
      window.location.href = response.data.portal_url;
    } catch (error) {
      console.error("Portal error:", error);
      toast.error(error.response?.data?.detail || "Failed to open billing portal");
    }
  };

  // Updated pricing: INR ₹5,000 and ₹12,000
  const getPrice = (plan) => {
    if (currency === "inr") {
      return plan === "starter" ? "₹5,000" : "₹12,000";
    }
    return plan === "starter" ? "$99" : "$149";
  };

  if (loading || !countryDetected) {
    return (
      <div className="flex min-h-screen bg-slate-50">
        <Sidebar user={user} setUser={setUser} />
        <main className="flex-1 p-6 lg:p-8">
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
          </div>
        </main>
      </div>
    );
  }

  const currentPlan = subscriptionData?.plan_type || "free";
  const isActive = subscriptionData?.subscription_active;
  const statusDetails = subscriptionData?.status_details || {};

  // Helper retained for backward-compatible fields; the new Free Plan never expires.
  const getTrialDaysRemaining = () => null;

  const trialDays = getTrialDaysRemaining();

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar user={user} setUser={setUser} />
      <main className="flex-1 p-6 lg:p-8 overflow-y-auto">
        <div className="max-w-5xl mx-auto">
          {/* Back Button + Header */}
          <div className="mb-8">
            <button
              onClick={() => navigate("/dashboard")}
              className="flex items-center gap-2 text-slate-500 hover:text-slate-700 mb-4 transition-colors"
              data-testid="back-to-dashboard-btn"
            >
              <ArrowLeft size={18} />
              <span className="text-sm font-medium">Back to Dashboard</span>
            </button>
            <h1 className="text-3xl font-bold text-slate-900 mb-2">Subscription</h1>
            <p className="text-slate-600">Manage your plan and billing</p>
          </div>

          {/* Alert Banners */}
          {subscriptionData?.downgraded_to_free_at && subscriptionData?.downgrade_reason && currentPlan === "free" && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-6 flex items-center gap-3"
              data-testid="downgrade-notice"
            >
              <div className="w-10 h-10 bg-amber-100 rounded-full flex items-center justify-center flex-shrink-0">
                <AlertTriangle size={20} className="text-amber-600" />
              </div>
              <div>
                <p className="font-semibold text-amber-900">You are now on the Free Plan</p>
                <p className="text-sm text-amber-700">Your paid plan has expired. You can keep sending up to 500 unique contacts/month for free, or upgrade any time below.</p>
              </div>
            </motion.div>
          )}

          {subscriptionData?.subscription_status === "past_due" && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-6 flex items-center gap-3"
            >
              <div className="w-10 h-10 bg-amber-100 rounded-full flex items-center justify-center flex-shrink-0">
                <CreditCard size={20} className="text-amber-600" />
              </div>
              <div>
                <p className="font-semibold text-amber-900">Payment Past Due</p>
                <p className="text-sm text-amber-700">
                  Please update your payment method. 
                  {statusDetails.grace_ends && ` Grace period ends ${new Date(statusDetails.grace_ends).toLocaleDateString()}`}
                </p>
              </div>
              <Button size="sm" onClick={handleManageSubscription} className="ml-auto bg-amber-600 hover:bg-amber-700">
                Update Payment
              </Button>
            </motion.div>
          )}

          {subscriptionData?.subscription_status === "canceled_pending" && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-slate-100 border border-slate-300 rounded-xl p-4 mb-6 flex items-center gap-3"
            >
              <div className="w-10 h-10 bg-slate-200 rounded-full flex items-center justify-center flex-shrink-0">
                <Clock size={20} className="text-slate-600" />
              </div>
              <div>
                <p className="font-semibold text-slate-900">Downgrade Scheduled</p>
                <p className="text-sm text-slate-600">
                  Your plan will change to Free on {subscriptionData?.billing_cycle_end 
                    ? new Date(subscriptionData.billing_cycle_end).toLocaleDateString() 
                    : "the next billing date"
                  }
                </p>
              </div>
            </motion.div>
          )}

          {/* Current Plan Status */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white rounded-xl border border-slate-200 p-6 mb-8"
          >
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div>
                <p className="text-sm text-slate-500 mb-1">Current Plan</p>
                <div className="flex items-center gap-3 flex-wrap">
                  <h2 className="text-2xl font-bold text-slate-900 capitalize flex items-center gap-2">
                    {currentPlan === "growth" && <Crown className="text-amber-500" size={24} />}
                    {currentPlan === "starter" && <Zap className="text-blue-500" size={24} />}
                    {currentPlan === "free" && <Shield className="text-slate-400" size={24} />}
                    {currentPlan} Plan
                  </h2>
                  {/* Status Badge */}
                  <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                    subscriptionData?.subscription_status === "active"
                      ? "bg-green-100 text-green-700"
                      : subscriptionData?.subscription_status === "past_due"
                      ? "bg-amber-100 text-amber-700"
                      : subscriptionData?.subscription_status === "canceled_pending"
                      ? "bg-slate-100 text-slate-700"
                      : "bg-red-100 text-red-700"
                  }`}>
                    {currentPlan === "free" ? "Free forever" : subscriptionData?.subscription_status?.replace("_", " ")}
                  </span>
                </div>
                
                {/* Billing Info */}
                <div className="mt-3 space-y-1 text-sm text-slate-500">
                  {currentPlan === "free" && (
                    <p className="flex items-center gap-2">
                      <Shield size={14} />
                      No expiry — your Free Plan is active forever.
                    </p>
                  )}
                  {subscriptionData?.billing_cycle_end && currentPlan !== "free" && (
                    <p className="flex items-center gap-2">
                      <Calendar size={14} />
                      Next billing: <span className="font-medium text-slate-700">{new Date(subscriptionData.billing_cycle_end).toLocaleDateString()}</span>
                    </p>
                  )}
                  {statusDetails.grace_ends && (
                    <p className="flex items-center gap-2 text-amber-600">
                      <AlertTriangle size={14} />
                      Grace period ends: <span className="font-medium">{new Date(statusDetails.grace_ends).toLocaleDateString()}</span>
                    </p>
                  )}
                </div>
              </div>
              {currentPlan !== "free" && (
                <Button
                  onClick={handleManageSubscription}
                  variant="outline"
                  className="gap-2"
                  data-testid="manage-billing-btn"
                >
                  <CreditCard size={16} />
                  Manage Billing
                </Button>
              )}
            </div>

            {/* Usage Stats */}
            {subscriptionData?.usage && (
              <div className="grid grid-cols-3 gap-4 mt-6 pt-6 border-t border-slate-100">
                <div>
                  <p className="text-sm text-slate-500">Email Accounts</p>
                  <p className="text-lg font-semibold text-slate-900">
                    {subscriptionData.usage.accounts.current} / {subscriptionData.usage.accounts.limit}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-slate-500">Stored Contacts</p>
                  <p className="text-lg font-semibold text-slate-900">
                    {subscriptionData.usage.contacts.current.toLocaleString()} / {subscriptionData.usage.contacts.limit.toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-slate-500">Monthly Recipients</p>
                  <p className="text-lg font-semibold text-slate-900">
                    {subscriptionData.usage.recipients.current.toLocaleString()} / {subscriptionData.usage.recipients.limit.toLocaleString()}
                  </p>
                </div>
              </div>
            )}
          </motion.div>

          {/* Monthly Contacts Usage Tracker (prominent) */}
          {subscriptionData?.usage?.recipients && (
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-gradient-to-br from-emerald-50 to-blue-50 rounded-xl border border-emerald-200 p-6 mb-6"
              data-testid="monthly-contacts-tracker"
            >
              <div className="flex items-center justify-between mb-3">
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wide">Contacts Used This Month</p>
                  <p className="text-2xl font-bold text-slate-900">
                    {subscriptionData.usage.recipients.current.toLocaleString()}{" "}
                    <span className="text-base font-medium text-slate-500">
                      / {subscriptionData.usage.recipients.limit.toLocaleString()}
                    </span>
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xs text-slate-500">Remaining</p>
                  <p className="text-lg font-semibold text-emerald-700">
                    {Math.max(
                      subscriptionData.usage.recipients.limit -
                        subscriptionData.usage.recipients.current,
                      0
                    ).toLocaleString()}
                  </p>
                </div>
              </div>
              {(() => {
                const cur = subscriptionData.usage.recipients.current || 0;
                const lim = subscriptionData.usage.recipients.limit || 1;
                const pct = Math.min(Math.round((cur / lim) * 100), 100);
                const tone =
                  pct >= 95
                    ? "bg-red-500"
                    : pct >= 80
                    ? "bg-amber-500"
                    : "bg-emerald-500";
                return (
                  <>
                    <div className="h-3 w-full bg-white rounded-full overflow-hidden border border-slate-200">
                      <div
                        className={`h-full ${tone} transition-all duration-500`}
                        style={{ width: `${pct}%` }}
                        data-testid="monthly-contacts-progress"
                      />
                    </div>
                    <p className="text-xs text-slate-500 mt-2">
                      {pct}% of monthly contact allowance used.{" "}
                      <span className="text-slate-600">
                        Sending to existing recipients you've already contacted this month
                        does NOT count again.
                      </span>
                    </p>
                  </>
                );
              })()}
            </motion.div>
          )}

          {/* Plans */}
          <div className="grid md:grid-cols-3 gap-6">
            {/* Free Plan */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className={`bg-white rounded-xl border-2 p-6 ${
                currentPlan === "free" ? "border-slate-900" : "border-slate-200"
              }`}
            >
              {currentPlan === "free" && (
                <div className="inline-flex items-center gap-1 px-2 py-1 bg-slate-100 text-slate-700 rounded text-xs font-medium mb-3">
                  Current Plan
                </div>
              )}
              <h3 className="text-xl font-bold text-slate-900 mb-1">Free</h3>
              <p className="text-slate-500 text-sm mb-4">Free forever — no expiry</p>
              <div className="text-3xl font-bold text-slate-900 mb-6">
                $0<span className="text-base text-slate-500 font-medium">/year</span>
              </div>
              
              <ul className="space-y-3 mb-6">
                <li className="flex items-center gap-2 text-sm text-slate-600">
                  <Check size={16} className="text-green-500" />
                  3 email accounts
                </li>
                <li className="flex items-center gap-2 text-sm text-slate-600">
                  <Check size={16} className="text-green-500" />
                  500 contacts/month
                </li>
                <li className="flex items-center gap-2 text-sm text-slate-600">
                  <Check size={16} className="text-green-500" />
                  Basic rotation
                </li>
              </ul>

              {currentPlan === "free" ? (
                <Button
                  variant="outline"
                  className="w-full"
                  disabled
                  data-testid="free-plan-current-btn"
                >
                  Current Plan
                </Button>
              ) : (
                <div className="text-xs text-slate-500 px-2 py-2 text-center" data-testid="cancel-support-note">
                  To downgrade to Free, please email{" "}
                  <a href="mailto:support@routemail.co" className="text-blue-600 underline">
                    support@routemail.co
                  </a>
                </div>
              )}
            </motion.div>

            {/* Starter Plan */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className={`bg-gradient-to-br from-blue-600 to-violet-600 rounded-xl p-6 text-white relative ${
                currentPlan === "starter" ? "ring-4 ring-blue-500/30" : ""
              }`}
            >
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <span className="px-3 py-1 bg-amber-400 text-amber-900 rounded-full text-xs font-bold">
                  Most Popular
                </span>
              </div>
              {currentPlan === "starter" && (
                <div className="inline-flex items-center gap-1 px-2 py-1 bg-white/20 text-white rounded text-xs font-medium mb-3 mt-2">
                  Current Plan
                </div>
              )}
              <h3 className="text-xl font-bold mb-1 mt-2">Starter</h3>
              <p className="text-blue-200 text-sm mb-4">For growing businesses</p>
              <div className="flex items-baseline gap-1 mb-6">
                <span className="text-3xl font-bold">{getPrice("starter")}</span>
                <span className="text-xl font-medium text-blue-200">/year</span>
              </div>
              
              <ul className="space-y-3 mb-6">
                <li className="flex items-center gap-2 text-sm text-white/90">
                  <Check size={16} className="text-blue-200" />
                  10 email accounts
                </li>
                <li className="flex items-center gap-2 text-sm text-white/90">
                  <Check size={16} className="text-blue-200" />
                  4,000 contacts/month
                </li>
                <li className="flex items-center gap-2 text-sm text-white/90">
                  <Check size={16} className="text-blue-200" />
                  48,000 contacts per year
                </li>
                <li className="flex items-center gap-2 text-sm text-white/90">
                  <Check size={16} className="text-blue-200" />
                  Unlimited emails
                </li>
                <li className="flex items-center gap-2 text-sm text-white/90">
                  <Check size={16} className="text-blue-200" />
                  Full rotation engine
                </li>
                <li className="flex items-center gap-2 text-sm text-white/90">
                  <Check size={16} className="text-blue-200" />
                  Unlimited campaigns
                </li>
              </ul>

              {currentPlan === "starter" ? (
                <div className="space-y-2">
                  <Button
                    className="w-full bg-white/20 text-white cursor-default"
                    disabled
                    data-testid="current-starter-btn"
                  >
                    Current Plan
                  </Button>
                  <div className="text-xs text-white/85 text-center px-1" data-testid="cancel-support-note-starter">
                    To cancel, email{" "}
                    <a href="mailto:support@routemail.co" className="underline">
                      support@routemail.co
                    </a>
                  </div>
                </div>
              ) : currentPlan === "growth" || (typeof currentPlan === "string" && currentPlan.startsWith("custom_")) ? (
                <div className="text-xs text-white/85 text-center px-2 py-2" data-testid="cancel-support-note-starter-from-other">
                  To downgrade, email{" "}
                  <a href="mailto:support@routemail.co" className="underline">
                    support@routemail.co
                  </a>
                </div>
              ) : (
                <Button
                  onClick={() => handleUpgrade("starter")}
                  disabled={checkoutLoading === "starter"}
                  className="w-full bg-white text-blue-600 hover:bg-blue-50"
                  data-testid="upgrade-starter-btn"
                >
                  {checkoutLoading === "starter" ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    "Upgrade to Starter"
                  )}
                </Button>
              )}
            </motion.div>

            {/* Growth Plan */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className={`bg-white rounded-xl border-2 p-6 ${
                currentPlan === "growth" ? "border-amber-500" : "border-slate-200"
              }`}
            >
              {currentPlan === "growth" && (
                <div className="inline-flex items-center gap-1 px-2 py-1 bg-amber-100 text-amber-700 rounded text-xs font-medium mb-3">
                  <Crown size={12} /> Current Plan
                </div>
              )}
              <h3 className="text-xl font-bold text-slate-900 mb-1">Growth</h3>
              <p className="text-slate-500 text-sm mb-4">For scaling teams</p>
              <div className="flex items-baseline gap-1 mb-6">
                <span className="text-3xl font-bold text-slate-900">{getPrice("growth")}</span>
                <span className="text-xl font-medium text-slate-500">/year</span>
              </div>
              
              <ul className="space-y-3 mb-6">
                <li className="flex items-center gap-2 text-sm text-slate-600">
                  <Check size={16} className="text-green-500" />
                  15 email accounts
                </li>
                <li className="flex items-center gap-2 text-sm text-slate-600">
                  <Check size={16} className="text-green-500" />
                  10,000 contacts/month
                </li>
                <li className="flex items-center gap-2 text-sm text-slate-600">
                  <Check size={16} className="text-green-500" />
                  120,000 contacts per year
                </li>
                <li className="flex items-center gap-2 text-sm text-slate-600">
                  <Check size={16} className="text-green-500" />
                  Unlimited emails
                </li>
                <li className="flex items-center gap-2 text-sm text-slate-600">
                  <Check size={16} className="text-green-500" />
                  Full rotation engine
                </li>
                <li className="flex items-center gap-2 text-sm text-slate-600">
                  <Check size={16} className="text-green-500" />
                  Unlimited campaigns
                </li>
              </ul>

              {currentPlan === "growth" ? (
                <div className="space-y-2">
                  <Button
                    variant="outline"
                    className="w-full border-amber-500 text-amber-700 cursor-default"
                    disabled
                    data-testid="current-growth-btn"
                  >
                    <Crown size={16} className="mr-2" />
                    Current Plan
                  </Button>
                  <div className="text-xs text-slate-500 text-center px-1" data-testid="cancel-support-note-growth">
                    To cancel or downgrade, please email{" "}
                    <a href="mailto:support@routemail.co" className="text-blue-600 underline">
                      support@routemail.co
                    </a>
                  </div>
                </div>
              ) : (
                <Button
                  onClick={() => handleUpgrade("growth")}
                  disabled={checkoutLoading === "growth"}
                  className="w-full bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600 text-white"
                  data-testid="upgrade-growth-btn"
                >
                  {checkoutLoading === "growth" ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <Crown size={16} className="mr-2" />
                      Upgrade to Growth
                    </>
                  )}
                </Button>
              )}
            </motion.div>
          </div>

          {/* Custom Plan (shared component, reused on landing page too) */}
          <div className="mt-6">
            <CustomPlanCard
              variant="dashboard"
              currentPlanSlug={currentPlan}
            />
          </div>

          {/* Cancellation note */}
          <div className="mt-6 text-center text-sm text-slate-600" data-testid="global-cancel-note">
            Need to cancel or change your plan? Drop us a line at{" "}
            <a href="mailto:support@routemail.co" className="text-blue-600 underline">
              support@routemail.co
            </a>{" "}
            and our team will take care of it.
          </div>
        </div>
      </main>
    </div>
  );
}
