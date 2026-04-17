import {
  type ChangeEvent,
  type DragEvent,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";
import * as api from "@/lib/api";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const ACCEPTED_IMAGE_TYPES = ["image/png", "image/jpeg", "image/webp"];

function formatFileSize(size: number) {
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }

  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

interface ImageDropzoneProps {
  mode: api.PredictionMode | "";
  onPrediction: (result: api.UnifiedPredictionResponse | null) => void;
}

export default function ImageDropzone({
  mode,
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

    onPrediction(null);

    if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
      setError("Use a PNG, JPG, or WEBP image.");
      return;
    }

    setSelectedFile(file);
    setError(null);
  };

  const handleUpload = async () => {
    if (!selectedFile || !mode) {
      if (!mode) {
        toast.error("Select a model first.");
      }
      return;
    }

    setUploading(true);
    try {
      const result = await api.predict(mode, selectedFile);
      onPrediction(result);
      toast.success(
        mode === "both" ? "Compare run complete." : "Prediction complete.",
      );
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
    onPrediction(null);

    if (inputRef.current) {
      inputRef.current.value = "";
    }
  };

  const canUpload = Boolean(selectedFile && mode && !uploading);
  const helperTone = error
    ? "error"
    : !mode && selectedFile
      ? "warning"
      : "muted";
  const helperMessage = error
    ? error
    : !mode && selectedFile
      ? "Select a model before running classification."
      : selectedFile
        ? "Image ready. Review details below and run prediction when ready."
        : "PNG, JPG, or WEBP. Maximum upload size: 2 MB.";
  const helperClassName =
    helperTone === "error"
      ? "text-[var(--color-opencode-danger)]"
      : helperTone === "warning"
        ? "text-[var(--color-opencode-warning)]"
        : "text-muted-foreground";

  return (
    <div className="flex flex-col gap-4">
      <label
        htmlFor={inputId}
        className={cn(
          "group bg-card relative flex min-h-[18rem] cursor-pointer flex-col items-center justify-center overflow-hidden rounded-[4px] border px-6 py-10 text-center transition-[border-color,background-color] duration-150 sm:min-h-[18rem] sm:px-10",
          error
            ? "border-[var(--color-opencode-danger)]"
            : isDragging
              ? "border-[var(--color-opencode-accent-blue)]"
              : selectedFile
                ? "border-[var(--color-opencode-success)]"
                : "border-border hover:border-[var(--color-opencode-border-outline)]",
          uploading && "opacity-85",
        )}
        aria-busy={uploading}
        aria-describedby={`${inputId}-helper`}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
      >
        <input
          ref={inputRef}
          id={inputId}
          type="file"
          accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
          className="sr-only"
          onChange={onInputChange}
        />

        <div className="relative z-10 max-w-[38ch]">
          <p className="text-muted-foreground text-xs leading-none font-bold tracking-[0.08em] uppercase">
            Chest X-ray upload
          </p>
          <h2 className="text-foreground mt-1 font-mono text-base leading-[1.5] font-bold sm:text-[1.0625rem]">
            {selectedFile
              ? "Image ready for pneumonia classification"
              : "Drop chest X-ray image here"}
          </h2>
          <p className="text-muted-foreground mt-2 text-sm leading-[1.5] sm:text-base">
            {selectedFile
              ? "Replace it by dropping another chest X-ray image or choosing a new one."
              : "Drag and drop a PNG, JPG, or WEBP chest X-ray image, or choose one from your device."}
          </p>
        </div>

        <div aria-hidden="true" className="relative z-10 mt-6">
          <span className="text-foreground inline-flex min-h-11 items-center justify-center rounded-[4px] border border-[var(--color-opencode-border-outline)] px-5 py-1 text-sm leading-[1.5] font-medium transition-[border-color,background-color,color] duration-150 group-hover:border-[var(--color-opencode-accent-blue)] group-hover:bg-white/5">
            {selectedFile ? "Replace image" : "Choose image"}
          </span>
        </div>

        {previewUrl ? (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-4">
            <img
              src={previewUrl}
              alt={selectedFile?.name ?? "Selected upload preview"}
              className="h-full w-full rounded-[4px] object-contain opacity-25"
            />
          </div>
        ) : (
          <div
            className="pointer-events-none absolute inset-0 flex items-center justify-center opacity-10"
            aria-hidden="true"
          >
            <div className="text-muted-foreground relative h-28 w-28 rounded-[4px] border border-current">
              <div className="absolute -right-4 -bottom-4 h-16 w-16 rounded-[4px] border border-current" />
            </div>
          </div>
        )}
      </label>

      <div
        className="border-border bg-card flex flex-col gap-4 rounded-[4px] border px-5 py-4 text-sm sm:flex-row sm:items-center sm:px-6"
        aria-live="polite"
      >
        <div className="min-w-0 flex-1">
          <span className="text-muted-foreground text-xs leading-none font-medium tracking-[0.08em] uppercase">
            Selected file
          </span>
          <strong className="text-foreground mt-1 block text-sm font-bold [overflow-wrap:anywhere] sm:text-base">
            {selectedFile?.name ?? "No file selected"}
          </strong>
        </div>
        <div className="min-w-0 sm:w-32">
          <span className="text-muted-foreground text-xs leading-none font-medium tracking-[0.08em] uppercase">
            File size
          </span>
          <strong className="text-foreground mt-1 block text-sm font-bold sm:text-base">
            {selectedFile ? formatFileSize(selectedFile.size) : "-"}
          </strong>
        </div>
        <button
          type="button"
          onClick={clearFile}
          disabled={!selectedFile || uploading}
          className="inline-flex min-h-10 items-center justify-center rounded-[4px] border border-[rgba(255,59,48,0.3)] bg-[rgba(255,59,48,0.08)] px-4 py-1 text-sm font-medium text-[var(--color-opencode-danger)] transition-[border-color,background-color] duration-150 hover:border-[var(--color-opencode-danger)] hover:bg-[rgba(255,59,48,0.15)] disabled:cursor-not-allowed disabled:opacity-50 sm:ml-auto sm:min-w-[9rem]"
        >
          Remove image
        </button>
      </div>

      <div className="mt-4 flex flex-col items-center gap-4">
        <button
          type="button"
          onClick={handleUpload}
          className="inline-flex min-h-11 w-full items-center justify-center rounded-[4px] bg-[var(--color-opencode-accent-blue)] px-5 py-2 text-base leading-[1.5] font-bold text-white transition-[background-color,color] duration-150 hover:bg-[var(--color-opencode-accent-blue-hover)] active:bg-[var(--color-opencode-accent-blue-active)] disabled:cursor-not-allowed disabled:opacity-50 sm:w-fit sm:min-w-[12rem]"
          disabled={!canUpload}
          aria-busy={uploading}
        >
          {uploading ? "Processing..." : "Run prediction"}
        </button>

        <p
          id={`${inputId}-helper`}
          className={cn("min-h-6 text-sm font-medium", helperClassName)}
        >
          {helperMessage}
        </p>
      </div>
    </div>
  );
}
