import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Mail,
  FileText,
  Upload,
  Send,
  Workflow,
  ShieldOff,
  LogOut,
  Menu,
  X,
  ChevronRight,
  Shield,
  CreditCard,
  Crown,
  Zap,
  Archive,
  Inbox,
  Star,
  Server,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { api } from "../App";
import { toast } from "sonner";

const navItems = [
  { path: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { path: "/accounts", label: "Email Accounts", icon: Mail },
  { path: "/email-lists", label: "Email Lists", icon: FileText },
  { path: "/campaign", label: "Campaign", icon: Send },
  { path: "/drip-campaigns", label: "Drip Campaigns", icon: Workflow },
  { path: "/unibox", label: "Unibox", icon: Inbox },
  { path: "/leads", label: "Responses / Leads", icon: Star },
  { path: "/do-not-email", label: "Do Not Email", icon: ShieldOff },
  { path: "/backup", label: "Backup & Restore", icon: Archive },
  { path: "/subscription", label: "Subscription", icon: CreditCard },
];

export default function Sidebar({ user, setUser }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [userPlan, setUserPlan] = useState(null);

  const isSuperAdmin = user?.role === "super_admin";

  // Fetch user subscription status
  useEffect(() => {
    const fetchSubscription = async () => {
      try {
        const response = await api.get("/subscription/status");
        setUserPlan(response.data);
      } catch (error) {
        console.error("Failed to fetch subscription:", error);
      }
    };
    fetchSubscription();
  }, []);

  const getPlanBadge = () => {
    if (!userPlan) return null;
    
    const planType = userPlan.plan_type || "free";
    const isActive = userPlan.subscription_active;
    
    if (planType === "growth") {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800">
          <Crown size={12} />
          Growth
        </span>
      );
    } else if (planType === "starter") {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
          <Zap size={12} />
          Starter
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600">
          Free Plan
        </span>
      );
    }
  };

  const handleLogout = async () => {
    try {
      await api.post("/auth/logout");
      setUser(null);
      navigate("/", { replace: true });
    } catch (error) {
      toast.error("Failed to logout");
    }
  };

  const NavLink = ({ item }) => {
    const isActive = location.pathname === item.path || location.pathname.startsWith(item.path + "/");
    const Icon = item.icon;

    return (
      <button
        data-testid={`nav-${item.path.replace("/", "")}`}
        onClick={() => {
          navigate(item.path);
          setMobileOpen(false);
        }}
        className={`sidebar-link w-full ${isActive ? "active" : ""}`}
      >
        <Icon size={20} strokeWidth={1.5} />
        <span className="font-medium">{item.label}</span>
        {isActive && <ChevronRight size={16} className="ml-auto" />}
      </button>
    );
  };

  return (
    <>
      {/* Mobile header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 h-20 bg-white border-b border-slate-200 z-40 flex items-center justify-between px-4">
        <div className="flex items-center gap-2 cursor-pointer" onClick={() => navigate("/dashboard")}>
          <img 
            src="/routemail-logo.png" 
            alt="RouteMail" 
            className="h-14 w-auto object-contain"
          />
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setMobileOpen(!mobileOpen)}
          data-testid="mobile-menu-toggle"
        >
          {mobileOpen ? <X size={24} /> : <Menu size={24} />}
        </Button>
      </div>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/20 z-40"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed top-0 left-0 h-full w-[280px] bg-white border-r border-slate-200 z-50
          flex flex-col transition-transform duration-300 ease-in-out
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}
          lg:translate-x-0 lg:static lg:z-auto
        `}
      >
        {/* Logo */}
        <div className="h-24 flex items-center px-6 border-b border-slate-200 py-4">
          <img 
            src="/routemail-logo.png" 
            alt="RouteMail" 
            className="h-20 w-auto object-contain cursor-pointer"
            onClick={() => navigate("/dashboard")}
            data-testid="sidebar-logo"
          />
        </div>

        {/* User info */}
        <div className="p-6 border-b border-slate-200">
          <div className="flex items-center gap-3">
            {user?.picture ? (
              <img
                src={user.picture}
                alt={user.name}
                className="w-10 h-10 rounded-full"
              />
            ) : (
              <div className="w-10 h-10 rounded-full bg-slate-200 flex items-center justify-center">
                <span className="text-slate-600 font-semibold">
                  {user?.name?.charAt(0) || "U"}
                </span>
              </div>
            )}
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-slate-900 truncate">{user?.name}</p>
              <p className="text-sm text-slate-500 truncate">{user?.email}</p>
            </div>
          </div>
          <div className="mt-3">
            {getPlanBadge()}
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink key={item.path} item={item} />
          ))}
          
          {/* Admin Panel Link - Only for super_admin */}
          {isSuperAdmin && (
            <>
              <button
                data-testid="nav-admin"
                onClick={() => {
                  navigate("/admin");
                  setMobileOpen(false);
                }}
                className={`sidebar-link w-full mt-4 border-t border-slate-200 pt-4 ${
                  location.pathname === "/admin" || location.pathname.startsWith("/admin/users") || location.pathname.startsWith("/admin/blogs") ? "active" : ""
                }`}
              >
                <Shield size={20} strokeWidth={1.5} className="text-violet-600" />
                <span className="font-medium text-violet-600">Admin Panel</span>
                {(location.pathname === "/admin" || location.pathname.startsWith("/admin/users") || location.pathname.startsWith("/admin/blogs")) && (
                  <ChevronRight size={16} className="ml-auto" />
                )}
              </button>
              <button
                data-testid="nav-system-backup"
                onClick={() => {
                  navigate("/admin/system-backup");
                  setMobileOpen(false);
                }}
                className={`sidebar-link w-full ${
                  location.pathname.startsWith("/admin/system-backup") ? "active" : ""
                }`}
              >
                <Server size={20} strokeWidth={1.5} className="text-violet-600" />
                <span className="font-medium text-violet-600">System Backup &amp; Restore</span>
                {location.pathname.startsWith("/admin/system-backup") && (
                  <ChevronRight size={16} className="ml-auto" />
                )}
              </button>
            </>
          )}
        </nav>

        {/* Logout */}
        <div className="p-4 border-t border-slate-200">
          <button
            onClick={handleLogout}
            className="sidebar-link w-full text-slate-500 hover:text-red-600"
            data-testid="logout-btn"
          >
            <LogOut size={20} strokeWidth={1.5} />
            <span className="font-medium">Sign Out</span>
          </button>
        </div>

        {/* Support footer — visible on every dashboard page that uses Sidebar */}
        <div
          className="px-4 py-3 border-t border-slate-100 bg-slate-50/60 text-[11px] leading-snug text-slate-500"
          data-testid="sidebar-support-footer"
        >
          <span className="font-medium text-slate-600">Need help?</span>{" "}
          <span className="block sm:inline">
            For any queries or support, please contact{" "}
            <a
              href="mailto:support@routemail.co"
              className="text-blue-600 hover:text-blue-700 underline break-all"
              data-testid="support-email-link"
            >
              support@routemail.co
            </a>
          </span>
        </div>
      </aside>

      {/* Main content spacer for mobile */}
      <div className="lg:hidden h-20" />
    </>
  );
}
