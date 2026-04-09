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
          <header className="topbar glass-card animate-rise">
            <div>
              <p className="brand">OncoRay</p>
              <p className="topnote">AI-assisted X-ray cancer screening</p>
            </div>
            <nav className="flex items-center gap-4">
              <span className="text-[var(--muted)] text-sm">{user?.email}</span>
              <button
                type="button"
                onClick={logout}
                className="glass-card rounded-full px-4 py-2 text-sm transition-colors hover:bg-white/8"
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
