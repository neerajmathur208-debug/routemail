import { motion } from "framer-motion";
import { useNavigate, Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { Button } from "../components/ui/button";

export default function PrivacyPolicy() {
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
            Privacy Policy
          </h1>
          <p className="text-slate-500 mb-8">Last Updated: 25-02-2026</p>

          <div className="prose prose-slate max-w-none">
            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">1. Introduction</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              RouteMail ("RouteMail", "Company", "we", "our", "us") operates routemail.co and provides an email rotation and delivery management platform that enables users to connect multiple email accounts, upload contact lists, and manage campaign sending infrastructure.
            </p>
            <p className="text-slate-700 leading-relaxed mb-4">
              We are committed to protecting personal data in accordance with:
            </p>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>The Information Technology Act, 2000 (India)</li>
              <li>IT (Reasonable Security Practices and Procedures and Sensitive Personal Data or Information) Rules, 2011</li>
              <li>Digital Personal Data Protection Act, 2023 (India)</li>
              <li>GDPR (for users located in the European Union)</li>
            </ul>
            <p className="text-slate-700 leading-relaxed mb-4">
              By using RouteMail, you agree to this Privacy Policy.
            </p>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">2. Data Fiduciary / Controller Information</h2>
            <p className="text-slate-700 leading-relaxed mb-2">
              Registered in India<br />
              <strong>RouteMail</strong><br />
              Perfect Multimedia<br />
              1036C B3 Tower Spaze iTech Park, Gurgaon, Haryana 122018<br />
              Email: support@routemail.co
            </p>
            <p className="text-slate-700 leading-relaxed mb-4">
              For data protection purposes:
            </p>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>We act as a Data Fiduciary (India) for account and billing data.</li>
              <li>We act as a Data Processor for contact lists and campaign content uploaded by users.</li>
            </ul>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">3. Information We Collect</h2>
            
            <h3 className="text-lg font-medium text-slate-800 mt-6 mb-3">A. Account Information</h3>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>Name</li>
              <li>Business name</li>
              <li>Email address</li>
              <li>Password (encrypted and hashed)</li>
              <li>Contact number (if provided)</li>
              <li>Billing details</li>
            </ul>

            <h3 className="text-lg font-medium text-slate-800 mt-6 mb-3">B. Payment Information</h3>
            <p className="text-slate-700 leading-relaxed mb-4">
              Payments are processed via third-party payment processors. We do not store full card details.
            </p>

            <h3 className="text-lg font-medium text-slate-800 mt-6 mb-3">C. Campaign Data (Processed on Your Instructions)</h3>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>Email addresses of recipients</li>
              <li>Uploaded contact lists</li>
              <li>Campaign content</li>
              <li>Subject lines</li>
              <li>Sending schedule</li>
              <li>Performance metrics (opens, clicks, bounce data)</li>
            </ul>
            <p className="text-slate-700 leading-relaxed mb-4">
              We process this data solely to provide the service.
            </p>

            <h3 className="text-lg font-medium text-slate-800 mt-6 mb-3">D. Technical & Usage Data</h3>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>IP address</li>
              <li>Browser type</li>
              <li>Device information</li>
              <li>Login timestamps</li>
              <li>API usage logs</li>
              <li>Sending volume data</li>
              <li>Spam complaint metrics</li>
            </ul>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">4. Purpose of Processing</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              We process personal data to:
            </p>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>Provide, operate, and maintain the platform</li>
              <li>Authenticate users</li>
              <li>Enable email sending functionality</li>
              <li>Monitor abuse and spam activity</li>
              <li>Improve platform performance</li>
              <li>Process payments</li>
              <li>Comply with legal obligations</li>
            </ul>
            <p className="text-slate-700 leading-relaxed mb-4">
              We do not sell or rent personal data.
            </p>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">5. Legal Basis</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              We process data based on:
            </p>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>User consent</li>
              <li>Contractual necessity</li>
              <li>Legitimate business interests</li>
              <li>Compliance with legal obligations</li>
            </ul>
            <p className="text-slate-700 leading-relaxed mb-4">
              For EU users, GDPR lawful bases apply accordingly.
            </p>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">6. Data Retention</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              We retain:
            </p>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>Account data: while your account is active</li>
              <li>Campaign data: until deleted by user or account termination</li>
              <li>Logs: retained for security and compliance monitoring</li>
            </ul>
            <p className="text-slate-700 leading-relaxed mb-4">
              We may retain certain data where legally required.
            </p>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">7. Data Security</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              We implement reasonable technical and organizational safeguards including:
            </p>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>HTTPS encryption</li>
              <li>Secure server infrastructure</li>
              <li>Role-based access controls</li>
              <li>Abuse monitoring systems</li>
              <li>OAuth-based email integrations</li>
            </ul>
            <p className="text-slate-700 leading-relaxed mb-4">
              However, no system is completely secure.
            </p>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">8. International Data Transfers</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              Data may be stored or processed outside India depending on hosting providers.
            </p>
            <p className="text-slate-700 leading-relaxed mb-4">
              For EU users, appropriate safeguards may be implemented.
            </p>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">9. Your Rights</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              Under Indian law:
            </p>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>Access your personal data</li>
              <li>Request correction</li>
              <li>Request erasure</li>
              <li>Withdraw consent</li>
            </ul>
            <p className="text-slate-700 leading-relaxed mb-4">
              Under GDPR (for EU users):
            </p>
            <ul className="list-disc pl-6 text-slate-700 space-y-2 mb-4">
              <li>Access</li>
              <li>Rectification</li>
              <li>Erasure</li>
              <li>Restriction</li>
              <li>Portability</li>
              <li>Objection</li>
            </ul>
            <p className="text-slate-700 leading-relaxed mb-4">
              Requests: support@routemail.co
            </p>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">10. Children's Data</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              RouteMail is not intended for individuals under 18 years of age.
            </p>

            <h2 className="text-xl font-semibold text-slate-900 mt-8 mb-4">11. Updates</h2>
            <p className="text-slate-700 leading-relaxed mb-4">
              We may update this policy periodically. Continued use constitutes acceptance.
            </p>
          </div>
        </motion.div>

        {/* Footer Links */}
        <div className="mt-8 flex flex-wrap justify-center gap-4 text-sm text-slate-500">
          <Link to="/privacy-policy" className="hover:text-slate-700 font-medium text-blue-600">Privacy Policy</Link>
          <span className="text-slate-300">|</span>
          <Link to="/terms-and-conditions" className="hover:text-slate-700">Terms & Conditions</Link>
          <span className="text-slate-300">|</span>
          <Link to="/anti-spam-policy" className="hover:text-slate-700">Anti-Spam Policy</Link>
          <span className="text-slate-300">|</span>
          <Link to="/gdpr-compliance" className="hover:text-slate-700">GDPR Compliance</Link>
        </div>
      </main>
    </div>
  );
}
