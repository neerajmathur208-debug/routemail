import { motion } from "framer-motion";
import { useNavigate, Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "../components/ui/button";

export default function TermsAndConditions() {
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
            Terms and Conditions
          </h1>
          <p className="text-slate-500 mb-8">Last Updated: 25-02-2026</p>

          <div className="prose prose-slate max-w-none">
            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">1. Acceptance of Terms</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              By accessing or using RouteMail, you agree to be bound by these Terms.
            </p>
            <p className="text-slate-700 leading-relaxed mb-4">
              If you do not agree, you must not use the service.
            </p>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">2. Description of Service</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              RouteMail is an email rotation platform that enables users to:
            </p>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>Connect multiple email accounts</li>
              <li>Send campaigns using rotation logic</li>
              <li>Monitor sending metrics</li>
            </ul>
            <p className="text-slate-700 leading-relaxed mb-4">
              We do not guarantee inbox placement, deliverability rates, or campaign performance.
            </p>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">3. Eligibility</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              You must:
            </p>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>Be at least 18 years old</li>
              <li>Use the service for lawful business purposes</li>
              <li>Have legal authority to represent your organization</li>
            </ul>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">4. User Responsibilities</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              You are solely responsible for:
            </p>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>The legality of your contact lists</li>
              <li>Ensuring lawful basis to email recipients</li>
              <li>Complying with all anti-spam laws</li>
              <li>Campaign content accuracy</li>
            </ul>
            <p className="text-slate-700 leading-relaxed mb-4">
              RouteMail does not review campaign content before sending.
            </p>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">5. Prohibited Use</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              You may not use RouteMail for:
            </p>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>Spam campaigns</li>
              <li>Fraud or phishing</li>
              <li>Illegal products</li>
              <li>Prohibited content (as defined in Anti-Spam Policy)</li>
              <li>Malware distribution</li>
            </ul>
            <p className="text-slate-700 leading-relaxed mb-4">
              We reserve the right to suspend accounts without notice.
            </p>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">6. Payments & Billing</h2>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>Subscriptions are billed annually.</li>
              <li>Fees must be paid in advance.</li>
              <li>Failure to pay may result in suspension.</li>
            </ul>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">7. NO REFUND POLICY</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              All payments are final and non-refundable.
            </p>
            <p className="text-slate-700 leading-relaxed mb-4">
              We do not provide refunds for:
            </p>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>Partial usage</li>
              <li>Deliverability issues</li>
              <li>Account suspension due to policy violation</li>
              <li>User dissatisfaction</li>
              <li>Technical misunderstanding</li>
            </ul>
            <p className="text-slate-700 leading-relaxed mb-4">
              If an account is suspended for violation of policies, no refund shall be issued under any circumstances.
            </p>
            <p className="text-slate-700 leading-relaxed mb-4">
              Exceptions apply only where required by applicable law.
            </p>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">8. Account Suspension & Termination</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              We may suspend or terminate accounts for:
            </p>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>High spam complaint rates</li>
              <li>Blacklisting</li>
              <li>Abuse reports</li>
              <li>Violation of Anti-Spam Policy</li>
              <li>Fraudulent activity</li>
            </ul>
            <p className="text-slate-700 leading-relaxed mb-4">
              We are not liable for resulting business losses.
            </p>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">9. Limitation of Liability</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              RouteMail shall not be liable for:
            </p>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>Deliverability failures</li>
              <li>Third-party email provider restrictions</li>
              <li>Blacklisting events</li>
              <li>Indirect or consequential damages</li>
            </ul>
            <p className="text-slate-700 leading-relaxed mb-4">
              Maximum liability shall not exceed the amount paid in the previous three (3) months.
            </p>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">10. Indemnification</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              You agree to indemnify RouteMail against claims arising from:
            </p>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>Your email campaigns</li>
              <li>Legal violations</li>
              <li>Data protection breaches caused by you</li>
            </ul>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">11. Governing Law</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              These Terms are governed by the laws of India.
            </p>
          </div>
        </motion.div>

        {/* Footer Links */}
        <div className="mt-8 flex flex-wrap justify-center gap-4 text-sm text-slate-500">
          <Link to="/privacy-policy" className="hover:text-slate-700">Privacy Policy</Link>
          <span className="text-slate-300">|</span>
          <Link to="/terms-and-conditions" className="hover:text-slate-700 font-medium text-blue-600">Terms & Conditions</Link>
          <span className="text-slate-300">|</span>
          <Link to="/anti-spam-policy" className="hover:text-slate-700">Anti-Spam Policy</Link>
          <span className="text-slate-300">|</span>
          <Link to="/gdpr-compliance" className="hover:text-slate-700">GDPR Compliance</Link>
        </div>
      </main>
    </div>
  );
}
