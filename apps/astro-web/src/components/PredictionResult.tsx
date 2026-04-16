import type { PredictionResponse } from "@/lib/api";

interface PredictionResultProps {
  prediction: PredictionResponse | null;
}

function confidenceColor(confidence: number): string {
  if (confidence > 0.8) return "var(--success)";
  if (confidence > 0.5) return "var(--warning)";
  return "var(--danger)";
}

export default function PredictionResult({
  prediction,
}: PredictionResultProps) {
  const hasPrediction = prediction !== null;
  const confidence = prediction?.confidence ?? 0;
  const percentage = hasPrediction
    ? `${(confidence * 100).toFixed(1)}%`
    : "Pending";
  const confidenceColorValue = hasPrediction
    ? confidenceColor(confidence)
    : "var(--muted)";
  const predictedClass = prediction?.prediction ?? "Awaiting upload";
  const uploadReference = prediction?.image_s3_key ?? "Prediction pending";
  const valueClass = hasPrediction
    ? "prediction-value"
    : "prediction-value prediction-value--placeholder";
  const monoValueClass = hasPrediction
    ? "prediction-value mono"
    : "prediction-value mono prediction-value--placeholder";

  return (
    <div className="prediction-card flat-card animate-rise" aria-live="polite">
      <p className="section-label">Classification result</p>
      <p className="prediction-note">
        {hasPrediction
          ? "Latest upload scored and stored."
          : "Upload a chest X-ray to populate predicted class, confidence, and storage reference."}
      </p>

      <div className="prediction-grid">
        <div className="prediction-row">
          <span className="prediction-label">Predicted class</span>
          <strong className={valueClass}>{predictedClass}</strong>
        </div>

        <div className="prediction-row">
          <span className="prediction-label">Confidence</span>
          <div className="confidence-bar-container">
            <div className="confidence-bar">
              <div
                className="confidence-bar-fill"
                style={{
                  width: `${confidence * 100}%`,
                  backgroundColor: confidenceColorValue,
                }}
              />
            </div>
            <strong
              className={valueClass}
              style={{ color: confidenceColorValue }}
            >
              {percentage}
            </strong>
          </div>
        </div>

        <div className="prediction-row">
          <span className="prediction-label">Upload reference</span>
          <strong className={monoValueClass}>{uploadReference}</strong>
        </div>
      </div>
    </div>
  );
}
