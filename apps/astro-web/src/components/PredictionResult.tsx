import type { PredictionResponse } from "@/lib/api";

interface PredictionResultProps {
  prediction: PredictionResponse | null;
}

function confidenceColor(confidence: number): string {
  if (confidence > 0.8) return "#4ade80";
  if (confidence > 0.5) return "#facc15";
  return "#f87171";
}

export default function PredictionResult({
  prediction,
}: PredictionResultProps) {
  if (!prediction) {
    return null;
  }

  const percentage = (prediction.confidence * 100).toFixed(1);

  return (
    <div className="glass-card" style={{ padding: "24px", marginTop: "20px" }}>
      <p className="section-label" style={{ marginBottom: "16px" }}>
        Prediction result
      </p>

      <div style={{ display: "grid", gap: "14px" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "16px 18px",
            borderRadius: "20px",
            border: "1px solid var(--line)",
          }}
        >
          <span style={{ color: "var(--muted)" }}>Label</span>
          <strong style={{ fontSize: "1rem", color: "var(--text)" }}>
            {prediction.prediction}
          </strong>
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "16px 18px",
            borderRadius: "20px",
            border: "1px solid var(--line)",
          }}
        >
          <span style={{ color: "var(--muted)" }}>Confidence</span>
          <strong
            style={{
              fontSize: "1rem",
              color: confidenceColor(prediction.confidence),
            }}
          >
            {percentage}%
          </strong>
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            padding: "16px 18px",
            borderRadius: "20px",
            border: "1px solid var(--line)",
          }}
        >
          <span style={{ color: "var(--muted)" }}>Image reference</span>
          <strong
            style={{
              fontSize: "0.85rem",
              color: "var(--text)",
              fontFamily: "monospace",
            }}
          >
            {prediction.image_s3_key}
          </strong>
        </div>
      </div>
    </div>
  );
}
