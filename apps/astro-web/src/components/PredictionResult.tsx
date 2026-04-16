import type { PredictionResponse } from "@/lib/api";
import { cn } from "@/lib/utils";

interface PredictionResultProps {
  prediction: PredictionResponse | null;
}

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
  const confidence = prediction?.confidence ?? 0;
  const percentage = hasPrediction
    ? `${(confidence * 100).toFixed(1)}%`
    : "Pending";
  const confidenceBarClass = hasPrediction
    ? confidenceColor(confidence)
    : "bg-muted-foreground";
  const confidenceTextClass = hasPrediction
    ? confidenceTextColor(confidence)
    : "text-muted-foreground";
  const predictedClass = prediction?.prediction ?? "Awaiting upload";
  const uploadReference = prediction?.image_s3_key ?? "Prediction pending";
  const valueClass = cn(
    "text-base font-bold",
    hasPrediction ? "text-foreground" : "text-muted-foreground",
  );
  const monoValueClass = cn(
    "text-sm font-medium [overflow-wrap:anywhere] sm:text-base",
    hasPrediction ? "text-foreground" : "text-muted-foreground",
  );

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
          ? "Latest upload scored and stored."
          : "Upload a chest X-ray to populate predicted class, confidence, and storage reference."}
      </p>

      <div className="mt-4 grid gap-2">
        <div className="border-border bg-card flex flex-col gap-3 rounded-[4px] border px-5 py-4 transition-colors duration-150 hover:border-[var(--color-opencode-border-outline)] sm:flex-row sm:items-center sm:justify-between">
          <span className="text-muted-foreground text-xs leading-none font-bold tracking-[0.08em] uppercase">
            Predicted class
          </span>
          <strong className={valueClass}>{predictedClass}</strong>
        </div>

        <div className="border-border bg-card flex flex-col gap-3 rounded-[4px] border px-5 py-4 transition-colors duration-150 hover:border-[var(--color-opencode-border-outline)] sm:flex-row sm:items-center sm:justify-between">
          <span className="text-muted-foreground text-xs leading-none font-bold tracking-[0.08em] uppercase">
            Confidence
          </span>
          <div className="flex w-full flex-col gap-2 sm:w-[20rem] sm:flex-row sm:items-center">
            <div
              className="bg-border h-1 w-full overflow-hidden rounded-[4px]"
              role="progressbar"
              aria-label="Prediction confidence"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={
                hasPrediction
                  ? Number((confidence * 100).toFixed(1))
                  : undefined
              }
            >
              <div
                className={cn(
                  "h-full rounded-[4px] transition-[width] duration-200",
                  confidenceBarClass,
                )}
                style={{
                  width: hasPrediction ? `${confidence * 100}%` : "0%",
                }}
              />
            </div>
            <strong className={cn(valueClass, confidenceTextClass)}>
              {percentage}
            </strong>
          </div>
        </div>

        <div className="border-border bg-card flex flex-col gap-3 rounded-[4px] border px-5 py-4 transition-colors duration-150 hover:border-[var(--color-opencode-border-outline)] sm:flex-row sm:items-center sm:justify-between">
          <span className="text-muted-foreground text-xs leading-none font-bold tracking-[0.08em] uppercase">
            Upload reference
          </span>
          <strong className={monoValueClass}>{uploadReference}</strong>
        </div>
      </div>
    </div>
  );
}
