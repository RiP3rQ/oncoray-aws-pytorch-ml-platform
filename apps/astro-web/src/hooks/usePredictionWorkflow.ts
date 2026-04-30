import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "@/lib/api";
import {
  beginPredictionRun,
  canRunPrediction,
  clearChestXrayUploadDraft,
  completePredictionRun,
  createInitialPredictionWorkflowState,
  failPredictionRun,
  selectChestXrayUploadDraft,
  selectPredictionMode,
  toPredictionRunFailure,
  type PredictionRunner,
  type PredictionRunOutcome,
} from "@/lib/prediction-workflow";
import type { PredictionMode } from "@/lib/api";

const browserPredictionRunner: PredictionRunner = {
  run: api.predict,
};

export function usePredictionWorkflow(
  runner: PredictionRunner = browserPredictionRunner,
) {
  const [state, setState] = useState(createInitialPredictionWorkflowState);
  const previewUrlRef = useRef<string | null>(null);

  const releasePreviewUrl = useCallback(() => {
    if (previewUrlRef.current) {
      URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
  }, []);

  useEffect(() => releasePreviewUrl, [releasePreviewUrl]);

  const selectMode = useCallback((mode: PredictionMode) => {
    setState((current) => selectPredictionMode(current, mode));
  }, []);

  const selectUpload = useCallback(
    (file: File | undefined) => {
      if (!file) {
        return;
      }

      releasePreviewUrl();
      const previewUrl = URL.createObjectURL(file);
      previewUrlRef.current = previewUrl;

      setState((current) =>
        selectChestXrayUploadDraft(current, file, previewUrl),
      );
    },
    [releasePreviewUrl],
  );

  const clearUpload = useCallback(() => {
    releasePreviewUrl();
    setState((current) => clearChestXrayUploadDraft(current));
  }, [releasePreviewUrl]);

  const runPrediction = useCallback(async (): Promise<PredictionRunOutcome> => {
    if (!state.selectedMode) {
      const failure = {
        kind: "missing-mode" as const,
        message: "Select a model first.",
      };
      setState((current) => ({ ...current, runError: failure }));
      return { ok: false, failure };
    }

    if (state.uploadDraft.status !== "ready") {
      const failure = {
        kind: "network-error" as const,
        message: "Select a chest X-ray upload first.",
      };
      setState((current) => ({ ...current, runError: failure }));
      return { ok: false, failure };
    }

    const { selectedMode, uploadDraft } = state;
    setState((current) => beginPredictionRun(current));

    try {
      const prediction = await runner.run(selectedMode, uploadDraft.file);
      setState((current) => completePredictionRun(current, prediction));
      return { ok: true, prediction };
    } catch (error) {
      const failure = toPredictionRunFailure(error);
      setState((current) => failPredictionRun(current, error));
      return { ok: false, failure };
    }
  }, [runner, state]);

  return {
    ...state,
    canRun: canRunPrediction(state),
    selectMode,
    selectUpload,
    clearUpload,
    runPrediction,
  };
}
