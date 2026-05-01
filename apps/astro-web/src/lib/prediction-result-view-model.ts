import type { ModelSlug, Prediction, PredictionResultStatus } from "./api";

export type PredictionResultTone = "success" | "warning" | "danger" | "muted";
export type PredictionUploadTone = "foreground" | "warning";

export interface PredictionResultCardViewModel {
  slug: ModelSlug;
  label: string;
  statusCopy: string;
  predictedClass: string;
  valueTone: PredictionResultTone;
  confidenceTone: PredictionResultTone;
  confidenceText: string;
  confidencePercent: number | null;
}

export interface PredictionResultViewModel {
  summaryCopy: string;
  uploadReference: string;
  uploadTone: PredictionUploadTone;
  cards: PredictionResultCardViewModel[];
}

const MODEL_LABELS: Record<ModelSlug, string> = {
  effnetb0: "EffNetB0",
  vitb16: "ViTB16",
};

const RESULT_ORDER: ModelSlug[] = ["effnetb0", "vitb16"];

export function createPredictionResultViewModel(
  prediction: Prediction | null,
): PredictionResultViewModel {
  if (!prediction) {
    return {
      summaryCopy:
        "Upload a chest X-ray to populate predicted class, confidence, and upload status.",
      uploadReference: "Prediction pending",
      uploadTone: "foreground",
      cards: [
        createPredictionResultCard("effnetb0", null, "Awaiting upload"),
        createPredictionResultCard("vitb16", null, "Pending compare mode"),
      ],
    };
  }

  return {
    summaryCopy:
      prediction.mode === "both"
        ? "Latest upload scored both internal models on the same image."
        : "Latest upload scored selected model and recorded upload status.",
    uploadReference:
      prediction.upload.status === "ok"
        ? (prediction.upload.image_s3_key ?? "Stored without reference")
        : "Upload not persisted",
    uploadTone: prediction.upload.status === "ok" ? "foreground" : "warning",
    cards: RESULT_ORDER.flatMap((slug) => {
      const result = prediction.results[slug];
      return result ? [createPredictionResultCard(slug, result)] : [];
    }),
  };
}

function createPredictionResultCard(
  slug: ModelSlug,
  result: PredictionResultStatus | null,
  pendingLabel = "Awaiting upload",
): PredictionResultCardViewModel {
  if (!result) {
    return {
      slug,
      label: MODEL_LABELS[slug],
      statusCopy: "waiting",
      predictedClass: pendingLabel,
      valueTone: "muted",
      confidenceTone: "muted",
      confidenceText: "Pending",
      confidencePercent: null,
    };
  }

  if (result.status === "error") {
    return {
      slug,
      label: MODEL_LABELS[slug],
      statusCopy: "error",
      predictedClass: result.error ?? "Prediction failed",
      valueTone: "danger",
      confidenceTone: "danger",
      confidenceText: "Unavailable",
      confidencePercent: null,
    };
  }

  const confidence = result.confidence ?? 0;
  const confidenceTone = toneForConfidence(confidence);

  return {
    slug,
    label: MODEL_LABELS[slug],
    statusCopy: "ok",
    predictedClass: result.prediction ?? "Unknown",
    valueTone: "success",
    confidenceTone,
    confidenceText: `${(confidence * 100).toFixed(1)}%`,
    confidencePercent: Number((confidence * 100).toFixed(1)),
  };
}

export function toneForConfidence(confidence: number): PredictionResultTone {
  if (confidence > 0.8) return "success";
  if (confidence > 0.5) return "warning";
  return "danger";
}
