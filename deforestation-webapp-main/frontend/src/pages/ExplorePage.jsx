import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Trees, ArrowRight, MapPin, ShieldQuestion } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { useDemo } from "@/context/DemoContext";
import { isDemoUser } from "@/lib/demo";
import SurfaceCard from "@/components/product/SurfaceCard";
import StatusBadge from "@/components/product/StatusBadge";

const STEPS = [
  "Watch forests you care about",
  "See what changed",
  "Know what deserves attention",
  "Review evidence before acting",
];

export default function ExplorePage() {
  const { user, startDemo } = useAuth();
  const demo = useDemo();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const signedIn = user && typeof user === "object";
  const demoSession = isDemoUser(user);
  const remainingInvestigations = demo.status?.budget?.remaining?.investigation;
  const sessionKnown = Boolean(demo.status?.budget);
  const investigationExhausted =
    Boolean(demo.status?.budget?.exhausted) || remainingInvestigations === 0;
  const canResume = demoSession && sessionKnown && !investigationExhausted;

  const onStart = async () => {
    setError("");
    setLoading(true);
    const res = await startDemo();
    if (res.ok) {
      try {
        await demo.refresh?.();
      } catch {
        // Server session is already fresh; dashboard will reload status.
      }
      setLoading(false);
      navigate("/dashboard", { replace: true });
    } else {
      setLoading(false);
      setError(res.error || "The demonstration could not be started.");
    }
  };

  return (
    <div className="min-h-screen bg-[var(--surface-subtle)]" data-testid="explore-page">
      <header className="border-b border-[var(--surface-inset)] bg-white">
        <div className="max-w-5xl mx-auto px-5 py-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-md bg-[var(--accent-strong)] flex items-center justify-center">
              <Trees className="w-4 h-4 text-white" strokeWidth={1.7} />
            </div>
            <div>
              <div className="font-bold text-sm tracking-tight text-[var(--text-primary)]">
                ForestWatch
              </div>
              <div className="text-[10px] tracking-[0.18em] uppercase text-[var(--text-muted)]">
                Environmental intelligence
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3 text-sm">
            {signedIn ? (
              <Link
                to="/dashboard"
                className="font-semibold text-[var(--accent)] hover:underline"
                data-testid="explore-continue"
              >
                Continue
              </Link>
            ) : (
              <Link
                to="/login"
                className="text-[var(--text-secondary)] hover:underline"
                data-testid="explore-signin"
              >
                Sign in
              </Link>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-5 py-10 md:py-14">
        <div className="fw-kicker mb-3">Explore ForestWatch</div>
        <h1 className="text-3xl md:text-4xl font-bold tracking-tight text-[var(--text-primary)] max-w-2xl leading-tight">
          See how ForestWatch turns environmental observations into prioritized forest intelligence.
        </h1>
        <p className="mt-4 max-w-xl text-[var(--text-secondary)] leading-relaxed">
          ForestWatch continuously watches forests, identifies meaningful disturbances,
          provides contextual evidence, prioritizes what requires attention, and can notify
          the organization.
        </p>

        <div className="mt-8 flex flex-col sm:flex-row gap-3">
          {demoSession && !sessionKnown ? (
            <button
              type="button"
              disabled
              className="fw-button-primary"
              data-testid="explore-demo-loading"
            >
              Preparing demonstration…
            </button>
          ) : canResume ? (
            <>
              <button
                type="button"
                onClick={() => navigate("/dashboard")}
                className="fw-button-primary"
                data-testid="explore-resume-demo"
              >
                Continue demonstration
                <ArrowRight className="w-4 h-4 ml-2" strokeWidth={1.7} />
              </button>
              <button
                type="button"
                onClick={onStart}
                disabled={loading}
                className="inline-flex items-center justify-center px-4 py-2.5 rounded-md text-sm font-semibold border border-[var(--surface-inset)] bg-white text-[var(--text-primary)] hover:bg-[var(--surface-subtle)]"
                data-testid="explore-restart-demo"
              >
                {loading ? "Preparing demonstration…" : "Restart demonstration"}
              </button>
            </>
          ) : signedIn && !demoSession ? (
            <Link to="/dashboard" className="fw-button-primary" data-testid="explore-go-dashboard">
              Open your workspace
            </Link>
          ) : (
            <button
              type="button"
              onClick={onStart}
              disabled={loading}
              className="fw-button-primary"
              data-testid="start-interactive-demo"
            >
              {loading ? "Preparing demonstration…" : "Start interactive demo"}
              {!loading && <ArrowRight className="w-4 h-4 ml-2" strokeWidth={1.7} />}
            </button>
          )}
          {!signedIn && (
            <Link
              to="/register?from=demo"
              className="inline-flex items-center justify-center px-4 py-2.5 rounded-md text-sm font-semibold border border-[var(--surface-inset)] bg-white text-[var(--text-primary)] hover:bg-[var(--surface-subtle)]"
              data-testid="explore-create-organization"
            >
              Start a 14-day trial
            </Link>
          )}
        </div>

        {error && (
          <p className="mt-4 text-sm text-[var(--signal-strong)]" data-testid="explore-error" role="alert">
            {error}
          </p>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-12">
          <SurfaceCard className="p-5" testId="explore-geography">
            <div className="fw-kicker mb-2 flex items-center gap-1.5">
              <MapPin className="w-3 h-3" /> Geography
            </div>
            <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
              Three Romanian forest stands are already under watch. The map stays central.
            </p>
          </SurfaceCard>
          <SurfaceCard className="p-5" testId="explore-priority">
            <div className="fw-kicker mb-2">Priority</div>
            <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
              Not every observation is urgent. The queue shows what to investigate first.
            </p>
          </SurfaceCard>
          <SurfaceCard className="p-5" testId="explore-evidence">
            <div className="fw-kicker mb-2 flex items-center gap-1.5">
              <ShieldQuestion className="w-3 h-3" /> Evidence
            </div>
            <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
              Observation, inference, and evidence stay separate. Nothing here proves illegal activity.
            </p>
          </SurfaceCard>
        </div>

        <ol className="mt-10 space-y-2" data-testid="explore-value-chain">
          {STEPS.map((step, index) => (
            <li key={step} className="flex items-center gap-3 text-sm text-[var(--text-secondary)]">
              <span className="font-mono text-xs tabular-nums text-[var(--text-muted)] w-5">
                {String(index + 1).padStart(2, "0")}
              </span>
              {step}
            </li>
          ))}
        </ol>

        <div className="mt-10">
          <StatusBadge variant="unknown" label="Demonstration data — not a live assessment" />
        </div>
      </main>
    </div>
  );
}
