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
      <div className="glass-card auth-card skeleton animate-rise">
        Loading models…
      </div>
    );
  }

  if (error || !models) {
    return (
      <div className="glass-card auth-card animate-rise">
        <p className="dropzone-error">Failed to load models</p>
        <div className="dropzone-actions">
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="dropzone-button"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (models.length === 0) {
    return (
      <div className="glass-card auth-card animate-rise">
        <p className="section-label">No models available</p>
        <div className="dropzone-actions">
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="dropzone-button"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <Tabs value={value} onValueChange={onValueChange} className="animate-rise">
      <TabsList>
        {models.map((model) => (
          <TabsTrigger key={model.id} value={model.id}>
            {model.name}
          </TabsTrigger>
        ))}
      </TabsList>
      {models.map((model) => (
        <TabsContent key={model.id} value={model.id}>
          <p className="section-label">{model.name}</p>
          <p className="lede">{model.description}</p>
        </TabsContent>
      ))}
    </Tabs>
  );
}
