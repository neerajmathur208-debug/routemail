import { useRef, useState, useEffect } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation, useNavigate, Navigate } from "react-router-dom";
import axios from "axios";

// Font imports
import "@fontsource/manrope/400.css";
import "@fontsource/manrope/600.css";
import "@fontsource/manrope/800.css";
import "@fontsource/public-sans/400.css";
import "@fontsource/public-sans/500.css";
import "@fontsource/jetbrains-mono/400.css";

// Pages
import LandingPage from "./pages/LandingPage";
import Dashboard from "./pages/Dashboard";
import EmailAccounts from "./pages/EmailAccounts";
import EmailLists from "./pages/EmailLists";
import ListDetails from "./pages/ListDetails";
import UploadList from "./pages/UploadList";
import Campaign from "./pages/Campaign";
import CampaignLogs from "./pages/CampaignLogs";
import CampaignView from "./pages/CampaignView";
import DripCampaigns from "./pages/DripCampaigns";
import DripCampaignView from "./pages/DripCampaignView";
import DoNotEmail from "./pages/DoNotEmail";
import DoNotEmailDetail from "./pages/DoNotEmailDetail";
import BlogList from "./pages/BlogList";
import BlogDetail from "./pages/BlogDetail";
import AdminBlogs from "./pages/AdminBlogs";
import AdminDashboard from "./pages/AdminDashboard";
import AdminUserDetail from "./pages/AdminUserDetail";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Subscription from "./pages/Subscription";
import VerifyEmail from "./pages/VerifyEmail";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import PrivacyPolicy from "./pages/PrivacyPolicy";
import TermsAndConditions from "./pages/TermsAndConditions";
import AntiSpamPolicy from "./pages/AntiSpamPolicy";
import GDPRCompliance from "./pages/GDPRCompliance";

// Components
import { Toaster } from "./components/ui/sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Create axios instance
const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

// Auth Context
export { api, API, BACKEND_URL };

// Auth Callback Component
const AuthCallback = () => {
  const navigate = useNavigate();
  const hasProcessed = useRef(false);

  useEffect(() => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const processAuth = async () => {
      const hash = window.location.hash;
      const sessionIdMatch = hash.match(/session_id=([^&]+)/);
      
      if (sessionIdMatch) {
        const sessionId = sessionIdMatch[1];
        
        try {
          const response = await api.post("/auth/session", { session_id: sessionId });
          const userData = response.data;
          
          // Redirect based on user role
          const redirectPath = userData.role === "super_admin" ? "/admin" : "/dashboard";
          navigate(redirectPath, { state: { user: userData }, replace: true });
        } catch (error) {
          console.error("Auth error:", error);
          navigate("/", { replace: true });
        }
      } else {
        navigate("/", { replace: true });
      }
    };

    processAuth();
  }, [navigate]);

  return (
    <div className="min-h-screen bg-white flex items-center justify-center">
      <div className="animate-pulse text-slate-600">Authenticating...</div>
    </div>
  );
};

// Protected Route Component
const ProtectedRoute = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const [isAuthenticated, setIsAuthenticated] = useState(location.state?.user ? true : null);
  const [user, setUser] = useState(location.state?.user || null);

  useEffect(() => {
    // Skip if user passed from AuthCallback
    if (location.state?.user) {
      setUser(location.state.user);
      setIsAuthenticated(true);
      return;
    }

    const checkAuth = async () => {
      try {
        const response = await api.get("/auth/me");
        setUser(response.data);
        setIsAuthenticated(true);
      } catch (error) {
        setIsAuthenticated(false);
        navigate("/", { replace: true });
      }
    };

    checkAuth();
  }, [location.state, navigate]);

  if (isAuthenticated === null) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="animate-pulse text-slate-600">Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  // Clone children with user prop
  return typeof children === "function" ? children({ user, setUser }) : children;
};

// App Router
function AppRouter() {
  const location = useLocation();

  // Check URL fragment for session_id synchronously during render
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }

  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            {({ user, setUser }) => <Dashboard user={user} setUser={setUser} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/accounts"
        element={
          <ProtectedRoute>
            {({ user, setUser }) => <EmailAccounts user={user} setUser={setUser} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/email-lists"
        element={
          <ProtectedRoute>
            {({ user, setUser }) => <EmailLists user={user} setUser={setUser} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/email-lists/:listId"
        element={
          <ProtectedRoute>
            {({ user, setUser }) => <ListDetails user={user} setUser={setUser} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/upload"
        element={
          <ProtectedRoute>
            {({ user, setUser }) => <UploadList user={user} setUser={setUser} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/campaign"
        element={
          <ProtectedRoute>
            {({ user, setUser }) => <Campaign user={user} setUser={setUser} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/campaign/:campaignId/logs"
        element={
          <ProtectedRoute>
            {({ user, setUser }) => <CampaignLogs user={user} setUser={setUser} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/campaign/:campaignId/view"
        element={
          <ProtectedRoute>
            {({ user, setUser }) => <CampaignView user={user} setUser={setUser} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/drip-campaigns"
        element={
          <ProtectedRoute>
            {({ user, setUser }) => <DripCampaigns user={user} setUser={setUser} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/drip-campaigns/:dripId"
        element={
          <ProtectedRoute>
            {({ user, setUser }) => <DripCampaignView user={user} setUser={setUser} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/do-not-email"
        element={
          <ProtectedRoute>
            {({ user, setUser }) => <DoNotEmail user={user} setUser={setUser} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/do-not-email/:listId"
        element={
          <ProtectedRoute>
            {({ user, setUser }) => <DoNotEmailDetail user={user} setUser={setUser} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin"
        element={
          <ProtectedRoute>
            {({ user, setUser }) => <AdminDashboard user={user} setUser={setUser} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/users/:userId"
        element={
          <ProtectedRoute>
            {({ user, setUser }) => <AdminUserDetail user={user} setUser={setUser} />}
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/blogs"
        element={
          <ProtectedRoute>
            {({ user, setUser }) => <AdminBlogs user={user} setUser={setUser} />}
          </ProtectedRoute>
        }
      />
      <Route path="/blog" element={<BlogList />} />
      <Route path="/blog/:slug" element={<BlogDetail />} />
      <Route
        path="/subscription"
        element={
          <ProtectedRoute>
            {({ user, setUser }) => <Subscription user={user} setUser={setUser} />}
          </ProtectedRoute>
        }
      />
      {/* Auth Routes */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/verify-email" element={<VerifyEmail />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      {/* Legal Pages */}
      <Route path="/privacy-policy" element={<PrivacyPolicy />} />
      <Route path="/terms-and-conditions" element={<TermsAndConditions />} />
      <Route path="/anti-spam-policy" element={<AntiSpamPolicy />} />
      <Route path="/gdpr-compliance" element={<GDPRCompliance />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <div className="App font-body">
      <BrowserRouter>
        <AppRouter />
      </BrowserRouter>
      <Toaster position="bottom-right" />
    </div>
  );
}

export default App;
