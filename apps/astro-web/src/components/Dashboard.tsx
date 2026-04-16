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
            <div className="topbar-brand-block">
              <p className="brand">OncoRay</p>
              <p className="topnote">
                Default workflow: chest X-ray pneumonia classification
              </p>
            </div>
            <nav className="topbar-actions" aria-label="Workspace actions">
              <span className="topbar-email">{user?.email}</span>
              <button type="button" onClick={logout} className="toolbar-button">
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
