import { motion } from "framer-motion";
import { useNavigate, Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "../components/ui/button";

export default function AntiSpamPolicy() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-6 py-4 flex items-center gap-4">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate(-1)}
            data-testid="back-btn"
          >
            <ArrowLeft size={20} />
          </Button>
          <Link to="/" className="flex items-center">
            <img 
              src="/routemail-logo.png" 
              alt="RouteMail" 
              className="h-8 w-auto object-contain"
            />
          </Link>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-4xl mx-auto px-6 py-12">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-xl shadow-sm border border-slate-200 p-8 md:p-12"
        >
          <h1 className="text-3xl md:text-4xl font-bold text-slate-900 mb-2">
            Anti-Spam & Acceptable Use Policy
          </h1>
          <p className="text-slate-500 mb-8">Effective Date: 25-02-2026</p>

          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-8">
            <p className="text-red-800 font-semibold">
              RouteMail maintains a strict zero-tolerance spam policy.
            </p>
          </div>

          <div className="prose prose-slate max-w-none">
            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">Prohibited Activities</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              Users may not send:
            </p>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>Unsolicited bulk emails</li>
              <li>Purchased or scraped lists</li>
              <li>Deceptive subject lines</li>
              <li>Phishing content</li>
              <li>Malware</li>
            </ul>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">Prohibited Content Categories</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              Users may not promote:
            </p>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>Pornography or explicit adult content</li>
              <li>Escort services</li>
              <li>Illegal drugs or unregulated pharmaceuticals</li>
              <li>Firearms or weapons</li>
              <li>Hate speech or extremist material</li>
              <li>Gambling services (unless legally licensed)</li>
              <li>Get-rich-quick schemes</li>
              <li>Crypto scams</li>
              <li>Counterfeit goods</li>
              <li>Misleading medical claims</li>
            </ul>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">Monitoring</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              We actively monitor:
            </p>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>Bounce rates</li>
              <li>Spam complaints</li>
              <li>Blacklists</li>
              <li>Sending patterns</li>
            </ul>

            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mt-8">
              <p className="text-amber-800 font-medium mb-2">Important Notice</p>
              <p className="text-amber-700">
                Accounts may be suspended immediately for violations. No refunds will be issued for violations.
              </p>
            </div>
          </div>
        </motion.div>

        {/* Footer Links */}
        <div className="mt-8 flex flex-wrap justify-center gap-4 text-sm text-slate-500">
          <Link to="/privacy-policy" className="hover:text-slate-700">Privacy Policy</Link>
          <span className="text-slate-300">|</span>
          <Link to="/terms-and-conditions" className="hover:text-slate-700">Terms & Conditions</Link>
          <span className="text-slate-300">|</span>
          <Link to="/anti-spam-policy" className="hover:text-slate-700 font-medium text-blue-600">Anti-Spam Policy</Link>
          <span className="text-slate-300">|</span>
          <Link to="/gdpr-compliance" className="hover:text-slate-700">GDPR Compliance</Link>
        </div>
      </main>
    </div>
  );
}
