import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  Mail,
  Upload,
  RefreshCw,
  Shield,
  Zap,
  Check,
  ArrowRight,
} from "lucide-react";
import { Button } from "../components/ui/button";

const features = [
  {
    icon: Mail,
    title: "Multiple Email Accounts",
    description: "Connect and manage multiple Gmail accounts from one dashboard.",
  },
  {
    icon: RefreshCw,
    title: "Smart Rotation",
    description: "Automatically rotate sends across accounts to maximize deliverability.",
  },
  {
    icon: Shield,
    title: "Daily Limits",
    description: "Built-in 50 emails/day limit per account to protect your sender reputation.",
  },
  {
    icon: Upload,
    title: "Easy CSV Upload",
    description: "Upload your email list with automatic validation and duplicate removal.",
  },
  {
    icon: Zap,
    title: "Personalization",
    description: "Use {first_name} and {company} tags to personalize every email.",
  },
];

const pricingFeatures = [
  "Unlimited email accounts",
  "Unlimited email lists",
  "50 emails/day per account",
  "Rotational sending",
  "CSV upload & validation",
  "Basic personalization",
  "Unsubscribe management",
  "Campaign dashboard",
];

export default function LandingPage() {
  const navigate = useNavigate();

  const handleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen bg-white">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-white/80 backdrop-blur-sm border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <span className="font-heading font-extrabold text-xl text-slate-900">ROTATION</span>
          <Button
            onClick={handleLogin}
            variant="outline"
            className="border-slate-300"
            data-testid="nav-login-btn"
          >
            Sign In
          </Button>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="max-w-3xl"
          >
            <h1 className="font-heading font-extrabold text-4xl sm:text-5xl lg:text-6xl text-slate-900 leading-tight">
              Send Emails from
              <br />
              <span className="text-electric-blue">Multiple Accounts</span>
            </h1>
            <p className="mt-6 text-lg text-slate-600 leading-relaxed max-w-2xl">
              A simple rotational email tool for small businesses. Connect multiple
              Gmail accounts, upload your list, and let us handle the rest.
            </p>
            <div className="mt-8 flex flex-wrap gap-4">
              <Button
                onClick={handleLogin}
                size="lg"
                className="bg-signal-orange hover:bg-orange-600 text-white px-8"
                data-testid="hero-get-started-btn"
              >
                Get Started Free
                <ArrowRight size={18} className="ml-2" />
              </Button>
            </div>
          </motion.div>

          {/* Hero Image */}
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="mt-16"
          >
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-8">
              <img
                src="https://images.unsplash.com/photo-1640551497504-ec05b9e50b50?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NjAzMjd8MHwxfHNlYXJjaHwzfHxtaW5pbWFsaXN0JTIwd29ya3NwYWNlJTIwbGFwdG9wfGVufDB8fHx8MTc3MTUyODY1Mnww&ixlib=rb-4.1.0&q=85&w=1200"
                alt="Clean workspace"
                className="w-full h-auto rounded-md"
              />
            </div>
          </motion.div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 px-6 bg-slate-50">
        <div className="max-w-7xl mx-auto">
          <h2 className="font-heading font-semibold text-2xl sm:text-3xl text-slate-900 mb-12">
            Everything you need,
            <br />
            nothing you don't.
          </h2>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature, index) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4, delay: index * 0.1 }}
                viewport={{ once: true }}
                className="bg-white border border-slate-200 rounded-md p-6 card-hover"
              >
                <div className="w-10 h-10 bg-slate-100 rounded-md flex items-center justify-center mb-4">
                  <feature.icon size={20} className="text-slate-600" strokeWidth={1.5} />
                </div>
                <h3 className="font-heading font-semibold text-lg text-slate-900 mb-2">
                  {feature.title}
                </h3>
                <p className="text-slate-600 leading-relaxed">
                  {feature.description}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="max-w-xl">
            <h2 className="font-heading font-semibold text-2xl sm:text-3xl text-slate-900 mb-4">
              Simple, transparent pricing
            </h2>
            <p className="text-slate-600">
              One plan, everything included. No hidden fees, no complicated tiers.
            </p>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            viewport={{ once: true }}
            className="mt-12 max-w-md"
          >
            <div className="bg-white border-2 border-slate-900 rounded-md p-8">
              <div className="flex items-baseline gap-2">
                <span className="font-heading font-extrabold text-5xl text-slate-900">$99</span>
                <span className="text-slate-500">/year</span>
              </div>
              <p className="mt-2 text-slate-600">Everything you need to rotate emails</p>

              <ul className="mt-8 space-y-3">
                {pricingFeatures.map((feature) => (
                  <li key={feature} className="flex items-center gap-3 text-slate-700">
                    <Check size={18} className="text-success-green flex-shrink-0" />
                    <span>{feature}</span>
                  </li>
                ))}
              </ul>

              <Button
                onClick={handleLogin}
                className="w-full mt-8 bg-slate-900 hover:bg-slate-800 text-white"
                size="lg"
                data-testid="pricing-get-started-btn"
              >
                Get Started
                <ArrowRight size={18} className="ml-2" />
              </Button>
            </div>
          </motion.div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-6 bg-slate-900">
        <div className="max-w-7xl mx-auto">
          <div className="max-w-2xl">
            <h2 className="font-heading font-semibold text-2xl sm:text-3xl text-white mb-4">
              Ready to start rotating?
            </h2>
            <p className="text-slate-400 mb-8">
              Join small businesses that trust Rotation for their email outreach.
            </p>
            <Button
              onClick={handleLogin}
              size="lg"
              className="bg-signal-orange hover:bg-orange-600 text-white"
              data-testid="cta-get-started-btn"
            >
              Start Free Trial
              <ArrowRight size={18} className="ml-2" />
            </Button>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 border-t border-slate-200">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <span className="font-heading font-bold text-slate-900">ROTATION</span>
          <p className="text-sm text-slate-500">
            &copy; {new Date().getFullYear()} Rotation. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
