import { useState } from "react";
import AuthGuard from "@/components/AuthGuard";
import ModelSelector from "@/components/ModelSelector";
import ImageDropzone from "@/components/ImageDropzone";
import PredictionResult from "@/components/PredictionResult";
import { useAuthContext } from "@/lib/auth";
import type { PredictionResponse } from "@/lib/api";

export default function Dashboard() {
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
            <nav style={{ display: "flex", alignItems: "center", gap: "18px" }}>
              <span style={{ color: "var(--muted)", fontSize: "0.88rem" }}>
                {user?.email}
              </span>
              <button
                type="button"
                onClick={logout}
                style={{
                  padding: "8px 16px",
                  borderRadius: "999px",
                  border: "1px solid var(--line)",
                  background: "rgba(255,255,255,0.04)",
                  color: "var(--text)",
                  cursor: "pointer",
                  fontSize: "0.85rem",
                }}
              >
                Log out
              </button>
            </nav>
          </header>

          <section style={{ marginTop: "28px" }}>
            <ModelSelector
              value={selectedModelId}
              onValueChange={setSelectedModelId}
            />
          </section>

          <section style={{ marginTop: "28px" }}>
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
