import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Crown, Loader2, Sparkles, Check } from "lucide-react";
import { Button } from "./ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./ui/select";
import { api } from "../App";
import { toast } from "sonner";

/**
 * Shared "Custom Plan" pricing card.
 *
 * Used on:
 *   - Public LandingPage (variant="public")  — clicking the CTA routes to /register
 *   - Authenticated Subscription page (variant="dashboard") — clicking the CTA
 *     fires the existing /api/subscription/create-checkout flow.
 *
 * Pricing slabs and Stripe price IDs are sourced from /api/subscription/prices,
 * which the backend already exposes (env-backed). Falls back to a static slab list
 * if the prices endpoint hasn't loaded yet.
 */

const FALLBACK_SLABS = [
  { slug: "custom_15k",  contacts_per_month: 15000,  price_usd: 199 },
  { slug: "custom_20k",  contacts_per_month: 20000,  price_usd: 249 },
  { slug: "custom_30k",  contacts_per_month: 30000,  price_usd: 349 },
  { slug: "custom_50k",  contacts_per_month: 50000,  price_usd: 499 },
  { slug: "custom_75k",  contacts_per_month: 75000,  price_usd: 699 },
  { slug: "custom_100k", contacts_per_month: 100000, price_usd: 899 },
];

export function CustomPlanCard({
  variant = "public",
  navigate,
  currentPlanSlug = null,
  className = "",
}) {
  const [slabs, setSlabs] = useState(FALLBACK_SLABS);
  const [selectedSlug, setSelectedSlug] = useState("custom_15k");
  const [checkoutLoading, setCheckoutLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get("/subscription/prices");
        const apiSlabs = res.data?.custom_plan?.slabs;
        if (!cancelled && Array.isArray(apiSlabs) && apiSlabs.length > 0) {
          setSlabs(apiSlabs);
        }
      } catch (err) {
        // Fallback already in place.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedSlab =
    slabs.find((s) => s.slug === selectedSlug) || slabs[0] || FALLBACK_SLABS[0];
  const isCurrent = currentPlanSlug === selectedSlab.slug;

  const handleCta = async () => {
    if (variant === "public") {
      // Send the user to register; we pass the chosen slab via querystring so
      // we can pre-select it after sign-up if desired (optional).
      if (navigate) navigate(`/register?plan=${selectedSlab.slug}`);
      return;
    }
    // Dashboard variant — start Stripe checkout.
    if (!selectedSlab?.price_id || selectedSlab?.available === false) {
      toast.error(
        "This Custom plan tier is not active yet. Please email support@routemail.co."
      );
      return;
    }
    setCheckoutLoading(true);
    try {
      const response = await api.post("/subscription/create-checkout", {
        price_id: selectedSlab.price_id,
        success_url: `${window.location.origin}/dashboard?subscription=success`,
        cancel_url: `${window.location.origin}/subscription?canceled=true`,
      });
      window.location.href = response.data.checkout_url;
    } catch (error) {
      toast.error(
        error.response?.data?.detail || "Failed to start checkout"
      );
    } finally {
      setCheckoutLoading(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-50px" }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className={`relative rounded-2xl border-2 border-violet-200 bg-gradient-to-br from-violet-50 via-white to-blue-50 p-6 md:p-8 shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all duration-300 ${className}`}
      data-testid="custom-plan-card"
    >
      <div className="absolute -top-3 left-6">
        <span className="inline-flex items-center gap-1 px-3 py-1 bg-gradient-to-r from-violet-600 to-fuchsia-600 text-white rounded-full text-xs font-bold tracking-wide">
          <Sparkles size={12} />
          CUSTOM
        </span>
      </div>

      <div className="flex items-start justify-between mb-2">
        <div>
          <h3 className="text-2xl font-bold text-slate-900">Custom Plan</h3>
          <p className="text-sm text-slate-500 mt-1">
            Scale beyond Growth — pick the monthly capacity that fits.
          </p>
        </div>
        <Crown size={28} className="text-violet-600" />
      </div>

      <div className="mt-5 mb-3">
        <label
          htmlFor="custom-slab-select"
          className="block text-xs font-bold tracking-[0.2em] uppercase text-violet-700 mb-2"
        >
          Select Monthly Contacts
        </label>
        <Select value={selectedSlug} onValueChange={setSelectedSlug}>
          <SelectTrigger
            id="custom-slab-select"
            className="w-full bg-white border-slate-200 h-11"
            data-testid="pricing-custom-select"
          >
            <SelectValue placeholder="Pick contacts/month" />
          </SelectTrigger>
          <SelectContent>
            {slabs.map((s) => (
              <SelectItem
                key={s.slug}
                value={s.slug}
                data-testid={`pricing-custom-option-${s.slug}`}
              >
                {Number(s.contacts_per_month).toLocaleString()} contacts/month
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="mt-4 flex items-baseline gap-2">
        <motion.span
          key={selectedSlab.slug}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-4xl md:text-5xl font-bold text-slate-900"
          data-testid="custom-plan-price"
        >
          ${selectedSlab.price_usd}
        </motion.span>
        <span className="text-base text-slate-500">/year</span>
      </div>
      <p className="text-xs text-slate-500 mt-1">
        Billed yearly · Cancel anytime via support
      </p>

      <ul className="mt-5 space-y-2.5">
        <li className="flex items-start gap-2 text-sm text-slate-700">
          <Check size={16} className="text-emerald-500 mt-0.5 shrink-0" />
          <span>
            <strong>
              {Number(selectedSlab.contacts_per_month).toLocaleString()}
            </strong>{" "}
            unique contacts per month
          </span>
        </li>
        <li className="flex items-start gap-2 text-sm text-slate-700">
          <Check size={16} className="text-emerald-500 mt-0.5 shrink-0" />
          Unlimited follow-ups to existing contacts
        </li>
        <li className="flex items-start gap-2 text-sm text-slate-700">
          <Check size={16} className="text-emerald-500 mt-0.5 shrink-0" />
          Unlimited lists, campaigns &amp; drip sequences
        </li>
        <li className="flex items-start gap-2 text-sm text-slate-700">
          <Check size={16} className="text-emerald-500 mt-0.5 shrink-0" />
          Smart rotation, warmup &amp; deliverability suite
        </li>
      </ul>

      <Button
        onClick={handleCta}
        disabled={checkoutLoading || isCurrent}
        className="mt-6 w-full bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:from-violet-700 hover:to-fuchsia-700 text-white h-11"
        data-testid="custom-plan-cta-btn"
      >
        {checkoutLoading ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : isCurrent ? (
          "Current Plan"
        ) : variant === "public" ? (
          <>Start with Custom Plan</>
        ) : (
          <>Upgrade to Custom — ${selectedSlab.price_usd}/yr</>
        )}
      </Button>

      {variant === "dashboard" && isCurrent && (
        <p className="mt-2 text-xs text-center text-slate-500">
          To change capacity or cancel, email{" "}
          <a
            href="mailto:support@routemail.co"
            className="text-blue-600 underline"
          >
            support@routemail.co
          </a>
        </p>
      )}
    </motion.div>
  );
}

export default CustomPlanCard;
