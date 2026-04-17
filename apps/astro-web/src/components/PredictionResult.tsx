import type {
  ModelSlug,
  PredictionResultStatus,
  UnifiedPredictionResponse,
} from "@/lib/api";
import { cn } from "@/lib/utils";

interface PredictionResultProps {
  prediction: UnifiedPredictionResponse | null;
}

const MODEL_LABELS: Record<ModelSlug, string> = {
  effnetb0: "EffNetB0",
  vitb16: "ViTB16",
};

const RESULT_ORDER: ModelSlug[] = ["effnetb0", "vitb16"];

function confidenceColor(confidence: number): string {
  if (confidence > 0.8) return "bg-[var(--color-opencode-success)]";
  if (confidence > 0.5) return "bg-[var(--color-opencode-warning)]";
  return "bg-[var(--color-opencode-danger)]";
}

function confidenceTextColor(confidence: number): string {
  if (confidence > 0.8) return "text-[var(--color-opencode-success)]";
  if (confidence > 0.5) return "text-[var(--color-opencode-warning)]";
  return "text-[var(--color-opencode-danger)]";
}

export default function PredictionResult({
  prediction,
}: PredictionResultProps) {
  const hasPrediction = prediction !== null;
  const uploadReference = !prediction
    ? "Prediction pending"
    : prediction.upload.status === "ok"
      ? (prediction.upload.image_s3_key ?? "Stored without reference")
      : "Upload not persisted";
  const uploadToneClass =
    !prediction || prediction.upload.status === "ok"
      ? "text-foreground"
      : "text-[var(--color-opencode-warning)]";
  const orderedResults = RESULT_ORDER.flatMap((slug) => {
    const result = prediction?.results[slug];
    return result ? [{ slug, result }] : [];
  });

  return (
    <div
      className="border-border bg-card motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2 rounded-[4px] border p-6 motion-safe:duration-200 sm:p-8"
      aria-live="polite"
    >
      <p className="text-muted-foreground text-sm leading-none font-bold tracking-[0.05em] uppercase">
        Classification result
      </p>
      <p className="text-muted-foreground mt-3 max-w-[48ch] text-sm leading-[1.5] sm:text-[0.9375rem]">
        {hasPrediction
          ? prediction.mode === "both"
            ? "Latest upload scored both internal models on the same image."
            : "Latest upload scored selected model and recorded upload status."
          : "Upload a chest X-ray to populate predicted class, confidence, and upload status."}
      </p>

      <div className="mt-4 grid gap-4">
        <div className="grid gap-4 lg:grid-cols-2">
          {hasPrediction ? (
            orderedResults.map(({ slug, result }) => (
              <PredictionCard key={slug} slug={slug} result={result} />
            ))
          ) : (
            <PredictionCard
              slug="effnetb0"
              result={null}
              pendingLabel="Awaiting upload"
            />
          )}
          {!hasPrediction ? (
            <PredictionCard
              slug="vitb16"
              result={null}
              pendingLabel="Pending compare mode"
            />
          ) : null}
        </div>

        <div className="border-border bg-card flex flex-col gap-3 rounded-[4px] border px-5 py-4 transition-colors duration-150 hover:border-[var(--color-opencode-border-outline)] sm:flex-row sm:items-center sm:justify-between">
          <span className="text-muted-foreground text-xs leading-none font-bold tracking-[0.08em] uppercase">
            Upload reference
          </span>
          <strong
            className={cn(
              "text-sm font-medium [overflow-wrap:anywhere] sm:text-base",
              uploadToneClass,
            )}
          >
            {uploadReference}
          </strong>
        </div>
      </div>
    </div>
  );
}

function PredictionCard({
  slug,
  result,
  pendingLabel = "Awaiting upload",
}: {
  slug: ModelSlug;
  result: PredictionResultStatus | null;
  pendingLabel?: string;
}) {
  const isPending = result === null;
  const isOk = result?.status === "ok";
  const confidence = isOk ? (result.confidence ?? 0) : 0;
  const percentage = isOk
    ? `${(confidence * 100).toFixed(1)}%`
    : isPending
      ? "Pending"
      : "Unavailable";
  const confidenceBarClass = isOk
    ? confidenceColor(confidence)
    : "bg-muted-foreground";
  const confidenceTextClass = isOk
    ? confidenceTextColor(confidence)
    : result?.status === "error"
      ? "text-[var(--color-opencode-danger)]"
      : "text-muted-foreground";
  const predictedClass = isOk
    ? (result.prediction ?? "Unknown")
    : isPending
      ? pendingLabel
      : (result.error ?? "Prediction failed");
  const statusCopy = isOk
    ? "ok"
    : result?.status === "error"
      ? "error"
      : "waiting";
  const valueClass = cn(
    "text-base font-bold",
    isOk
      ? "text-foreground"
      : result?.status === "error"
        ? "text-[var(--color-opencode-danger)]"
        : "text-muted-foreground",
  );

  return (
    <div className="border-border bg-card rounded-[4px] border px-5 py-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-muted-foreground text-xs leading-none font-bold tracking-[0.08em] uppercase">
          {MODEL_LABELS[slug]}
        </p>
        <span
          className={cn(
            "text-xs leading-none font-medium tracking-[0.08em] uppercase",
            isOk
              ? "text-[var(--color-opencode-success)]"
              : result?.status === "error"
                ? "text-[var(--color-opencode-danger)]"
                : "text-muted-foreground",
          )}
        >
          {statusCopy}
        </span>
      </div>

      <div className="mt-4 grid gap-2">
        <div className="border-border bg-card flex flex-col gap-3 rounded-[4px] border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <span className="text-muted-foreground text-xs leading-none font-bold tracking-[0.08em] uppercase">
            Predicted class
          </span>
          <strong className={valueClass}>{predictedClass}</strong>
        </div>

        <div className="border-border bg-card flex flex-col gap-3 rounded-[4px] border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <span className="text-muted-foreground text-xs leading-none font-bold tracking-[0.08em] uppercase">
            Confidence
          </span>
          <div className="flex w-full flex-col gap-2 sm:w-[16rem] sm:flex-row sm:items-center">
            <div
              className="bg-border h-1 w-full overflow-hidden rounded-[4px]"
              role="progressbar"
              aria-label={`${MODEL_LABELS[slug]} prediction confidence`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={
                isOk ? Number((confidence * 100).toFixed(1)) : undefined
              }
            >
              <div
                className={cn(
                  "h-full rounded-[4px] transition-[width] duration-200",
                  confidenceBarClass,
                )}
                style={{
                  width: isOk ? `${confidence * 100}%` : "0%",
                }}
              />
            </div>
            <strong className={cn("text-base font-bold", confidenceTextClass)}>
              {percentage}
            </strong>
          </div>
        </div>
      </div>
    </div>
  );
}
