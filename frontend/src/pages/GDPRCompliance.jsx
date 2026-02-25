import { motion } from "framer-motion";
import { useNavigate, Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "../components/ui/button";

export default function GDPRCompliance() {
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
          <h1 className="text-3xl md:text-4xl font-bold text-slate-900 mb-8">
            GDPR Compliance
          </h1>

          <div className="prose prose-slate max-w-none">
            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">Commitment to GDPR</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              Although RouteMail is based in India, we support global users and align our practices with GDPR for EU data subjects.
            </p>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">Roles</h2>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li><strong>Account data</strong> → Controller</li>
              <li><strong>Campaign data</strong> → Processor</li>
            </ul>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">Data Subject Rights</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              EU users may:
            </p>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>Access personal data</li>
              <li>Request deletion</li>
              <li>Request correction</li>
              <li>Object to processing</li>
              <li>Request portability</li>
            </ul>
            <p className="text-slate-700 leading-relaxed mb-4">
              Requests: <a href="mailto:support@routemail.co" className="text-blue-600 hover:underline">support@routemail.co</a>
            </p>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">Data Transfers</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              Where EU data is transferred outside the EU, appropriate safeguards may apply.
            </p>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-6 mt-8">
              <h3 className="text-lg font-semibold text-blue-900 mb-3">Contact Us</h3>
              <p className="text-blue-800">
                For any GDPR-related inquiries or to exercise your data rights, please contact us at:
              </p>
              <p className="text-blue-900 font-medium mt-2">
                <a href="mailto:support@routemail.co" className="hover:underline">support@routemail.co</a>
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
          <Link to="/anti-spam-policy" className="hover:text-slate-700">Anti-Spam Policy</Link>
          <span className="text-slate-300">|</span>
          <Link to="/gdpr-compliance" className="hover:text-slate-700 font-medium text-blue-600">GDPR Compliance</Link>
        </div>
      </main>
    </div>
  );
}
