import useSWR from "swr";
import * as api from "@/lib/api";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import type { ModelRead } from "@/lib/api";

interface ModelSelectorProps {
  value: string;
  onValueChange: (modelId: string) => void;
}

export default function ModelSelector({
  value,
  onValueChange,
}: ModelSelectorProps) {
  const {
    data: models,
    error,
    isLoading,
  } = useSWR<ModelRead[]>("/model/", () => api.getModels());

  if (isLoading) {
    return (
      <div
        className="glass-card"
        style={{ padding: "24px", textAlign: "center" }}
      >
        <p
          style={{
            color: "var(--muted)",
            letterSpacing: "0.15em",
            textTransform: "uppercase",
            fontSize: "0.76rem",
          }}
        >
          Loading models…
        </p>
      </div>
    );
  }

  if (error || !models) {
    return (
      <div
        className="glass-card"
        style={{ padding: "24px", textAlign: "center" }}
      >
        <p style={{ color: "#f87171" }}>Failed to load models</p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          style={{
            marginTop: "12px",
            padding: "10px 18px",
            borderRadius: "999px",
            border: "1px solid var(--line)",
            background: "rgba(255,255,255,0.04)",
            color: "var(--text)",
            cursor: "pointer",
          }}
        >
          Retry
        </button>
      </div>
    );
  }

  if (models.length === 0) {
    return (
      <div
        className="glass-card"
        style={{ padding: "24px", textAlign: "center" }}
      >
        <p style={{ color: "var(--muted)" }}>No models available</p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          style={{
            marginTop: "12px",
            padding: "10px 18px",
            borderRadius: "999px",
            border: "1px solid var(--line)",
            background: "rgba(255,255,255,0.04)",
            color: "var(--text)",
            cursor: "pointer",
          }}
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <Tabs value={value} onValueChange={onValueChange}>
      <TabsList>
        {models.map((model) => (
          <TabsTrigger key={model.id} value={model.id}>
            {model.name}
          </TabsTrigger>
        ))}
      </TabsList>
      {models.map((model) => (
        <TabsContent key={model.id} value={model.id}>
          <p
            style={{
              color: "var(--muted)",
              fontSize: "0.9rem",
              lineHeight: "1.6",
              marginTop: "8px",
            }}
          >
            {model.description}
          </p>
        </TabsContent>
      ))}
    </Tabs>
  );
}
