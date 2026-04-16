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
  if (!prediction) {
    return null;
  }

  const percentage = (prediction.confidence * 100).toFixed(1);

  return (
    <div className="prediction-card flat-card animate-rise">
      <p className="section-label">Classification result</p>

      <div className="prediction-grid">
        <div className="prediction-row">
          <span className="prediction-label">Predicted class</span>
          <strong className="prediction-value">{prediction.prediction}</strong>
        </div>

        <div className="prediction-row">
          <span className="prediction-label">Confidence</span>
          <div className="confidence-bar-container">
            <div className="confidence-bar">
              <div
                className="confidence-bar-fill"
                style={{
                  width: `${prediction.confidence * 100}%`,
                  backgroundColor: confidenceColor(prediction.confidence),
                }}
              />
            </div>
            <strong
              className="prediction-value"
              style={{ color: confidenceColor(prediction.confidence) }}
            >
              {percentage}%
            </strong>
          </div>
        </div>

        <div className="prediction-row">
          <span className="prediction-label">Upload reference</span>
          <strong className="prediction-value mono">
            {prediction.image_s3_key}
          </strong>
        </div>
      </div>
    </div>
  );
}
