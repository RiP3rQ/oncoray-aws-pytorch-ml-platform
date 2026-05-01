import { describe, expect, test } from "bun:test";
import { ApiError, type Prediction } from "./api";
import {
  beginPredictionRun,
  clearChestXrayUploadDraft,
  completePredictionRun,
  createInitialPredictionWorkflowState,
  failPredictionRun,
  preparePredictionRun,
  selectChestXrayUploadDraft,
  selectPredictionMode,
  transitionPredictionWorkflow,
} from "./prediction-workflow";

function file(name: string, type: string, size = 1536) {
  return new File([new Uint8Array(size)], name, { type });
}

const prediction: Prediction = {
  request_id: "request-1",
  mode: "effnetb0",
  upload: { status: "ok", image_s3_key: "uploads/scan-a.png" },
  results: {
    effnetb0: {
      status: "ok",
      prediction: "Normal",
      confidence: 0.91,
    },
  },
};

describe("Prediction Workflow state", () => {
  test("valid Chest X-ray Upload becomes ready with display metadata", () => {
    const state = selectChestXrayUploadDraft(
      createInitialPredictionWorkflowState(),
      file("scan-a.png", "image/png", 1536),
      "blob:scan-a",
    );

    expect(state.uploadDraft).toMatchObject({
      status: "ready",
      displayName: "scan-a.png",
      displaySize: "1.5 KB",
      previewUrl: "blob:scan-a",
    });
  });

  test("invalid type clears latest Prediction", () => {
    const withPrediction = completePredictionRun(
      beginPredictionRun(createInitialPredictionWorkflowState()),
      prediction,
    );

    const state = selectChestXrayUploadDraft(
      withPrediction,
      file("notes.txt", "text/plain"),
      "blob:notes",
    );

    expect(state.prediction).toBeNull();
    expect(state.uploadDraft).toMatchObject({
      status: "invalid",
      message: "Use a PNG, JPG, or WEBP image.",
    });
  });

  test("mode change keeps upload and clears latest Prediction", () => {
    const withUpload = selectChestXrayUploadDraft(
      createInitialPredictionWorkflowState(),
      file("scan-a.png", "image/png"),
      "blob:scan-a",
    );
    const withPrediction = completePredictionRun(
      beginPredictionRun(withUpload),
      prediction,
    );

    const state = selectPredictionMode(withPrediction, "vitb16");

    expect(state.selectedMode).toBe("vitb16");
    expect(state.uploadDraft.status).toBe("ready");
    expect(state.prediction).toBeNull();
  });

  test("successful run stores latest Prediction", () => {
    const state = completePredictionRun(
      beginPredictionRun(createInitialPredictionWorkflowState()),
      prediction,
    );

    expect(state.isRunning).toBe(false);
    expect(state.prediction).toBe(prediction);
    expect(state.runError).toBeNull();
  });

  test("413 marks ready upload invalid", () => {
    const running = beginPredictionRun(
      selectChestXrayUploadDraft(
        createInitialPredictionWorkflowState(),
        file("scan-a.png", "image/png"),
        "blob:scan-a",
      ),
    );

    const state = failPredictionRun(running, new ApiError(413, "too large"));

    expect(state.prediction).toBeNull();
    expect(state.uploadDraft).toMatchObject({
      status: "invalid",
      message: "Image exceeds 2 MB limit.",
    });
  });

  test("generic failure clears Prediction but keeps ready upload", () => {
    const running = beginPredictionRun(
      selectChestXrayUploadDraft(
        completePredictionRun(
          beginPredictionRun(createInitialPredictionWorkflowState()),
          prediction,
        ),
        file("scan-a.png", "image/png"),
        "blob:scan-a",
      ),
    );

    const state = failPredictionRun(running, new Error("offline"));

    expect(state.prediction).toBeNull();
    expect(state.uploadDraft.status).toBe("ready");
    expect(state.runError).toMatchObject({
      kind: "network-error",
      message: "Network error. Try again.",
    });
  });

  test("clear upload clears latest Prediction", () => {
    const withUpload = selectChestXrayUploadDraft(
      createInitialPredictionWorkflowState(),
      file("scan-a.png", "image/png"),
      "blob:scan-a",
    );
    const withPrediction = completePredictionRun(
      beginPredictionRun(withUpload),
      prediction,
    );

    const state = clearChestXrayUploadDraft(withPrediction);

    expect(state.uploadDraft.status).toBe("empty");
    expect(state.prediction).toBeNull();
  });

  test("run request fails when mode is missing", () => {
    const state = selectChestXrayUploadDraft(
      createInitialPredictionWorkflowState(),
      file("scan-a.png", "image/png"),
      "blob:scan-a",
    );

    const request = preparePredictionRun(state);

    expect(request).toMatchObject({
      ok: false,
      failure: {
        kind: "missing-mode",
        message: "Select a model first.",
      },
    });
  });

  test("run request fails when Chest X-ray Upload is missing", () => {
    const state = selectPredictionMode(
      createInitialPredictionWorkflowState(),
      "effnetb0",
    );

    const request = preparePredictionRun(state);

    expect(request).toMatchObject({
      ok: false,
      failure: {
        kind: "missing-upload",
        message: "Select a chest X-ray upload first.",
      },
    });
  });

  test("run request fails while Prediction is already running", () => {
    const state = beginPredictionRun(
      selectPredictionMode(
        selectChestXrayUploadDraft(
          createInitialPredictionWorkflowState(),
          file("scan-a.png", "image/png"),
          "blob:scan-a",
        ),
        "effnetb0",
      ),
    );

    const request = preparePredictionRun(state);

    expect(request).toMatchObject({
      ok: false,
      failure: {
        kind: "already-running",
        message: "Prediction already running.",
      },
    });
  });

  test("run request returns selected mode and ready Chest X-ray Upload", () => {
    const upload = file("scan-a.png", "image/png");
    const state = selectPredictionMode(
      selectChestXrayUploadDraft(
        createInitialPredictionWorkflowState(),
        upload,
        "blob:scan-a",
      ),
      "effnetb0",
    );

    const request = preparePredictionRun(state);

    expect(request).toMatchObject({
      ok: true,
      mode: "effnetb0",
      upload,
    });
  });

  test("transition handles run lifecycle events", () => {
    const ready = transitionPredictionWorkflow(
      transitionPredictionWorkflow(
        transitionPredictionWorkflow(createInitialPredictionWorkflowState(), {
          type: "mode-selected",
          mode: "effnetb0",
        }),
        {
          type: "upload-selected",
          file: file("scan-a.png", "image/png"),
          previewUrl: "blob:scan-a",
        },
      ),
      { type: "run-requested" },
    );

    expect(ready.isRunning).toBe(true);

    const completed = transitionPredictionWorkflow(ready, {
      type: "run-succeeded",
      prediction,
    });

    expect(completed).toMatchObject({
      isRunning: false,
      prediction,
      runError: null,
    });
  });
});
