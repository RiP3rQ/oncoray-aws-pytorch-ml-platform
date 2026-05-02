import type { UnifiedPredictionResponse } from "@/lib/api";
import {
  createPredictionResultViewModel,
  type PredictionResultCardViewModel,
  type PredictionResultTone,
  type PredictionUploadTone,
} from "@/lib/prediction-result-view-model";
import { cn } from "@/lib/utils";

interface PredictionResultProps {
  prediction: UnifiedPredictionResponse | null;
}

export default function PredictionResult({
  prediction,
}: PredictionResultProps) {
  const viewModel = createPredictionResultViewModel(prediction);

  return (
    <div
      className="border-border bg-card motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2 rounded-[4px] border p-6 motion-safe:duration-200 sm:p-8"
      aria-live="polite"
    >
      <p className="text-muted-foreground text-sm leading-none font-bold tracking-[0.05em] uppercase">
        Classification result
      </p>
      <p className="text-muted-foreground mt-3 max-w-[48ch] text-sm leading-[1.5] sm:text-[0.9375rem]">
        {viewModel.summaryCopy}
      </p>

      <div className="mt-4 grid gap-4">
        <div className="grid gap-4 lg:grid-cols-2">
          {viewModel.cards.map((card) => (
            <PredictionCard key={card.slug} card={card} />
          ))}
        </div>

        <div className="border-border bg-card flex flex-col gap-3 rounded-[4px] border px-5 py-4 transition-colors duration-150 hover:border-[var(--color-opencode-border-outline)] sm:flex-row sm:items-center sm:justify-between">
          <span className="text-muted-foreground text-xs leading-none font-bold tracking-[0.08em] uppercase">
            Upload reference
          </span>
          <strong
            className={cn(
              "text-sm font-medium [overflow-wrap:anywhere] sm:text-base",
              uploadToneClass(viewModel.uploadTone),
            )}
          >
            {viewModel.uploadReference}
          </strong>
        </div>
      </div>
    </div>
  );
}

function PredictionCard({ card }: { card: PredictionResultCardViewModel }) {
  return (
    <div className="border-border bg-card min-w-0 overflow-hidden rounded-[4px] border px-5 py-4">
      <div className="flex min-w-0 flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-muted-foreground text-xs leading-none font-bold tracking-[0.08em] uppercase">
          {card.label}
        </p>
        <span
          className={cn(
            "text-xs leading-none font-medium tracking-[0.08em] uppercase",
            statusToneClass(card.valueTone),
          )}
        >
          {card.statusCopy}
        </span>
      </div>

      <div className="mt-4 grid gap-2">
        <div className="border-border bg-card grid min-w-0 gap-3 rounded-[4px] border px-4 py-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,13rem)] sm:items-center">
          <span className="text-muted-foreground text-xs leading-none font-bold tracking-[0.08em] uppercase">
            Predicted class
          </span>
          <strong
            className={cn(
              "min-w-0 text-base font-bold [overflow-wrap:anywhere] sm:text-right",
              valueToneClass(card.valueTone),
            )}
          >
            {card.predictedClass}
          </strong>
        </div>

        <div className="border-border bg-card grid min-w-0 gap-3 rounded-[4px] border px-4 py-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,13rem)] sm:items-center">
          <span className="text-muted-foreground text-xs leading-none font-bold tracking-[0.08em] uppercase">
            Confidence
          </span>
          <div className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
            <div
              className="bg-border h-1 min-w-0 overflow-hidden rounded-[4px]"
              role="progressbar"
              aria-label={`${card.label} prediction confidence`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={card.confidencePercent ?? undefined}
            >
              <div
                className={cn(
                  "h-full rounded-[4px] transition-[width] duration-200",
                  confidenceBarClass(card.confidenceTone),
                )}
                style={{
                  width: `${confidenceBarWidth(card.confidencePercent)}%`,
                }}
              />
            </div>
            <strong
              className={cn(
                "shrink-0 text-right text-base font-bold tabular-nums",
                confidenceTextClass(card.confidenceTone),
              )}
            >
              {card.confidenceText}
            </strong>
          </div>
        </div>
      </div>
    </div>
  );
}

function confidenceBarWidth(confidencePercent: number | null): number {
  if (confidencePercent === null) return 0;
  return Math.min(Math.max(confidencePercent, 0), 100);
}

function uploadToneClass(tone: PredictionUploadTone): string {
  return tone === "foreground"
    ? "text-foreground"
    : "text-[var(--color-opencode-warning)]";
}

function statusToneClass(tone: PredictionResultTone): string {
  if (tone === "success") return "text-[var(--color-opencode-success)]";
  if (tone === "danger") return "text-[var(--color-opencode-danger)]";
  return "text-muted-foreground";
}

function valueToneClass(tone: PredictionResultTone): string {
  if (tone === "success") return "text-foreground";
  if (tone === "danger") return "text-[var(--color-opencode-danger)]";
  return "text-muted-foreground";
}

function confidenceBarClass(tone: PredictionResultTone): string {
  if (tone === "success") return "bg-[var(--color-opencode-success)]";
  if (tone === "warning") return "bg-[var(--color-opencode-warning)]";
  if (tone === "danger") return "bg-[var(--color-opencode-danger)]";
  return "bg-muted-foreground";
}

function confidenceTextClass(tone: PredictionResultTone): string {
  if (tone === "success") return "text-[var(--color-opencode-success)]";
  if (tone === "warning") return "text-[var(--color-opencode-warning)]";
  if (tone === "danger") return "text-[var(--color-opencode-danger)]";
  return "text-muted-foreground";
}
