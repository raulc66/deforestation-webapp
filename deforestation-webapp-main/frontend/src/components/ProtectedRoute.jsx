import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

export default function ProtectedRoute({ children }) {
  const { user } = useAuth();
  if (user === null) {
    return (
      <div
        data-testid="auth-loading"
        className="flex items-center justify-center min-h-screen"
      >
        <div className="text-sm tracking-[0.2em] uppercase text-[#7b827b]">
          Loading
        </div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  return children;
}
