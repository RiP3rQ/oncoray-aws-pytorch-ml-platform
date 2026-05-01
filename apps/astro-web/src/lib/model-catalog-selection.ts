import type { ModelRead, ModelSlug, PredictionMode } from "./api";

export const MODEL_ORDER: ModelSlug[] = ["effnetb0", "vitb16"];
export const COMPARE_MODE: PredictionMode = "both";
export const COMPARE_REQUIRED_MODEL_SLUGS: ModelSlug[] = ["effnetb0", "vitb16"];

export interface ModelCatalogSelection {
  models: ModelRead[];
  hasCompareMode: boolean;
  resolvedMode: PredictionMode | "";
  modeToApply: PredictionMode | null;
}

export function sortModelCatalog(models: ModelRead[]): ModelRead[] {
  const order = new Map(MODEL_ORDER.map((slug, index) => [slug, index]));

  return [...models].sort((left, right) => {
    return (order.get(left.slug) ?? 99) - (order.get(right.slug) ?? 99);
  });
}

export function createModelCatalogSelection(
  models: ModelRead[],
  currentMode: PredictionMode | "",
): ModelCatalogSelection {
  const sortedModels = sortModelCatalog(models);
  const availableSlugs = new Set(sortedModels.map((model) => model.slug));
  const hasCompareMode = COMPARE_REQUIRED_MODEL_SLUGS.every((slug) =>
    availableSlugs.has(slug),
  );
  const validModes = new Set<PredictionMode>([
    ...sortedModels.map((model) => model.slug),
    ...(hasCompareMode ? [COMPARE_MODE] : []),
  ]);
  const resolvedMode =
    currentMode && validModes.has(currentMode)
      ? currentMode
      : (sortedModels[0]?.slug ?? "");
  const modeToApply =
    resolvedMode && resolvedMode !== currentMode ? resolvedMode : null;

  return {
    models: sortedModels,
    hasCompareMode,
    resolvedMode,
    modeToApply,
  };
}
