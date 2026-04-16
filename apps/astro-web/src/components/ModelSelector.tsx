import { useEffect } from "react";
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
  const panelClass =
    "min-h-[12rem] rounded-[4px] border border-border bg-card p-6 sm:p-8";
  const actionClass =
    "inline-flex min-h-11 items-center justify-center rounded-[4px] border border-[var(--color-opencode-border-outline)] px-5 py-1 text-sm font-medium text-foreground transition-[border-color,background-color,color] duration-150 hover:border-[var(--color-opencode-accent-blue)] hover:bg-white/5";

  const {
    data: models,
    error,
    isLoading,
  } = useSWR<ModelRead[]>("/model/", () => api.getModels());

  useEffect(() => {
    if (!value && models?.[0]) {
      onValueChange(models[0].id);
    }
  }, [models, onValueChange, value]);

  if (isLoading) {
    return (
      <div className={panelClass} aria-busy="true">
        <div className="flex h-full flex-col gap-4">
          <div
            aria-hidden="true"
            className="bg-muted h-4 w-32 animate-pulse rounded-[4px]"
          />
          <div
            aria-hidden="true"
            className="bg-muted h-12 w-full animate-pulse rounded-[4px]"
          />
          <div
            aria-hidden="true"
            className="bg-muted h-16 w-full animate-pulse rounded-[4px]"
          />
        </div>
      </div>
    );
  }

  if (error || !models) {
    return (
      <div className={panelClass}>
        <p className="text-sm leading-[1.5] font-medium text-[var(--color-opencode-danger)]">
          Failed to load models
        </p>
        <div className="mt-4">
          <button
            type="button"
            onClick={() => window.location.reload()}
            className={actionClass}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (models.length === 0) {
    return (
      <div className={panelClass}>
        <p className="text-muted-foreground text-sm leading-none font-bold tracking-[0.05em] uppercase">
          No models available
        </p>
        <div className="mt-4">
          <button
            type="button"
            onClick={() => window.location.reload()}
            className={actionClass}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const firstModel = models[0];

  if (!firstModel) {
    return null;
  }

  const resolvedValue = value || firstModel.id;

  return (
    <div className={panelClass}>
      <div className="mb-6">
        <p className="text-muted-foreground text-sm leading-none font-bold tracking-[0.05em] uppercase">
          Model selection
        </p>
        <p className="text-muted-foreground mt-2 max-w-[48ch] text-base leading-[1.5]">
          Default PyTorch workflow now targets chest X-ray pneumonia
          classification instead of skin lesion analysis.
        </p>
      </div>

      <Tabs
        value={resolvedValue}
        onValueChange={onValueChange}
        className="gap-4"
      >
        <TabsList className="w-full overflow-x-auto overflow-y-hidden whitespace-nowrap">
          {models.map((model) => (
            <TabsTrigger key={model.id} value={model.id} className="shrink-0">
              {model.name}
            </TabsTrigger>
          ))}
        </TabsList>
        {models.map((model) => (
          <TabsContent key={model.id} value={model.id} className="pt-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-muted-foreground text-sm leading-none font-bold tracking-[0.05em] uppercase">
                {model.name}
              </p>
              <span className="text-muted-foreground text-xs leading-none font-medium tracking-[0.08em] uppercase">
                v{model.version}
              </span>
            </div>
            <p className="text-muted-foreground mt-2 max-w-[56ch] text-[0.9375rem] leading-[1.5]">
              {model.description}
            </p>
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
