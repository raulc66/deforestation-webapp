import { useEffect, useState } from "react";
import AppLayout from "@/components/layout/AppLayout";
import { api } from "@/lib/api";

export default function ModulesPage() {
  const [modules, setModules] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get("/modules")
      .then((r) => setModules(r.data))
      .finally(() => setLoading(false));
  }, []);

  return (
    <AppLayout>
      <div className="bg-grain min-h-screen">
        <div
          className="max-w-7xl mx-auto px-6 lg:px-10 py-10"
          data-testid="modules-page"
        >
          <div className="label-eyebrow mb-3">Architecture</div>
          <h1 className="text-4xl font-bold tracking-tight mb-2">
            Platform modules
          </h1>
          <p className="text-[#4a524a] max-w-2xl mb-10">
            Each module is independently extensible — implemented behind a stable
            interface so you can swap providers, add sources, or scale workers
            without rewriting the platform.
          </p>

          {loading && <div className="text-[#7b827b] text-sm">Loading…</div>}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {modules.map((m) => (
              <div
                key={m.name}
                className="card-flat"
                data-testid={`module-detail-${m.name}`}
              >
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-lg font-semibold tracking-tight capitalize">
                    {m.name.replace("_", " ")}
                  </h3>
                  <span className="text-[9px] tracking-[0.22em] uppercase font-bold text-[#c84b31] bg-[#c84b31]/10 px-2 py-1 rounded">
                    {m.status}
                  </span>
                </div>
                <p className="text-sm text-[#4a524a] mb-4 leading-relaxed">
                  {m.description}
                </p>
                <div className="label-eyebrow mb-2">Planned capabilities</div>
                <ul className="space-y-1.5">
                  {m.planned_capabilities?.map((c) => (
                    <li
                      key={c}
                      className="text-sm text-[#1a1e1a] flex items-start gap-2"
                    >
                      <span className="mt-1.5 w-1 h-1 rounded-full bg-[#2d5a27]" />
                      {c}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppLayout>
  );
}
