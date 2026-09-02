import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { DemoProvider } from "@/context/DemoContext";
import ProtectedRoute from "@/components/ProtectedRoute";
import LoginPage from "@/pages/LoginPage";
import RegisterPage from "@/pages/RegisterPage";
import ExplorePage from "@/pages/ExplorePage";
import SalesPage from "@/pages/SalesPage";
import DashboardPage from "@/pages/DashboardPage";
import MapPage from "@/pages/MapPage";
import ModulesPage from "@/pages/ModulesPage";
import ReportsPage from "@/pages/ReportsPage";
import InvestigationsPage from "@/pages/InvestigationsPage";
import AlertsPage from "@/pages/AlertsPage";
import BillingPage from "@/pages/BillingPage";
import { OrganizationProvider } from "@/context/OrganizationContext";
import { TrialProvider } from "@/context/TrialContext";
import TrialSetupPage from "@/pages/TrialSetupPage";

function OrganizationProviderWrapper({ children }) {
  return <OrganizationProvider>{children}</OrganizationProvider>;
}

function HomeRoute() {
  const { user } = useAuth();
  if (user === null) {
    return (
      <div data-testid="auth-loading" className="flex items-center justify-center min-h-screen">
        <div className="text-sm tracking-[0.2em] uppercase text-[#7b827b]">Loading</div>
      </div>
    );
  }
  // Returning operators keep Command Center. Visitors see the commercial page.
  // Interactive demo remains at /explore.
  if (user) return <Navigate to="/dashboard" replace />;
  return <SalesPage />;
}

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <OrganizationProviderWrapper>
          <DemoProvider>
          <TrialProvider>
          <Toaster position="top-right" richColors />
          <Routes>
            <Route path="/" element={<HomeRoute />} />
            <Route path="/explore" element={<ExplorePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <DashboardPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/map"
              element={
                <ProtectedRoute>
                  <MapPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/modules"
              element={
                <ProtectedRoute>
                  <ModulesPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/reports"
              element={
                <ProtectedRoute>
                  <ReportsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/alerts"
              element={
                <ProtectedRoute>
                  <AlertsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/billing"
              element={
                <ProtectedRoute>
                  <BillingPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/investigations"
              element={
                <ProtectedRoute>
                  <InvestigationsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/investigations/:id"
              element={
                <ProtectedRoute>
                  <InvestigationsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/trial/setup"
              element={
                <ProtectedRoute>
                  <TrialSetupPage />
                </ProtectedRoute>
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          </TrialProvider>
          </DemoProvider>
          </OrganizationProviderWrapper>
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

export default App;
