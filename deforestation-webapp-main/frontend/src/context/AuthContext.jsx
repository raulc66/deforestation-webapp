import { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api, formatApiErrorDetail } from "@/lib/api";
import { startDemoSession } from "@/api/demo";
import {
  clearClientWorkspaceState,
  isSignOutRequiredDemoError,
} from "@/lib/sessionState";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  // user: null = checking, false = unauthenticated, object = authenticated
  const [user, setUser] = useState(null);

  const refreshUser = useCallback(async () => {
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
      return data;
    } catch {
      clearClientWorkspaceState();
      setUser(false);
      return null;
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } catch {
      // Cookie clear may still have been applied; drop client state either way.
    }
    clearClientWorkspaceState();
    setUser(false);
  };

  const login = async (email, password) => {
    try {
      clearClientWorkspaceState();
      const { data } = await api.post("/auth/login", { email, password });
      setUser(data);
      return { ok: true, user: data };
    } catch (e) {
      return { ok: false, error: formatApiErrorDetail(e.response?.data?.detail) || e.message };
    }
  };

  const register = async ({ email, password, name }) => {
    try {
      clearClientWorkspaceState();
      const { data } = await api.post("/auth/register", { email, password, name });
      setUser(data);
      return { ok: true, user: data };
    } catch (e) {
      return { ok: false, error: formatApiErrorDetail(e.response?.data?.detail) || e.message };
    }
  };

  const startDemo = async () => {
    const attempt = async () => startDemoSession();
    try {
      clearClientWorkspaceState();
      const data = await attempt();
      setUser(data);
      return { ok: true, user: data };
    } catch (e) {
      if (isSignOutRequiredDemoError(e)) {
        await logout();
        try {
          const data = await attempt();
          setUser(data);
          return { ok: true, user: data };
        } catch (retryErr) {
          return {
            ok: false,
            error: isSignOutRequiredDemoError(retryErr)
              ? "The demonstration could not be started. Refresh the page and try again."
              : formatApiErrorDetail(retryErr.response?.data?.detail) ||
                retryErr.message,
          };
        }
      }
      return { ok: false, error: formatApiErrorDetail(e.response?.data?.detail) || e.message };
    }
  };

  return (
    <AuthContext.Provider value={{ user, login, register, logout, refreshUser, startDemo }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
