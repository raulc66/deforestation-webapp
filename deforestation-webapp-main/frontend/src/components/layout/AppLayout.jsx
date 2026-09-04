import { NavLink, useNavigate } from "react-router-dom";
import { LayoutDashboard, LogOut, FileText, ClipboardList, BellRing, CreditCard, Menu, X, Trees } from "lucide-react";
import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { useDemo } from "@/context/DemoContext";
import { Button } from "@/components/ui/button";
import OrganizationSelector from "@/components/organization/OrganizationSelector";
import TrialStatusBar from "@/components/trial/TrialStatusBar";
import { isDemoUser } from "@/lib/demo";

const CUSTOMER_NAV = [
  { to: "/dashboard", label: "Command Center", icon: LayoutDashboard, testId: "nav-dashboard" },
  { to: "/alerts", label: "Alerts", icon: BellRing, testId: "nav-alerts" },
  { to: "/investigations", label: "Investigations", icon: ClipboardList, testId: "nav-investigations" },
  { to: "/reports", label: "Reports", icon: FileText, testId: "nav-reports" },
  { to: "/billing", label: "Plan", icon: CreditCard, testId: "nav-billing" },
];

const DEMO_NAV = [
  { to: "/dashboard", label: "Command Center", icon: LayoutDashboard, testId: "nav-dashboard" },
  { to: "/alerts", label: "Alerts", icon: BellRing, testId: "nav-alerts" },
];

export default function AppLayout({ children }) {
  const { user, logout } = useAuth();
  const { isDemo } = useDemo();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const demo = isDemo || isDemoUser(user);
  const navItems = demo ? DEMO_NAV : CUSTOMER_NAV;

  const handleLogout = async () => {
    await logout();
    navigate("/explore");
  };

  return (
    <div className="min-h-screen flex bg-[#f4f5f2]">
      <aside
        data-testid="sidebar"
        className="hidden md:flex flex-col w-64 bg-white border-r border-[#eaece6] sticky top-0 h-screen"
      >
        <div className="px-6 py-7 border-b border-[#eaece6]">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-md bg-[#2d5a27] flex items-center justify-center">
              <Trees className="w-5 h-5 text-white" strokeWidth={1.7} />
            </div>
            <div>
              <div className="font-bold text-[15px] tracking-tight text-[#1a1e1a]">
                ForestWatch
              </div>
              <div className="text-[10px] tracking-[0.2em] uppercase text-[#7b827b]" data-testid="app-subtitle">
                {demo ? "Demonstration" : "Forest intelligence"}
              </div>
            </div>
          </div>
        </div>

        {demo && (
          <div
            className="mx-3 mt-3 px-3 py-2 rounded-md bg-[var(--surface-subtle)] border border-[var(--surface-inset)]"
            data-testid="demo-banner"
          >
            <div className="fw-kicker">ForestWatch Demo</div>
            <p className="text-[11px] text-[var(--text-muted)] mt-1 leading-snug">
              Demonstration data — not a live environmental assessment.
            </p>
          </div>
        )}

        <OrganizationSelector />
        {!demo && <TrialStatusBar />}

        <nav className="flex-1 px-3 py-5 space-y-0.5" data-testid="app-nav">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              data-testid={item.testId}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors ${
                  isActive
                    ? "bg-[#eaece6] text-[#1a1e1a] font-semibold"
                    : "text-[#4a524a] hover:bg-[#f4f5f2]"
                }`
              }
            >
              <item.icon className="w-4 h-4" strokeWidth={1.6} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="px-4 py-4 border-t border-[#eaece6]">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-full bg-[#eaece6] flex items-center justify-center text-[#2d5a27] font-semibold text-sm">
              {user?.name?.[0]?.toUpperCase() || "U"}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-[#1a1e1a] truncate" data-testid="user-name">
                {user?.name}
              </div>
              <div className="text-xs text-[#7b827b] truncate">{user?.email}</div>
            </div>
          </div>
          <Button
            data-testid="logout-btn"
            onClick={handleLogout}
            variant="outline"
            className="w-full justify-start gap-2 border-[#eaece6] hover:bg-[#f4f5f2]"
          >
            <LogOut className="w-4 h-4" strokeWidth={1.6} />
            {demo ? "Leave demo" : "Sign out"}
          </Button>
        </div>
      </aside>

      <div className="md:hidden fixed top-0 left-0 right-0 z-40 bg-white border-b border-[#eaece6] px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-[#2d5a27] flex items-center justify-center">
            <Trees className="w-4 h-4 text-white" strokeWidth={1.7} />
          </div>
          <span className="font-bold text-sm">ForestWatch</span>
          {demo && (
            <span className="text-[10px] uppercase tracking-wider font-bold text-[var(--text-muted)]">
              Demo
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            data-testid="mobile-nav-toggle"
            onClick={() => setMobileOpen((open) => !open)}
            className="text-[#4a524a]"
            aria-label="Open navigation"
          >
            {mobileOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
          </button>
          <button
            data-testid="mobile-logout-btn"
            onClick={handleLogout}
            className="text-sm text-[#4a524a]"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>

      {mobileOpen && (
        <div
          className="md:hidden fixed inset-0 top-12 z-30 bg-white/95 p-4"
          data-testid="mobile-nav"
        >
          <nav className="space-y-1">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMobileOpen(false)}
                className="flex items-center gap-3 px-3 py-3 rounded-md text-sm text-[#4a524a] hover:bg-[#f4f5f2]"
              >
                <item.icon className="w-4 h-4" />
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      )}

      <main className="flex-1 md:pt-0 pt-14 min-w-0">{children}</main>
    </div>
  );
}
