import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import SalesPage from "@/pages/SalesPage";
import { isDemoUser } from "@/lib/demo";

export default function HomeRoute() {
  const { user } = useAuth();
  if (user === null) {
    return (
      <div data-testid="auth-loading" className="flex items-center justify-center min-h-screen bg-[var(--bg-default,#f4f5f2)]">
        <div className="text-sm tracking-[0.2em] uppercase text-[#7b827b]">Loading</div>
      </div>
    );
  }
  // Returning operators keep Command Center. Visitors see the commercial page.
  // A leftover demo cookie is not an operator session and must not enter /dashboard.
  // Interactive demo remains at /explore and requires an explicit Start/Continue/Restart.
  if (user && !isDemoUser(user)) return <Navigate to="/dashboard" replace />;
  return <SalesPage />;
}
