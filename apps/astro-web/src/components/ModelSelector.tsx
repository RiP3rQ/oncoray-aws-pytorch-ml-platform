import { useEffect } from "react";
import useSWR from "swr";
import * as api from "@/lib/api";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import type { ModelRead, ModelSlug, PredictionMode } from "@/lib/api";

interface ModelSelectorProps {
  value: PredictionMode | "";
  onValueChange: (mode: PredictionMode) => void;
}

const MODEL_ORDER: ModelSlug[] = ["effnetb0", "vitb16"];
const COMPARE_MODE: PredictionMode = "both";

function sortModels(models: ModelRead[]): ModelRead[] {
  const order = new Map(MODEL_ORDER.map((slug, index) => [slug, index]));
  return [...models].sort((left, right) => {
    return (order.get(left.slug) ?? 99) - (order.get(right.slug) ?? 99);
  });
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
  const sortedModels = models ? sortModels(models) : [];
  const hasCompareMode =
    sortedModels.some((model) => model.slug === "effnetb0") &&
    sortedModels.some((model) => model.slug === "vitb16");

  useEffect(() => {
    if (!value && sortedModels[0]) {
      onValueChange(sortedModels[0].slug);
    }
  }, [onValueChange, sortedModels, value]);

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

  if (sortedModels.length === 0) {
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

  const firstModel = sortedModels[0];

  if (!firstModel) {
    return null;
  }

  const resolvedValue = value || firstModel.slug;

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
        onValueChange={(nextValue) =>
          onValueChange(nextValue as PredictionMode)
        }
        className="gap-4"
      >
        <TabsList className="w-full overflow-x-auto overflow-y-hidden whitespace-nowrap">
          {sortedModels.map((model) => (
            <TabsTrigger key={model.id} value={model.slug} className="shrink-0">
              {model.name}
            </TabsTrigger>
          ))}
          {hasCompareMode ? (
            <TabsTrigger value={COMPARE_MODE} className="shrink-0">
              Compare both
            </TabsTrigger>
          ) : null}
        </TabsList>
        {sortedModels.map((model) => (
          <TabsContent key={model.id} value={model.slug} className="pt-4">
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
        {hasCompareMode ? (
          <TabsContent value={COMPARE_MODE} className="pt-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-muted-foreground text-sm leading-none font-bold tracking-[0.05em] uppercase">
                Compare both
              </p>
              <span className="text-muted-foreground text-xs leading-none font-medium tracking-[0.08em] uppercase">
                one upload, two results
              </span>
            </div>
            <p className="text-muted-foreground mt-2 max-w-[56ch] text-[0.9375rem] leading-[1.5]">
              Run EffNetB0 and ViTB16 against the exact same chest X-ray so the
              frontend can compare their outputs side by side.
            </p>
          </TabsContent>
        ) : null}
      </Tabs>
    </div>
  );
}
