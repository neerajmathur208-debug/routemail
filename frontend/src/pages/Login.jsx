import { useRef, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { motion } from "framer-motion";
import { Mail, Lock, ArrowRight, Eye, EyeOff } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { api } from "../App";
import { toast } from "sonner";
import Turnstile from "../components/Turnstile";

const TURNSTILE_SITE_KEY = process.env.REACT_APP_TURNSTILE_SITE_KEY;

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [turnstileToken, setTurnstileToken] = useState("");
  const turnstileWidgetRef = useRef(null);

  const handleEmailLogin = async (e) => {
    e.preventDefault();
    
    if (!email || !password) {
      toast.error("Please fill in all fields");
      return;
    }

    if (TURNSTILE_SITE_KEY && !turnstileToken) {
      toast.error("Please complete the security check.");
      return;
    }

    setLoading(true);
    try {
      const response = await api.post("/auth/login", {
        email,
        password,
        turnstile_token: turnstileToken || undefined,
      });
      const userData = response.data;
      
      toast.success("Login successful!");
      
      // Redirect based on role
      const redirectPath = userData.role === "super_admin" ? "/admin" : "/dashboard";
      navigate(redirectPath, { state: { user: userData }, replace: true });
    } catch (error) {
      const message = error.response?.data?.detail || "Login failed";
      toast.error(message);
      // Reset Turnstile so the user can solve a fresh challenge.
      setTurnstileToken("");
      turnstileWidgetRef.current?.reset?.();
    } finally {
      setLoading(false);
    }
  };

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
          <p className="mt-3 text-lg text-slate-600">Log in to your account</p>
        </div>

        <div className="bg-white rounded-2xl shadow-xl shadow-slate-200/50 p-8">
          {/* Email Form */}
          <form onSubmit={handleEmailLogin} className="space-y-4">
            <div>
              <Label htmlFor="email" className="text-slate-700">Email</Label>
              <div className="relative mt-1.5">
                <Mail size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
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
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
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
              <div className="flex justify-end mt-1">
                <Link 
                  to="/forgot-password"
                  className="text-xs text-blue-600 hover:text-blue-700"
                >
                  Forgot Password?
                </Link>
              </div>
            </div>

            <Button
              type="submit"
              disabled={loading || (TURNSTILE_SITE_KEY && !turnstileToken)}
              className="w-full py-6 text-base font-semibold bg-gradient-to-r from-blue-600 to-violet-600 hover:from-blue-700 hover:to-violet-700"
              data-testid="login-submit-btn"
            >
              {loading ? "Signing in..." : "Log In"}
              {!loading && <ArrowRight size={18} className="ml-2" />}
            </Button>

            {TURNSTILE_SITE_KEY && (
              <div className="pt-2" data-testid="login-turnstile-wrapper">
                <Turnstile
                  siteKey={TURNSTILE_SITE_KEY}
                  widgetRef={turnstileWidgetRef}
                  onToken={(t) => setTurnstileToken(t)}
                />
              </div>
            )}
          </form>

          {/* Register Link */}
          <p className="mt-6 text-center text-sm text-slate-600">
            Don&apos;t have an account?{" "}
            <Link to="/register" className="font-semibold text-blue-600 hover:text-blue-700" data-testid="register-link">
              Register
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
