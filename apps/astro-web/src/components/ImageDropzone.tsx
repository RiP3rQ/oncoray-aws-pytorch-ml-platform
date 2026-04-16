import {
  type ChangeEvent,
  type DragEvent,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";
import * as api from "@/lib/api";
import { toast } from "sonner";

const ACCEPTED_IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp"];

function formatFileSize(size: number) {
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }

  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

interface ImageDropzoneProps {
  modelId: string;
  onPrediction: (result: api.PredictionResponse) => void;
}

export default function ImageDropzone({
  modelId,
  onPrediction,
}: ImageDropzoneProps) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    if (!selectedFile) {
      setPreviewUrl(null);
      return;
    }

    const objectUrl = URL.createObjectURL(selectedFile);
    setPreviewUrl(objectUrl);

    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [selectedFile]);

  const applyFile = (file: File | undefined) => {
    if (!file) {
      return;
    }

    if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
      setError("Use a PNG, JPG, or WEBP image.");
      return;
    }

    setSelectedFile(file);
    setError(null);
  };

  const handleUpload = async () => {
    if (!selectedFile || !modelId) {
      if (!modelId) {
        toast.error("Select a model first.");
      }
      return;
    }

    setUploading(true);
    try {
      const result = await api.predict(modelId, selectedFile);
      onPrediction(result);
      toast.success("Prediction complete.");
    } catch (err) {
      if (err instanceof api.ApiError) {
        if (err.status === 413) {
          toast.error("Image exceeds 2 MB limit.");
        } else {
          toast.error(err.message || "Prediction failed.");
        }
      } else {
        toast.error("Network error. Try again.");
      }
    } finally {
      setUploading(false);
    }
  };

  const onInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    applyFile(event.target.files?.[0]);
  };

  const onDragOver = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(true);
  };

  const onDragLeave = (event: DragEvent<HTMLLabelElement>) => {
    if (event.currentTarget.contains(event.relatedTarget as Node | null)) {
      return;
    }

    setIsDragging(false);
  };

  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    setIsDragging(false);
    applyFile(event.dataTransfer.files?.[0]);
  };

  const clearFile = () => {
    setSelectedFile(null);
    setError(null);

    if (inputRef.current) {
      inputRef.current.value = "";
    }
  };

  const canUpload = Boolean(selectedFile && modelId && !uploading);
  const helperTone = error
    ? "error"
    : !modelId && selectedFile
      ? "warning"
      : "muted";
  const helperMessage = error
    ? error
    : !modelId && selectedFile
      ? "Select a model before running classification."
      : selectedFile
        ? "Image ready. Review details below and run prediction when ready."
        : "PNG, JPG, or WEBP. Maximum upload size: 2 MB.";

  return (
    <div className="dropzone-shell animate-rise">
      <label
        htmlFor={inputId}
        className={`dropzone ${isDragging ? "is-dragging" : ""} ${selectedFile ? "has-file" : ""}`}
        aria-busy={uploading}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
          onChange={onInputChange}
        />

        <div className="dropzone-copy">
          <p className="dropzone-kicker">Chest X-ray upload</p>
          <h2>
            {selectedFile
              ? "Image ready for pneumonia classification"
              : "Drop chest X-ray image here"}
          </h2>
          <p>
            {selectedFile
              ? "Replace it by dropping another chest X-ray image or choosing a new one."
              : "Drag and drop a PNG, JPG, or WEBP chest X-ray image, or choose one from your device."}
          </p>
        </div>

        <div className="dropzone-actions" aria-hidden="true">
          <span className="dropzone-button">
            {selectedFile ? "Replace image" : "Choose image"}
          </span>
        </div>

        {previewUrl ? (
          <div className="dropzone-preview">
            <img
              src={previewUrl}
              alt={selectedFile?.name ?? "Selected upload preview"}
            />
          </div>
        ) : (
          <div className="dropzone-placeholder" aria-hidden="true">
            <div></div>
            <div></div>
          </div>
        )}
      </label>

      <div className="dropzone-meta" aria-live="polite">
        <div>
          <span>Selected file</span>
          <strong>{selectedFile?.name ?? "No file selected"}</strong>
        </div>
        <div>
          <span>File size</span>
          <strong>
            {selectedFile ? formatFileSize(selectedFile.size) : "-"}
          </strong>
        </div>
        <button
          type="button"
          onClick={clearFile}
          disabled={!selectedFile || uploading}
        >
          Remove image
        </button>
      </div>

      <button
        type="button"
        onClick={handleUpload}
        className="dropzone-upload-btn"
        disabled={!canUpload}
        aria-busy={uploading}
      >
        {uploading ? "Processing..." : "Run prediction"}
      </button>

      <p className={`dropzone-feedback dropzone-feedback--${helperTone}`}>
        {helperMessage}
      </p>
    </div>
  );
}
