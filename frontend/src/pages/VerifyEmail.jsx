import { useEffect, useState, useRef } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { CheckCircle2, XCircle, Loader2, AlertTriangle } from "lucide-react";
import { Button } from "../components/ui/button";
import { api } from "../App";

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState("verifying"); // verifying, success, error, expired, already_verified
  const [message, setMessage] = useState("");
  const [redirectUrl, setRedirectUrl] = useState(null);
  const verificationAttempted = useRef(false);
  const verificationCompleted = useRef(false);

  useEffect(() => {
    const token = searchParams.get("token");
    
    // Debug logging for troubleshooting
    console.log("[VERIFY] Token from URL:", token);
    console.log("[VERIFY] Token length:", token?.length || 0);
    
    if (!token) {
      setStatus("error");
      setMessage("Invalid verification link.");
      return;
    }

    // Prevent double execution (React StrictMode or accidental re-renders)
    if (verificationAttempted.current) {
      return;
    }
    verificationAttempted.current = true;

    const verifyEmail = async () => {
      try {
        // URL encode the token to handle special characters properly
        const encodedToken = encodeURIComponent(token);
        console.log("[VERIFY] Encoded token:", encodedToken);
        console.log("[VERIFY] Making API request...");
        
        const response = await api.get(`/auth/verify-email?token=${encodedToken}`);
        
        console.log("[VERIFY] API Response:", response.data);
        
        // Prevent state updates if already completed (race condition protection)
        if (verificationCompleted.current) return;
        verificationCompleted.current = true;
        
        const data = response.data;
        
        // Check if it was already verified
        if (data.message?.toLowerCase().includes("already")) {
          setStatus("already_verified");
          setMessage("Your email has already been verified.");
        } else {
          setStatus("success");
          setMessage(data.message || "Email verified successfully!");
        }
        
        // Use redirect URL from API response (production URL)
        const targetUrl = data.redirect_url || "/dashboard";
        setRedirectUrl(targetUrl);
        
        // Redirect to production dashboard after 1.5 seconds
        setTimeout(() => {
          // Use window.location.href for absolute URL to ensure we go to production domain
          if (targetUrl.startsWith("http")) {
            window.location.href = targetUrl;
          } else {
            navigate(targetUrl);
          }
        }, 1500);
      } catch (error) {
        console.log("[VERIFY] API Error:", error.response?.data || error.message);
        
        // Prevent state updates if verification already succeeded
        if (verificationCompleted.current) return;
        verificationCompleted.current = true;
        
        const errorDetail = error.response?.data?.detail || "Verification failed. Please try again.";
        
        // Check for specific error types - order matters!
        // Check "invalid" first since it may also contain "expired" phrase
        if (errorDetail.toLowerCase().includes("invalid")) {
          setStatus("error");
          setMessage("Invalid verification link.");
        } else if (errorDetail.toLowerCase().includes("has expired") || 
                   errorDetail.toLowerCase().startsWith("verification link expired")) {
          setStatus("expired");
          setMessage("Verification link expired. Please request a new verification email.");
        } else if (errorDetail.toLowerCase().includes("already been used") || 
                   errorDetail.toLowerCase().includes("already verified")) {
          // Link was already used - treat as success since account is verified
          setStatus("already_verified");
          setMessage("Your email has already been verified.");
          // Redirect to login
          setTimeout(() => {
            navigate("/login");
          }, 1500);
        } else {
          setStatus("error");
          setMessage(errorDetail);
        }
      }
    };

    verifyEmail();
  }, [searchParams, navigate]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="bg-white rounded-2xl shadow-lg p-8 max-w-md w-full text-center"
      >
        {/* Logo */}
        <div className="mb-6">
          <img 
            src="/routemail-logo.png" 
            alt="RouteMail" 
            className="h-16 mx-auto object-contain"
          />
        </div>

        {status === "verifying" && (
          <>
            <Loader2 size={48} className="mx-auto text-blue-500 animate-spin mb-4" />
            <h2 className="text-xl font-semibold text-slate-800 mb-2">Verifying Your Email</h2>
            <p className="text-slate-500">Please wait while we verify your email address...</p>
          </>
        )}

        {status === "success" && (
          <>
            <CheckCircle2 size={48} className="mx-auto text-emerald-500 mb-4" />
            <h2 className="text-xl font-semibold text-slate-800 mb-2" data-testid="verify-success-title">Email Verified!</h2>
            <p className="text-slate-500 mb-4">{message}</p>
            <p className="text-sm text-slate-400">Redirecting to your dashboard...</p>
          </>
        )}

        {status === "already_verified" && (
          <>
            <CheckCircle2 size={48} className="mx-auto text-emerald-500 mb-4" />
            <h2 className="text-xl font-semibold text-slate-800 mb-2" data-testid="verify-already-title">Already Verified</h2>
            <p className="text-slate-500 mb-4">{message}</p>
            <p className="text-sm text-slate-400">Redirecting...</p>
          </>
        )}

        {status === "expired" && (
          <>
            <AlertTriangle size={48} className="mx-auto text-amber-500 mb-4" />
            <h2 className="text-xl font-semibold text-slate-800 mb-2">Verification Link Expired</h2>
            <p className="text-slate-500 mb-6">{message}</p>
            <div className="space-y-3">
              <Button 
                onClick={() => navigate("/register")}
                className="w-full bg-blue-600 hover:bg-blue-700"
              >
                Request New Verification Email
              </Button>
            </div>
          </>
        )}

        {status === "error" && (
          <>
            <XCircle size={48} className="mx-auto text-red-500 mb-4" />
            <h2 className="text-xl font-semibold text-slate-800 mb-2">Invalid Verification Link</h2>
            <p className="text-slate-500 mb-6">{message}</p>
            <div className="space-y-3">
              <Button 
                onClick={() => navigate("/register")}
                className="w-full bg-blue-600 hover:bg-blue-700"
              >
                Register Again
              </Button>
              <Button 
                variant="outline"
                onClick={() => navigate("/login")}
                className="w-full"
              >
                Go to Login
              </Button>
            </div>
          </>
        )}
      </motion.div>
    </div>
  );
}
