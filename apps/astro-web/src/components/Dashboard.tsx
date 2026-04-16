import { useState } from "react";
import { AuthProvider } from "@/hooks/useAuth";
import AuthGuard from "@/components/AuthGuard";
import ModelSelector from "@/components/ModelSelector";
import ImageDropzone from "@/components/ImageDropzone";
import PredictionResult from "@/components/PredictionResult";
import { useAuthContext } from "@/lib/auth";
import type { PredictionResponse } from "@/lib/api";

export default function Dashboard() {
  return (
    <AuthProvider>
      <DashboardInner />
    </AuthProvider>
  );
}

function DashboardInner() {
  const { user, logout } = useAuthContext();
  const [selectedModelId, setSelectedModelId] = useState("");
  const [prediction, setPrediction] = useState<PredictionResponse | null>(null);

  return (
    <AuthGuard>
      <div className="page-shell">
        <div className="frame app-frame">
          <header className="topbar flat-card animate-rise">
            <div>
              <p className="brand">OncoRay</p>
              <p className="topnote">
                Default workflow: chest X-ray pneumonia classification
              </p>
            </div>
            <nav className="flex items-center gap-4">
              <span className="text-sm text-[var(--muted)]">{user?.email}</span>
              <button
                type="button"
                onClick={logout}
                className="rounded border border-[var(--color-opencode-border-outline)] bg-transparent px-5 py-1 font-mono text-sm leading-[2] font-medium text-[var(--color-opencode-mid-gray)] transition-colors duration-[var(--duration-fast)] hover:border-[var(--color-opencode-accent-blue)] hover:text-[var(--color-opencode-light)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-opencode-accent-blue)]"
              >
                Log out
              </button>
            </nav>
          </header>

          <section className="animate-rise delay-1">
            <ModelSelector
              value={selectedModelId}
              onValueChange={setSelectedModelId}
            />
          </section>

          <section className="animate-rise delay-2">
            <ImageDropzone
              modelId={selectedModelId}
              onPrediction={setPrediction}
            />
          </section>

          <PredictionResult prediction={prediction} />
        </div>
      </div>
    </AuthGuard>
  );
}
