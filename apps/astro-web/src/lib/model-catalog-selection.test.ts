import { describe, expect, test } from "bun:test";
import type { ModelRead } from "./api";
import {
  COMPARE_MODE,
  createModelCatalogSelection,
  sortModelCatalog,
} from "./model-catalog-selection";

function model(slug: ModelRead["slug"], name = slug): ModelRead {
  return {
    id: `${slug}-id`,
    slug,
    name,
    description: `${name} classifier`,
    version: "1.0.0",
    created_at: "2026-04-06T18:00:00Z",
    updated_at: "2026-04-06T18:00:00Z",
  };
}

const effnet = model("effnetb0", "EffNetB0");
const vit = model("vitb16", "ViTB16");

describe("Model Catalog selection", () => {
  test("sorts Model Catalog by supported runtime order", () => {
    expect(sortModelCatalog([vit, effnet]).map((item) => item.slug)).toEqual([
      "effnetb0",
      "vitb16",
    ]);
  });

  test("selects first Model Runtime when current mode is empty", () => {
    const selection = createModelCatalogSelection([vit, effnet], "");

    expect(selection).toMatchObject({
      resolvedMode: "effnetb0",
      modeToApply: "effnetb0",
    });
  });

  test("keeps current model mode when Model Catalog still contains it", () => {
    const selection = createModelCatalogSelection([effnet, vit], "vitb16");

    expect(selection).toMatchObject({
      resolvedMode: "vitb16",
      modeToApply: null,
    });
  });

  test("enables compare mode only when both required Model Runtimes exist", () => {
    expect(createModelCatalogSelection([effnet, vit], "").hasCompareMode).toBe(
      true,
    );
    expect(createModelCatalogSelection([effnet], "").hasCompareMode).toBe(
      false,
    );
  });

  test("keeps compare mode when still supported", () => {
    const selection = createModelCatalogSelection([effnet, vit], COMPARE_MODE);

    expect(selection).toMatchObject({
      hasCompareMode: true,
      resolvedMode: COMPARE_MODE,
      modeToApply: null,
    });
  });

  test("repairs stale mode after Model Catalog refresh", () => {
    const selection = createModelCatalogSelection([effnet], "vitb16");

    expect(selection).toMatchObject({
      resolvedMode: "effnetb0",
      modeToApply: "effnetb0",
    });
  });

  test("repairs compare mode when required Model Runtime disappears", () => {
    const selection = createModelCatalogSelection([vit], COMPARE_MODE);

    expect(selection).toMatchObject({
      hasCompareMode: false,
      resolvedMode: "vitb16",
      modeToApply: "vitb16",
    });
  });

  test("keeps empty mode when Model Catalog is empty", () => {
    const selection = createModelCatalogSelection([], "");

    expect(selection).toMatchObject({
      models: [],
      resolvedMode: "",
      modeToApply: null,
    });
  });
});
