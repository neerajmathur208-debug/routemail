import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Check, Zap, Crown, Shield, CreditCard, Loader2 } from "lucide-react";
import { Button } from "../components/ui/button";
import Sidebar from "../components/Sidebar";
import { api } from "../App";
import { toast } from "sonner";

export default function Subscription({ user, setUser }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState(null);
  const [subscriptionData, setSubscriptionData] = useState(null);
  const [currency, setCurrency] = useState("usd");

  useEffect(() => {
    fetchSubscriptionStatus();
    detectCountry();
  }, []);

  const detectCountry = async () => {
    try {
      // Use a free geolocation API
      const response = await fetch("https://ipapi.co/json/");
      const data = await response.json();
      if (data.country_code === "IN") {
        setCurrency("inr");
      }
    } catch (error) {
      console.log("Could not detect country, defaulting to USD");
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
      const priceKey = `${plan}_${currency}`;
      const priceIds = {
        starter_usd: "price_1T3JubD2HZgi5NSCVPybSMdk",
        growth_usd: "price_1T3Jv7D2HZgi5NSCTvsCbPBi",
        starter_inr: "price_1T3xeED2HZgi5NSCTsHhLaVL",
        growth_inr: "price_1T3xecD2HZgi5NSC84ntUhgG",
      };

      const response = await api.post("/subscription/create-checkout", {
        price_id: priceIds[priceKey],
        success_url: `${window.location.origin}/dashboard?subscription=success`,
        cancel_url: `${window.location.origin}/subscription?canceled=true`,
      });

      // Redirect to Stripe Checkout
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

  const formatPrice = (usd, inr) => {
    if (currency === "inr") {
      return `₹${inr.toLocaleString()}`;
    }
    return `$${usd}`;
  };

  if (loading) {
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

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar user={user} setUser={setUser} />
      <main className="flex-1 p-6 lg:p-8 overflow-y-auto">
        <div className="max-w-5xl mx-auto">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-slate-900 mb-2">Subscription</h1>
            <p className="text-slate-600">Manage your plan and billing</p>
          </div>

          {/* Current Plan Status */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white rounded-xl border border-slate-200 p-6 mb-8"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-500 mb-1">Current Plan</p>
                <h2 className="text-2xl font-bold text-slate-900 capitalize flex items-center gap-2">
                  {currentPlan === "growth" && <Crown className="text-amber-500" size={24} />}
                  {currentPlan === "starter" && <Zap className="text-blue-500" size={24} />}
                  {currentPlan === "free" && <Shield className="text-slate-400" size={24} />}
                  {currentPlan} Plan
                </h2>
                <p className="text-sm text-slate-500 mt-1">
                  Status: <span className={`font-medium ${isActive ? "text-green-600" : "text-red-600"}`}>
                    {subscriptionData?.subscription_status}
                  </span>
                </p>
                {subscriptionData?.trial_ends_at && currentPlan === "free" && (
                  <p className="text-sm text-amber-600 mt-1">
                    Trial ends: {new Date(subscriptionData.trial_ends_at).toLocaleDateString()}
                  </p>
                )}
                {subscriptionData?.billing_cycle_end && currentPlan !== "free" && (
                  <p className="text-sm text-slate-500 mt-1">
                    Renews: {new Date(subscriptionData.billing_cycle_end).toLocaleDateString()}
                  </p>
                )}
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

          {/* Currency Toggle */}
          <div className="flex justify-center mb-6">
            <div className="inline-flex items-center bg-slate-100 rounded-full p-1">
              <button
                onClick={() => setCurrency("usd")}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                  currency === "usd" ? "bg-white text-slate-900 shadow-sm" : "text-slate-600"
                }`}
              >
                USD ($)
              </button>
              <button
                onClick={() => setCurrency("inr")}
                className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                  currency === "inr" ? "bg-white text-slate-900 shadow-sm" : "text-slate-600"
                }`}
              >
                INR (₹)
              </button>
            </div>
          </div>

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
              <h3 className="text-xl font-bold text-slate-900 mb-1">Free Trial</h3>
              <p className="text-slate-500 text-sm mb-4">14 days to explore</p>
              <div className="text-3xl font-bold text-slate-900 mb-6">Free</div>
              
              <ul className="space-y-3 mb-6">
                <li className="flex items-center gap-2 text-sm text-slate-600">
                  <Check size={16} className="text-green-500" />
                  3 email accounts
                </li>
                <li className="flex items-center gap-2 text-sm text-slate-600">
                  <Check size={16} className="text-green-500" />
                  500 contacts
                </li>
                <li className="flex items-center gap-2 text-sm text-slate-600">
                  <Check size={16} className="text-green-500" />
                  500 recipients/month
                </li>
                <li className="flex items-center gap-2 text-sm text-slate-600">
                  <Check size={16} className="text-green-500" />
                  Basic rotation
                </li>
              </ul>

              <Button
                variant="outline"
                className="w-full"
                disabled={currentPlan === "free"}
              >
                {currentPlan === "free" ? "Current Plan" : "Free Trial"}
              </Button>
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
              <div className="text-3xl font-bold mb-1">{formatPrice(99, 7999)}</div>
              <p className="text-blue-200 text-sm mb-6">/year</p>
              
              <ul className="space-y-3 mb-6">
                <li className="flex items-center gap-2 text-sm text-white/90">
                  <Check size={16} className="text-blue-200" />
                  10 email accounts
                </li>
                <li className="flex items-center gap-2 text-sm text-white/90">
                  <Check size={16} className="text-blue-200" />
                  4,000 contacts
                </li>
                <li className="flex items-center gap-2 text-sm text-white/90">
                  <Check size={16} className="text-blue-200" />
                  4,000 recipients/month
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

              <Button
                onClick={() => handleUpgrade("starter")}
                disabled={currentPlan === "starter" || currentPlan === "growth" || checkoutLoading === "starter"}
                className="w-full bg-white text-blue-600 hover:bg-blue-50"
                data-testid="upgrade-starter-btn"
              >
                {checkoutLoading === "starter" ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : currentPlan === "starter" ? (
                  "Current Plan"
                ) : currentPlan === "growth" ? (
                  "Downgrade"
                ) : (
                  "Upgrade to Starter"
                )}
              </Button>
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
              <div className="text-3xl font-bold text-slate-900 mb-1">{formatPrice(149, 11999)}</div>
              <p className="text-slate-500 text-sm mb-6">/year</p>
              
              <ul className="space-y-3 mb-6">
                <li className="flex items-center gap-2 text-sm text-slate-600">
                  <Check size={16} className="text-green-500" />
                  15 email accounts
                </li>
                <li className="flex items-center gap-2 text-sm text-slate-600">
                  <Check size={16} className="text-green-500" />
                  10,000 contacts
                </li>
                <li className="flex items-center gap-2 text-sm text-slate-600">
                  <Check size={16} className="text-green-500" />
                  10,000 recipients/month
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

              <Button
                onClick={() => handleUpgrade("growth")}
                disabled={currentPlan === "growth" || checkoutLoading === "growth"}
                variant="outline"
                className="w-full"
                data-testid="upgrade-growth-btn"
              >
                {checkoutLoading === "growth" ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : currentPlan === "growth" ? (
                  "Current Plan"
                ) : (
                  "Upgrade to Growth"
                )}
              </Button>
            </motion.div>
          </div>
        </div>
      </main>
    </div>
  );
}
