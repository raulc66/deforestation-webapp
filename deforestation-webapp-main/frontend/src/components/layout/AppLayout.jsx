import { NavLink, useNavigate } from "react-router-dom";
import { LayoutDashboard, Map, Trees, LogOut, BoxSelect } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, testId: "nav-dashboard" },
  { to: "/map", label: "Live Map", icon: Map, testId: "nav-map" },
  { to: "/modules", label: "Modules", icon: BoxSelect, testId: "nav-modules" },
];

export default function AppLayout({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen flex bg-[#f4f5f2]">
      {/* Sidebar */}
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
              <div className="text-[10px] tracking-[0.2em] uppercase text-[#7b827b]">
                Monitoring v0.1
              </div>
            </div>
          </div>
        </div>

        <nav className="flex-1 px-3 py-5 space-y-0.5">
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
            Sign out
          </Button>
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-40 bg-white border-b border-[#eaece6] px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-[#2d5a27] flex items-center justify-center">
            <Trees className="w-4 h-4 text-white" strokeWidth={1.7} />
          </div>
          <span className="font-bold text-sm">ForestWatch</span>
        </div>
        <button
          data-testid="mobile-logout-btn"
          onClick={handleLogout}
          className="text-sm text-[#4a524a]"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>

      <main className="flex-1 md:pt-0 pt-14 min-w-0">{children}</main>
    </div>
  );
}
