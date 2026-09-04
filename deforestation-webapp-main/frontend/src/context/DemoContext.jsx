import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  consumeDemoInvestigation,
  fetchDemoStatus,
  openDemoScenario,
  recordDemoEvent,
  resetDemoSession,
  setDemoGuideStep,
  simulateDemoAlert,
} from "@/api/demo";
import { useAuth } from "@/context/AuthContext";
import { budgetErrorMessage, isDemoUser } from "@/lib/demo";

const DemoContext = createContext({
  isDemo: false,
  status: null,
  loading: false,
  lastSimulation: null,
  conversion: null,
  exhaustedMessage: null,
  openedInvestigationEventId: null,
  resetDemo: async () => {},
  setGuideStep: async () => {},
  openScenario: async () => {},
  investigate: async () => ({ ok: false }),
  simulateAlert: async () => ({ ok: false }),
  recordEvent: async () => {},
  setConversion: () => {},
  clearConversion: () => {},
});

export function DemoProvider({ children }) {
  const { user } = useAuth();
  const isDemo = isDemoUser(user);
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [lastSimulation, setLastSimulation] = useState(null);
  const [conversion, setConversion] = useState(null);
  const [exhaustedMessage, setExhaustedMessage] = useState(null);
  const [openedInvestigationEventId, setOpenedInvestigationEventId] = useState(null);

  const refresh = useCallback(async () => {
    if (!isDemo) {
      setStatus(null);
      return null;
    }
    setLoading(true);
    try {
      const next = await fetchDemoStatus();
      setStatus(next);
      if (next?.budget?.exhausted) {
        setExhaustedMessage(
          "You've explored the ForestWatch intelligence engine. Create an organization to continue monitoring your own forests."
        );
        setConversion("exhausted");
      }
      return next;
    } catch {
      return null;
    } finally {
      setLoading(false);
    }
  }, [isDemo]);

  useEffect(() => {
    if (!isDemo) {
      setStatus(null);
      setLastSimulation(null);
      setConversion(null);
      setExhaustedMessage(null);
      setOpenedInvestigationEventId(null);
      return;
    }
    refresh();
  }, [isDemo, refresh, user?.id]);

  const applyStatus = useCallback((next, extras = {}) => {
    if (next?.demo) {
      setStatus(next.demo);
      if (next.demo.budget?.exhausted) {
        setExhaustedMessage(
          "You've explored the ForestWatch intelligence engine. Create an organization to continue monitoring your own forests."
        );
        setConversion("exhausted");
      }
    } else if (next?.budget) {
      setStatus(next);
    }
    return { ...next, ...extras };
  }, []);

  const resetDemo = useCallback(async () => {
    const next = await resetDemoSession();
    setLastSimulation(null);
    setConversion(null);
    setExhaustedMessage(null);
    setOpenedInvestigationEventId(null);
    setStatus(next);
    return next;
  }, []);

  const setGuideStep = useCallback(async (stepId) => {
    const next = await setDemoGuideStep(stepId);
    setStatus(next);
    return next;
  }, []);

  const openScenario = useCallback(async (scenarioId) => {
    const next = await openDemoScenario(scenarioId);
    setStatus(next);
    return next;
  }, []);

  const investigate = useCallback(
    async (eventId) => {
      try {
        const next = await consumeDemoInvestigation(eventId);
        applyStatus(next);
        setOpenedInvestigationEventId(eventId || null);
        return { ok: true, data: next };
      } catch (err) {
        const message = budgetErrorMessage(err);
        if (err?.response?.data?.code === "demo_budget_exhausted") {
          setExhaustedMessage(message);
          setConversion("exhausted");
        }
        return { ok: false, error: message, code: err?.response?.data?.code };
      }
    },
    [applyStatus]
  );

  const simulateAlert = useCallback(
    async (eventId) => {
      try {
        const next = await simulateDemoAlert(eventId);
        applyStatus(next);
        setLastSimulation(next);
        setConversion("alert");
        return { ok: true, data: next };
      } catch (err) {
        const message = budgetErrorMessage(err);
        if (err?.response?.data?.code === "demo_budget_exhausted") {
          setExhaustedMessage(message);
          setConversion("exhausted");
        }
        return { ok: false, error: message, code: err?.response?.data?.code };
      }
    },
    [applyStatus]
  );

  const recordEvent = useCallback(async (eventName, detail) => {
    try {
      await recordDemoEvent(eventName, detail);
    } catch {
      // Product telemetry must never block the demonstration.
    }
  }, []);

  const value = useMemo(
    () => ({
      isDemo,
      status,
      loading,
      lastSimulation,
      conversion,
      exhaustedMessage,
      openedInvestigationEventId,
      resetDemo,
      setGuideStep,
      openScenario,
      investigate,
      simulateAlert,
      recordEvent,
      setConversion,
      clearConversion: () => setConversion(null),
      refresh,
    }),
    [
      isDemo,
      status,
      loading,
      lastSimulation,
      conversion,
      exhaustedMessage,
      openedInvestigationEventId,
      resetDemo,
      setGuideStep,
      openScenario,
      investigate,
      simulateAlert,
      recordEvent,
      refresh,
    ]
  );

  return <DemoContext.Provider value={value}>{children}</DemoContext.Provider>;
}

export function useDemo() {
  return useContext(DemoContext);
}
