import { useEffect, useState } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { api } from "../App";

export default function VerifyEmail() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState("verifying"); // verifying, success, error
  const [message, setMessage] = useState("");

  useEffect(() => {
    const token = searchParams.get("token");
    
    if (!token) {
      setStatus("error");
      setMessage("Invalid verification link. Please request a new one.");
      return;
    }

    const verifyEmail = async () => {
      try {
        const response = await api.get(`/auth/verify-email?token=${token}`);
        setStatus("success");
        setMessage(response.data.message || "Email verified successfully!");
        
        // Redirect to dashboard after 2 seconds
        setTimeout(() => {
          navigate("/dashboard");
        }, 2000);
      } catch (error) {
        setStatus("error");
        setMessage(error.response?.data?.detail || "Verification failed. Please try again.");
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
            <h2 className="text-xl font-semibold text-slate-800 mb-2">Email Verified!</h2>
            <p className="text-slate-500 mb-4">{message}</p>
            <p className="text-sm text-slate-400">Redirecting to dashboard...</p>
          </>
        )}

        {status === "error" && (
          <>
            <XCircle size={48} className="mx-auto text-red-500 mb-4" />
            <h2 className="text-xl font-semibold text-slate-800 mb-2">Verification Failed</h2>
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
