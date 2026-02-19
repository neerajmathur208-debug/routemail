import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import {
  CreditCard,
  Check,
  AlertCircle,
  Clock,
  Loader2,
} from "lucide-react";
import { Button } from "../components/ui/button";
import Sidebar from "../components/Sidebar";
import { api } from "../App";
import { toast } from "sonner";

const features = [
  "Unlimited email accounts",
  "Unlimited email lists",
  "50 emails/day per account",
  "Rotational sending logic",
  "CSV upload & validation",
  "Basic personalization tags",
  "Automatic unsubscribe links",
  "Campaign dashboard & stats",
];

export default function Subscription({ user, setUser }) {
  const [searchParams] = useSearchParams();
  const [loading, setLoading] = useState(false);
  const [checkingPayment, setCheckingPayment] = useState(false);

  // Check for session_id in URL (returning from Stripe)
  useEffect(() => {
    const sessionId = searchParams.get("session_id");
    if (sessionId) {
      pollPaymentStatus(sessionId);
    }
  }, [searchParams]);

  const pollPaymentStatus = async (sessionId, attempts = 0) => {
    const maxAttempts = 5;
    const pollInterval = 2000;

    if (attempts >= maxAttempts) {
      toast.error("Payment verification timed out. Please refresh the page.");
      setCheckingPayment(false);
      return;
    }

    setCheckingPayment(true);

    try {
      const response = await api.get(`/payments/status/${sessionId}`);
      const data = response.data;

      if (data.payment_status === "paid") {
        toast.success("Payment successful! Your subscription is now active.");
        // Refresh user data
        const userRes = await api.get("/auth/me");
        setUser(userRes.data);
        setCheckingPayment(false);
        // Clear URL params
        window.history.replaceState({}, "", "/subscription");
      } else if (data.status === "expired") {
        toast.error("Payment session expired. Please try again.");
        setCheckingPayment(false);
      } else {
        // Continue polling
        setTimeout(() => pollPaymentStatus(sessionId, attempts + 1), pollInterval);
      }
    } catch (error) {
      console.error("Error checking payment:", error);
      setTimeout(() => pollPaymentStatus(sessionId, attempts + 1), pollInterval);
    }
  };

  const handleSubscribe = async () => {
    setLoading(true);
    try {
      const response = await api.post("/payments/checkout", {
        origin_url: window.location.origin,
      });

      if (response.data.url) {
        window.location.href = response.data.url;
      }
    } catch (error) {
      const message = error.response?.data?.detail || "Failed to create checkout";
      toast.error(message);
      setLoading(false);
    }
  };

  const isActive = user?.subscription_status === "active";
  const expiresAt = user?.subscription_expires_at
    ? new Date(user.subscription_expires_at)
    : null;

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar user={user} setUser={setUser} />

      <main className="flex-1 p-6 lg:p-8 overflow-y-auto">
        <div className="max-w-2xl mx-auto">
          {/* Header */}
          <div className="mb-8">
            <h1 className="font-heading font-extrabold text-2xl sm:text-3xl text-slate-900">
              Subscription
            </h1>
            <p className="text-slate-500 mt-1">
              Manage your plan and billing
            </p>
          </div>

          {/* Payment Processing */}
          {checkingPayment && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mb-6 bg-blue-50 border border-blue-200 rounded-md p-4 flex items-center gap-4"
            >
              <Loader2 size={20} className="text-blue-600 animate-spin" />
              <div>
                <p className="text-blue-800 font-medium">Processing payment...</p>
                <p className="text-blue-700 text-sm">Please wait while we verify your payment</p>
              </div>
            </motion.div>
          )}

          {/* Current Plan Status */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-white border border-slate-200 rounded-md p-6 mb-8"
          >
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-heading font-semibold text-lg text-slate-900">
                Current Plan
              </h2>
              <span
                className={`px-3 py-1 rounded-full text-sm font-medium ${
                  isActive
                    ? "bg-green-100 text-green-700"
                    : "bg-slate-100 text-slate-600"
                }`}
              >
                {isActive ? "Active" : "Inactive"}
              </span>
            </div>

            {isActive ? (
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-green-100 rounded-full flex items-center justify-center">
                    <Check size={20} className="text-green-600" />
                  </div>
                  <div>
                    <p className="font-semibold text-slate-900">Pro Plan</p>
                    <p className="text-sm text-slate-500">$99/year</p>
                  </div>
                </div>
                {expiresAt && (
                  <div className="flex items-center gap-2 text-sm text-slate-600">
                    <Clock size={16} />
                    <span>
                      Renews on {expiresAt.toLocaleDateString("en-US", {
                        year: "numeric",
                        month: "long",
                        day: "numeric",
                      })}
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-slate-100 rounded-full flex items-center justify-center">
                  <AlertCircle size={20} className="text-slate-400" />
                </div>
                <div>
                  <p className="font-semibold text-slate-900">No Active Plan</p>
                  <p className="text-sm text-slate-500">
                    Subscribe to unlock all features
                  </p>
                </div>
              </div>
            )}
          </motion.div>

          {/* Pricing Card */}
          {!isActive && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="bg-white border-2 border-slate-900 rounded-md p-8"
            >
              <div className="flex items-baseline gap-2 mb-2">
                <span className="font-heading font-extrabold text-5xl text-slate-900">
                  $99
                </span>
                <span className="text-slate-500">/year</span>
              </div>
              <p className="text-slate-600 mb-6">
                Full access to all features
              </p>

              <ul className="space-y-3 mb-8">
                {features.map((feature) => (
                  <li key={feature} className="flex items-center gap-3">
                    <Check size={18} className="text-green-600 flex-shrink-0" />
                    <span className="text-slate-700">{feature}</span>
                  </li>
                ))}
              </ul>

              <Button
                onClick={handleSubscribe}
                disabled={loading}
                className="w-full bg-signal-orange hover:bg-orange-600 text-white"
                size="lg"
                data-testid="subscribe-btn"
              >
                {loading ? (
                  <>
                    <Loader2 size={18} className="mr-2 animate-spin" />
                    Processing...
                  </>
                ) : (
                  <>
                    <CreditCard size={18} className="mr-2" />
                    Subscribe Now
                  </>
                )}
              </Button>

              <p className="text-xs text-slate-500 text-center mt-4">
                Secure payment powered by Stripe
              </p>
            </motion.div>
          )}

          {/* FAQ */}
          <div className="mt-8 space-y-4">
            <h3 className="font-heading font-semibold text-lg text-slate-900">
              Frequently Asked Questions
            </h3>

            <div className="bg-white border border-slate-200 rounded-md p-4">
              <p className="font-medium text-slate-900 mb-1">
                What happens when my subscription expires?
              </p>
              <p className="text-sm text-slate-600">
                You'll lose access to sending campaigns. Your data (accounts, lists)
                will be preserved for 30 days.
              </p>
            </div>

            <div className="bg-white border border-slate-200 rounded-md p-4">
              <p className="font-medium text-slate-900 mb-1">
                Can I cancel anytime?
              </p>
              <p className="text-sm text-slate-600">
                Yes, you can cancel your subscription at any time. You'll retain
                access until the end of your billing period.
              </p>
            </div>

            <div className="bg-white border border-slate-200 rounded-md p-4">
              <p className="font-medium text-slate-900 mb-1">
                Why is there a 50 emails/day limit per account?
              </p>
              <p className="text-sm text-slate-600">
                This limit helps protect your sender reputation and ensures better
                deliverability. It's a best practice for cold email outreach.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
