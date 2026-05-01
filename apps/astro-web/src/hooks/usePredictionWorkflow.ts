import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "@/lib/api";
import {
  canRunPrediction,
  createInitialPredictionWorkflowState,
  preparePredictionRun,
  toPredictionRunFailure,
  transitionPredictionWorkflow,
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
    setState((current) =>
      transitionPredictionWorkflow(current, { type: "mode-selected", mode }),
    );
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
        transitionPredictionWorkflow(current, {
          type: "upload-selected",
          file,
          previewUrl,
        }),
      );
    },
    [releasePreviewUrl],
  );

  const clearUpload = useCallback(() => {
    releasePreviewUrl();
    setState((current) =>
      transitionPredictionWorkflow(current, { type: "upload-cleared" }),
    );
  }, [releasePreviewUrl]);

  const runPrediction = useCallback(async (): Promise<PredictionRunOutcome> => {
    const request = preparePredictionRun(state);
    if (!request.ok) {
      setState(request.state);
      return { ok: false, failure: request.failure };
    }

    setState((current) =>
      transitionPredictionWorkflow(current, { type: "run-requested" }),
    );

    try {
      const prediction = await runner.run(request.mode, request.upload);
      setState((current) =>
        transitionPredictionWorkflow(current, {
          type: "run-succeeded",
          prediction,
        }),
      );
      return { ok: true, prediction };
    } catch (error) {
      const failure = toPredictionRunFailure(error);
      setState((current) =>
        transitionPredictionWorkflow(current, { type: "run-failed", error }),
      );
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
