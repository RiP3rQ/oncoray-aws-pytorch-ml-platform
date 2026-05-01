import { describe, expect, test } from "bun:test";
import type { Prediction } from "./api";
import {
  createPredictionResultViewModel,
  toneForConfidence,
} from "./prediction-result-view-model";

const singlePrediction: Prediction = {
  request_id: "request-1",
  mode: "effnetb0",
  upload: { status: "ok", image_s3_key: "uploads/scan-a.png" },
  results: {
    effnetb0: {
      status: "ok",
      prediction: "Pneumonia",
      confidence: 0.88,
    },
  },
};

describe("Prediction result view model", () => {
  test("creates pending cards when there is no latest Prediction", () => {
    const viewModel = createPredictionResultViewModel(null);

    expect(viewModel).toMatchObject({
      uploadReference: "Prediction pending",
      uploadTone: "foreground",
      cards: [
        {
          slug: "effnetb0",
          statusCopy: "waiting",
          predictedClass: "Awaiting upload",
          confidenceText: "Pending",
        },
        {
          slug: "vitb16",
          statusCopy: "waiting",
          predictedClass: "Pending compare mode",
          confidenceText: "Pending",
        },
      ],
    });
  });

  test("creates single successful Prediction card", () => {
    const viewModel = createPredictionResultViewModel(singlePrediction);

    expect(viewModel).toMatchObject({
      uploadReference: "uploads/scan-a.png",
      uploadTone: "foreground",
      cards: [
        {
          slug: "effnetb0",
          label: "EffNetB0",
          statusCopy: "ok",
          predictedClass: "Pneumonia",
          confidenceText: "88.0%",
          confidencePercent: 88,
          confidenceTone: "success",
        },
      ],
    });
  });

  test("creates ordered cards for partial compare Prediction", () => {
    const viewModel = createPredictionResultViewModel({
      request_id: "request-compare",
      mode: "both",
      upload: { status: "error", image_s3_key: null },
      results: {
        vitb16: {
          status: "error",
          error: "timeout",
        },
        effnetb0: {
          status: "ok",
          prediction: "Normal",
          confidence: 0.67,
        },
      },
    });

    expect(viewModel).toMatchObject({
      uploadReference: "Upload not persisted",
      uploadTone: "warning",
      cards: [
        {
          slug: "effnetb0",
          statusCopy: "ok",
          predictedClass: "Normal",
          confidenceTone: "warning",
        },
        {
          slug: "vitb16",
          statusCopy: "error",
          predictedClass: "timeout",
          confidenceText: "Unavailable",
          confidencePercent: null,
        },
      ],
    });
  });

  test("maps confidence thresholds without changing current behavior", () => {
    expect(toneForConfidence(0.81)).toBe("success");
    expect(toneForConfidence(0.8)).toBe("warning");
    expect(toneForConfidence(0.51)).toBe("warning");
    expect(toneForConfidence(0.5)).toBe("danger");
  });
});
