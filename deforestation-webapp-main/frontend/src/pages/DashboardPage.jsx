import AppLayout from "@/components/layout/AppLayout";
import IntelligenceSection from "@/components/intelligence/IntelligenceSection";
import { useAuth } from "@/context/AuthContext";
import { useDemo } from "@/context/DemoContext";
import { useOrganization } from "@/context/OrganizationContext";
import { useTrial } from "@/context/TrialContext";
import DemoBudgetBar from "@/components/demo/DemoBudgetBar";
import DemoGuideRail from "@/components/demo/DemoGuideRail";
import DemoScenarioSwitcher from "@/components/demo/DemoScenarioSwitcher";
import DemoConversionCta from "@/components/demo/DemoConversionCta";
import TrialOnboarding from "@/components/trial/TrialOnboarding";
import TrialConversionCta from "@/components/trial/TrialConversionCta";
import { isDemoUser } from "@/lib/demo";

export default function DashboardPage() {
  const { user } = useAuth();
  const demo = useDemo();
  const isDemo = demo.isDemo || isDemoUser(user);

  if (isDemo) {
    return <DemoDashboard demo={demo} />;
  }

  return <OperatorDashboard />;
}

function DemoDashboard({ demo }) {
  const { status, conversion, exhaustedMessage, resetDemo, setGuideStep, openScenario, recordEvent } = demo;

  return (
    <AppLayout>
      <div className="bg-grain min-h-screen">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-10 py-6 lg:py-10" data-testid="dashboard-page">
          <div className="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-4 mb-6">
            <div>
              <div className="fw-kicker mb-2">ForestWatch Demo</div>
              <h1 className="text-3xl lg:text-4xl font-bold tracking-tight">
                Prioritized forest intelligence
              </h1>
              <p className="text-[#4a524a] mt-2 max-w-xl text-sm leading-relaxed">
                You are watching demonstration forests in Romania. Open the queue,
                investigate a disturbance, review evidence, then simulate an alert.
              </p>
            </div>
            <button
              type="button"
              onClick={() => resetDemo()}
              className="text-sm font-semibold text-[var(--accent)] hover:underline self-start"
              data-testid="demo-reset"
            >
              Reset demonstration
            </button>
          </div>

          <div className="mb-4">
            <DemoBudgetBar status={status} />
          </div>

          {exhaustedMessage && (
            <div
              className="mb-5 px-4 py-3 rounded-md border border-[var(--signal)]/30 bg-[var(--signal)]/5 text-sm text-[var(--signal-strong)]"
              data-testid="demo-budget-exhausted"
              role="status"
            >
              {exhaustedMessage}
            </div>
          )}

          <div className="grid grid-cols-1 xl:grid-cols-4 gap-5 mb-8">
            <div className="xl:col-span-1 space-y-4">
              <DemoGuideRail
                guide={status?.guide ?? []}
                currentStep={status?.guide_step}
                onSelect={setGuideStep}
              />
              <DemoScenarioSwitcher
                scenarios={status?.scenarios ?? []}
                focused={status?.focused_scenario}
                onSelect={openScenario}
              />
              {conversion && (
                <DemoConversionCta
                  moment={conversion}
                  onClick={() => recordEvent("conversion_cta_clicked", { moment: conversion })}
                />
              )}
            </div>
            <div className="xl:col-span-3 min-w-0">
              <IntelligenceSection />
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

function OperatorDashboard() {
  const { status, isTrial, isExpired } = useTrial();
  const { currentOrganization } = useOrganization();
  const organizationName = currentOrganization?.name || "Your organization";

  return (
    <AppLayout>
      <div className="bg-grain min-h-screen">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-10 py-6 lg:py-10" data-testid="dashboard-page">
          <div className="mb-6">
            <div className="fw-kicker mb-2">Command Center</div>
            <h1 className="text-3xl lg:text-4xl font-bold tracking-tight" data-testid="operator-org-name">
              {organizationName}
            </h1>
            <p className="text-[#4a524a] mt-2 max-w-xl text-sm leading-relaxed">
              Prioritized intelligence for forests this organization monitors.
              Review evidence before acting — satellite disturbance is not a legal finding.
            </p>
            {isTrial && (
              <p
                className="text-xs text-[var(--text-muted)] mt-2 max-w-xl leading-relaxed"
                data-testid="trial-workspace-kicker"
              >
                Trial workspace for your organization — not demonstration data.
              </p>
            )}
          </div>
          <TrialOnboarding status={status} />
          {isExpired && <TrialConversionCta moment="expired" />}
          <IntelligenceSection />
        </div>
      </div>
    </AppLayout>
  );
}
