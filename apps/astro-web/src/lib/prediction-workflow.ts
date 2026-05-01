import { ApiError, type Prediction, type PredictionMode } from "./api";
import { validateChestXrayUploadDraft } from "./chest-xray-upload";

export type ChestXrayUploadDraft =
  | { status: "empty" }
  | { status: "invalid"; file: File; message: string }
  | {
      status: "ready";
      file: File;
      previewUrl: string;
      displayName: string;
      displaySize: string;
    };

export type PredictionRunFailure =
  | { kind: "missing-mode"; message: string }
  | { kind: "missing-upload"; message: string }
  | { kind: "already-running"; message: string }
  | { kind: "upload-too-large"; message: string }
  | { kind: "api-error"; message: string }
  | { kind: "network-error"; message: string };

export interface PredictionWorkflowState {
  selectedMode: PredictionMode | "";
  uploadDraft: ChestXrayUploadDraft;
  prediction: Prediction | null;
  isRunning: boolean;
  runError: PredictionRunFailure | null;
}

export interface PredictionRunner {
  run(mode: PredictionMode, upload: File): Promise<Prediction>;
}

export type PredictionRunOutcome =
  | { ok: true; prediction: Prediction }
  | { ok: false; failure: PredictionRunFailure };

export type PredictionWorkflowRunRequest =
  | { ok: true; mode: PredictionMode; upload: File }
  | {
      ok: false;
      state: PredictionWorkflowState;
      failure: PredictionRunFailure;
    };

export type PredictionWorkflowEvent =
  | { type: "mode-selected"; mode: PredictionMode }
  | { type: "upload-selected"; file: File; previewUrl: string }
  | { type: "upload-cleared" }
  | { type: "run-requested" }
  | { type: "run-succeeded"; prediction: Prediction }
  | { type: "run-failed"; error: unknown };

export function createInitialPredictionWorkflowState(): PredictionWorkflowState {
  return {
    selectedMode: "",
    uploadDraft: { status: "empty" },
    prediction: null,
    isRunning: false,
    runError: null,
  };
}

export function formatChestXrayUploadSize(size: number): string {
  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`;
  }

  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export function selectPredictionMode(
  state: PredictionWorkflowState,
  mode: PredictionMode,
): PredictionWorkflowState {
  return {
    ...state,
    selectedMode: mode,
    prediction: null,
    runError: null,
  };
}

export function transitionPredictionWorkflow(
  state: PredictionWorkflowState,
  event: PredictionWorkflowEvent,
): PredictionWorkflowState {
  switch (event.type) {
    case "mode-selected":
      return selectPredictionMode(state, event.mode);
    case "upload-selected":
      return selectChestXrayUploadDraft(state, event.file, event.previewUrl);
    case "upload-cleared":
      return clearChestXrayUploadDraft(state);
    case "run-requested": {
      const request = preparePredictionRun(state);
      if (!request.ok) {
        return request.state;
      }

      return beginPredictionRun(state);
    }
    case "run-succeeded":
      return completePredictionRun(state, event.prediction);
    case "run-failed":
      return failPredictionRun(state, event.error);
  }
}

export function preparePredictionRun(
  state: PredictionWorkflowState,
): PredictionWorkflowRunRequest {
  if (state.isRunning) {
    const failure: PredictionRunFailure = {
      kind: "already-running",
      message: "Prediction already running.",
    };

    return {
      ok: false,
      state: { ...state, runError: failure },
      failure,
    };
  }

  if (!state.selectedMode) {
    const failure: PredictionRunFailure = {
      kind: "missing-mode",
      message: "Select a model first.",
    };

    return {
      ok: false,
      state: { ...state, runError: failure },
      failure,
    };
  }

  if (state.uploadDraft.status !== "ready") {
    const failure: PredictionRunFailure = {
      kind: "missing-upload",
      message: "Select a chest X-ray upload first.",
    };

    return {
      ok: false,
      state: { ...state, runError: failure },
      failure,
    };
  }

  return {
    ok: true,
    mode: state.selectedMode,
    upload: state.uploadDraft.file,
  };
}

export function selectChestXrayUploadDraft(
  state: PredictionWorkflowState,
  file: File,
  previewUrl: string,
): PredictionWorkflowState {
  const validation = validateChestXrayUploadDraft(file);

  if (!validation.ok) {
    return {
      ...state,
      uploadDraft: { status: "invalid", file, message: validation.message },
      prediction: null,
      runError: null,
    };
  }

  return {
    ...state,
    uploadDraft: {
      status: "ready",
      file,
      previewUrl,
      displayName: file.name,
      displaySize: formatChestXrayUploadSize(file.size),
    },
    prediction: null,
    runError: null,
  };
}

export function clearChestXrayUploadDraft(
  state: PredictionWorkflowState,
): PredictionWorkflowState {
  return {
    ...state,
    uploadDraft: { status: "empty" },
    prediction: null,
    runError: null,
  };
}

export function beginPredictionRun(
  state: PredictionWorkflowState,
): PredictionWorkflowState {
  return {
    ...state,
    prediction: null,
    isRunning: true,
    runError: null,
  };
}

export function completePredictionRun(
  state: PredictionWorkflowState,
  prediction: Prediction,
): PredictionWorkflowState {
  return {
    ...state,
    prediction,
    isRunning: false,
    runError: null,
  };
}

export function failPredictionRun(
  state: PredictionWorkflowState,
  error: unknown,
): PredictionWorkflowState {
  const failure = toPredictionRunFailure(error);
  const uploadDraft =
    failure.kind === "upload-too-large" && state.uploadDraft.status === "ready"
      ? {
          status: "invalid" as const,
          file: state.uploadDraft.file,
          message: failure.message,
        }
      : state.uploadDraft;

  return {
    ...state,
    uploadDraft,
    prediction: null,
    isRunning: false,
    runError: failure,
  };
}

export function toPredictionRunFailure(error: unknown): PredictionRunFailure {
  if (error instanceof ApiError) {
    if (error.status === 413) {
      return {
        kind: "upload-too-large",
        message: "Image exceeds 2 MB limit.",
      };
    }

    return {
      kind: "api-error",
      message: error.message || "Prediction failed.",
    };
  }

  return {
    kind: "network-error",
    message: "Network error. Try again.",
  };
}

export function canRunPrediction(state: PredictionWorkflowState): boolean {
  return Boolean(
    state.selectedMode &&
    state.uploadDraft.status === "ready" &&
    !state.isRunning,
  );
}
