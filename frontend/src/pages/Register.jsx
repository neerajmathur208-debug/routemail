import { useState, useEffect } from "react";
import { useNavigate, Link, useSearchParams } from "react-router-dom";
import { motion } from "framer-motion";
import { User, Mail, Lock, ArrowRight, Eye, EyeOff, Check, Zap, Crown, CheckCircle2 } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { api } from "../App";
import { toast } from "sonner";

export default function Register() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const selectedPlan = searchParams.get("plan"); // 'starter' or 'growth'
  
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    password: "",
    confirm_password: "",
  });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [currency, setCurrency] = useState("usd");
  const [registrationSuccess, setRegistrationSuccess] = useState(false);
  const [registeredEmail, setRegisteredEmail] = useState("");
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [termsError, setTermsError] = useState(false);

  useEffect(() => {
    detectCountry();
  }, []);

  const detectCountry = async () => {
    try {
      const response = await fetch("https://ipapi.co/json/");
      const data = await response.json();
      if (data.country_code === "IN") {
        setCurrency("inr");
      }
    } catch (error) {
      console.log("Could not detect country, defaulting to USD");
    }
  };

  // Get display price based on geo
  const getDisplayPrice = (plan) => {
    if (currency === "inr") {
      return plan === "starter" ? "₹5,000/year" : "₹12,000/year";
    }
    return plan === "starter" ? "$99/year" : "$149/year";
  };

  const handleGoogleLogin = () => {
    // Check terms acceptance first
    if (!acceptedTerms) {
      setTermsError(true);
      toast.error("You must accept the Terms and Conditions and Privacy Policy to create an account.");
      return;
    }
    setTermsError(false);
    
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    // Store selected plan in sessionStorage before Google auth
    if (selectedPlan) {
      sessionStorage.setItem("selectedPlan", selectedPlan);
    }
    const redirectUrl = window.location.origin + '/dashboard';
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const passwordStrength = () => {
    const { password } = formData;
    if (!password) return { score: 0, label: "" };
    
    let score = 0;
    if (password.length >= 8) score++;
    if (/[A-Z]/.test(password)) score++;
    if (/[0-9]/.test(password)) score++;
    if (/[^A-Za-z0-9]/.test(password)) score++;
    
    const labels = ["", "Weak", "Fair", "Good", "Strong"];
    const colors = ["", "bg-red-500", "bg-yellow-500", "bg-blue-500", "bg-green-500"];
    
    return { score, label: labels[score], color: colors[score] };
  };

  const handleResendVerification = async () => {
    try {
      await api.post(`/auth/resend-verification?email=${encodeURIComponent(registeredEmail)}`);
      toast.success("Verification email sent! Check your inbox.");
    } catch (error) {
      toast.error("Failed to resend. Please try again.");
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    // Check terms acceptance first
    if (!acceptedTerms) {
      setTermsError(true);
      toast.error("You must accept the Terms and Conditions and Privacy Policy to create an account.");
      return;
    }
    setTermsError(false);
    
    const { name, email, password, confirm_password } = formData;

    if (!name || !email || !password || !confirm_password) {
      toast.error("Please fill in all fields");
      return;
    }

    if (password !== confirm_password) {
      toast.error("Passwords do not match");
      return;
    }

    if (password.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }

    setLoading(true);
    try {
      const response = await api.post("/auth/register", formData);
      
      // Check for successful response (status 200-299)
      if (response.status >= 200 && response.status < 300) {
        // New registration flow - requires email verification
        if (response.data.requires_verification) {
          setRegisteredEmail(email);
          setRegistrationSuccess(true);
          // Store selected plan for after verification
          if (selectedPlan) {
            sessionStorage.setItem("selectedPlan", selectedPlan);
          }
          toast.success("Check your email to verify your account!");
          return;
        }
        
        // Fallback for any other success response
        toast.success("Account created successfully!");
        navigate("/login");
        return;
      }
    } catch (error) {
      // Only show error if it's a real error from the server
      if (error.response) {
        // Server responded with an error status
        const message = error.response.data?.detail || "Registration failed";
        toast.error(message);
      } else if (error.request) {
        // Request was made but no response received
        toast.error("Network error. Please check your connection and try again.");
      } else {
        // Something else went wrong
        toast.error("An unexpected error occurred. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  const strength = passwordStrength();

  // Show verification success screen
  if (registrationSuccess) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white rounded-2xl shadow-xl p-8 max-w-md w-full text-center"
          data-testid="verification-sent-screen"
        >
          <div className="mb-6">
            <Link to="/">
              <img 
                src="/routemail-logo.png" 
                alt="RouteMail" 
                className="h-16 mx-auto object-contain"
              />
            </Link>
          </div>
          
          {/* Success Icon with animation */}
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: "spring", stiffness: 200, damping: 15, delay: 0.2 }}
          >
            <CheckCircle2 size={64} className="mx-auto text-emerald-500 mb-4" />
          </motion.div>
          
          {/* Main Success Message */}
          <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5 mb-6" data-testid="verification-success-alert">
            <h2 className="text-xl font-bold text-emerald-800 mb-2">Verification Link Sent!</h2>
            <p className="text-emerald-700">
              Please check your email to verify your account.
            </p>
          </div>
          
          <p className="text-slate-600 mb-2">
            We've sent a verification link to:
          </p>
          <p className="font-semibold text-slate-800 mb-4 break-all">{registeredEmail}</p>
          
          {/* Important Note - Spam Folder */}
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-6 text-left" data-testid="spam-folder-note">
            <div className="flex items-start gap-3">
              <div className="text-amber-500 mt-0.5">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                  <line x1="12" y1="9" x2="12" y2="13"/>
                  <line x1="12" y1="17" x2="12.01" y2="17"/>
                </svg>
              </div>
              <div>
                <p className="text-sm text-amber-800 font-medium mb-1">Can't find the email?</p>
                <p className="text-sm text-amber-700">
                  If you don't see the email in your inbox, please check your <strong>spam</strong> or <strong>junk</strong> folder. The link expires in 2 hours.
                </p>
              </div>
            </div>
          </div>
          
          <div className="space-y-3">
            <Button
              variant="outline"
              onClick={handleResendVerification}
              className="w-full"
              data-testid="resend-verification-btn"
            >
              Resend Verification Email
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setRegistrationSuccess(false);
                setFormData({ name: "", email: "", password: "", confirm_password: "" });
              }}
              className="w-full text-slate-500"
              data-testid="use-different-email-btn"
            >
              Use Different Email
            </Button>
          </div>
          
          <p className="mt-6 text-sm text-slate-500">
            Already verified?{" "}
            <Link to="/login" className="font-semibold text-blue-600 hover:text-blue-700">
              Log In
            </Link>
          </p>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-6">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md"
      >
        {/* Logo */}
        <div className="text-center mb-8">
          <Link to="/" className="inline-block">
            <img 
              src="/routemail-logo.png" 
              alt="RouteMail" 
              className="h-20 w-auto object-contain mx-auto"
            />
          </Link>
          <p className="mt-2 text-slate-600">Create your account</p>
        </div>

        {/* Selected Plan Banner */}
        {selectedPlan && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className={`mb-4 p-4 rounded-xl flex items-center gap-3 ${
              selectedPlan === "starter" 
                ? "bg-gradient-to-r from-blue-500 to-violet-500 text-white" 
                : "bg-gradient-to-r from-amber-500 to-orange-500 text-white"
            }`}
          >
            {selectedPlan === "starter" ? <Zap size={20} /> : <Crown size={20} />}
            <div>
              <p className="font-semibold capitalize">{selectedPlan} Plan Selected</p>
              <p className="text-sm opacity-90">
                {getDisplayPrice(selectedPlan)} - You'll checkout after verification
              </p>
            </div>
          </motion.div>
        )}

        <div className="bg-white rounded-2xl shadow-xl shadow-slate-200/50 p-8">
          {/* Google Sign Up */}
          <Button
            type="button"
            variant="outline"
            className="w-full py-6 text-base font-medium border-2 hover:bg-slate-50"
            onClick={handleGoogleLogin}
            data-testid="google-register-btn"
          >
            <svg className="w-5 h-5 mr-3" viewBox="0 0 24 24">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            Continue with Google
          </Button>

          {/* Divider */}
          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-200" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-4 bg-white text-slate-500">or register with email</span>
            </div>
          </div>

          {/* Email Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="name" className="text-slate-700">Full Name</Label>
              <div className="relative mt-1.5">
                <User size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  id="name"
                  name="name"
                  type="text"
                  value={formData.name}
                  onChange={handleChange}
                  placeholder="John Doe"
                  className="pl-10 py-5"
                  data-testid="name-input"
                />
              </div>
            </div>

            <div>
              <Label htmlFor="email" className="text-slate-700">Email</Label>
              <div className="relative mt-1.5">
                <Mail size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  id="email"
                  name="email"
                  type="email"
                  value={formData.email}
                  onChange={handleChange}
                  placeholder="you@example.com"
                  className="pl-10 py-5"
                  data-testid="email-input"
                />
              </div>
            </div>

            <div>
              <Label htmlFor="password" className="text-slate-700">Password</Label>
              <div className="relative mt-1.5">
                <Lock size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  id="password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  value={formData.password}
                  onChange={handleChange}
                  placeholder="Min 8 characters"
                  className="pl-10 pr-10 py-5"
                  data-testid="password-input"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
              {/* Password strength indicator */}
              {formData.password && (
                <div className="mt-2">
                  <div className="flex gap-1">
                    {[1, 2, 3, 4].map((i) => (
                      <div
                        key={i}
                        className={`h-1 flex-1 rounded-full ${
                          i <= strength.score ? strength.color : "bg-slate-200"
                        }`}
                      />
                    ))}
                  </div>
                  <p className="text-xs text-slate-500 mt-1">{strength.label}</p>
                </div>
              )}
            </div>

            <div>
              <Label htmlFor="confirm_password" className="text-slate-700">Confirm Password</Label>
              <div className="relative mt-1.5">
                <Lock size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  id="confirm_password"
                  name="confirm_password"
                  type={showPassword ? "text" : "password"}
                  value={formData.confirm_password}
                  onChange={handleChange}
                  placeholder="Confirm password"
                  className="pl-10 pr-10 py-5"
                  data-testid="confirm-password-input"
                />
                {formData.confirm_password && formData.password === formData.confirm_password && (
                  <Check size={18} className="absolute right-3 top-1/2 -translate-y-1/2 text-green-500" />
                )}
              </div>
            </div>

            {/* Terms and Privacy Checkbox */}
            <div className="flex items-start gap-3">
              <input
                type="checkbox"
                id="accept-terms"
                checked={acceptedTerms}
                onChange={(e) => {
                  setAcceptedTerms(e.target.checked);
                  if (e.target.checked) setTermsError(false);
                }}
                className={`mt-1 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 ${
                  termsError ? "border-red-500 ring-1 ring-red-500" : ""
                }`}
                data-testid="accept-terms-checkbox"
              />
              <label htmlFor="accept-terms" className="text-sm text-slate-600">
                I agree to the{" "}
                <a
                  href="/terms-and-conditions"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline"
                >
                  Terms and Conditions
                </a>{" "}
                and{" "}
                <a
                  href="/privacy-policy"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline"
                >
                  Privacy Policy
                </a>
              </label>
            </div>
            {termsError && (
              <p className="text-sm text-red-500 -mt-2">
                You must accept the Terms and Conditions and Privacy Policy to create an account.
              </p>
            )}

            <Button
              type="submit"
              disabled={loading}
              className="w-full py-6 text-base font-semibold bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700"
              data-testid="register-submit-btn"
            >
              {loading ? "Creating account..." : "Create Account"}
              {!loading && <ArrowRight size={18} className="ml-2" />}
            </Button>
          </form>

          {/* Trial Note */}
          <p className="mt-4 text-center text-xs text-slate-500">
            Start with a 14-day free trial. No credit card required.
          </p>

          {/* Login Link */}
          <p className="mt-6 text-center text-sm text-slate-600">
            Already have an account?{" "}
            <Link to="/login" className="font-semibold text-blue-600 hover:text-blue-700" data-testid="login-link">
              Log In
            </Link>
          </p>
        </div>

        {/* Back to Home */}
        <p className="mt-6 text-center text-sm text-slate-500">
          <Link to="/" className="hover:text-slate-700">
            ← Back to home
          </Link>
        </p>
      </motion.div>
    </div>
  );
}
