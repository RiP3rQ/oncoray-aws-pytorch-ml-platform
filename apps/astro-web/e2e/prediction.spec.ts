import { expect, test } from "@playwright/test";
import {
  authenticatedStorageState,
  gotoAuthenticatedDashboard,
  makeFile,
  mockApiJson,
  mockAuthenticatedDashboard,
  mockModels,
  mockUser,
  predictionRoutePattern,
  readTokenState,
  toastByText,
} from "./helpers";

test.use({ storageState: authenticatedStorageState });

async function openMockedDashboard(page: import("@playwright/test").Page) {
  await mockAuthenticatedDashboard(page);
  await gotoAuthenticatedDashboard(page);
  await expect(page.getByText(mockUser.email)).toBeVisible();
}

test("runs prediction happy path", async ({ page }) => {
  await page.route(predictionRoutePattern(), async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        request_id: "request-happy-path",
        mode: "effnetb0",
        upload: { status: "ok", image_s3_key: "uploads/scan-happy.png" },
        results: {
          effnetb0: {
            status: "ok",
            prediction: "Normal",
            confidence: 0.95,
          },
        },
      }),
    });
  });
  await openMockedDashboard(page);

  await page
    .locator('input[type="file"]')
    .setInputFiles(makeFile("scan-happy.png", "image/png"));
  await page.getByRole("button", { name: "Run prediction" }).click();

  await expect(page.getByText("Normal", { exact: true })).toBeVisible();
  await expect(page.getByText("95.0%", { exact: true })).toBeVisible();
  await expect(page.getByText("uploads/scan-happy.png")).toBeVisible();
  await expect(toastByText(page, "Prediction complete.")).toHaveCount(1);
});

test("keeps upload disabled until supported image is selected", async ({
  page,
}) => {
  await openMockedDashboard(page);

  const uploadButton = page.getByRole("button", { name: "Run prediction" });
  await expect(uploadButton).toBeDisabled();

  await page
    .locator('input[type="file"]')
    .setInputFiles(makeFile("scan-a.png", "image/png"));

  await expect(uploadButton).toBeEnabled();
});

test("keeps upload disabled when no model is available", async ({ page }) => {
  await mockAuthenticatedDashboard(page, { models: [] });
  await gotoAuthenticatedDashboard(page);

  await page
    .locator('input[type="file"]')
    .setInputFiles(makeFile("scan-a.png", "image/png"));

  await expect(
    page.getByText("Select a model before running classification."),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Run prediction" }),
  ).toBeDisabled();
});

test("shows validation message for oversized image before prediction request", async ({
  page,
}) => {
  await openMockedDashboard(page);

  await page
    .locator('input[type="file"]')
    .setInputFiles(
      makeFile("large-scan.jpg", "image/jpeg", 2 * 1024 * 1024 + 1),
    );

  await expect(page.getByText("Image exceeds 2 MB limit.")).toBeVisible();
  await expect(page.getByText("No file selected")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Run prediction" }),
  ).toBeDisabled();
});

test("shows validation message for unsupported file type", async ({ page }) => {
  await openMockedDashboard(page);

  await page.locator('input[type="file"]').setInputFiles({
    name: "notes.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("not-an-image"),
  });

  await expect(page.getByText("Use a PNG, JPG, or WEBP image.")).toBeVisible();
  await expect(page.getByText("No file selected")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Run prediction" }),
  ).toBeDisabled();
});

test("removes selected image preview and metadata", async ({ page }) => {
  const firstImage = makeFile("scan-a.png", "image/png", 1536);

  await openMockedDashboard(page);
  await page.locator('input[type="file"]').setInputFiles(firstImage);

  await expect(page.getByAltText("scan-a.png")).toBeVisible();
  await expect(page.getByText("scan-a.png", { exact: true })).toBeVisible();
  await expect(page.getByText("1.5 KB")).toBeVisible();

  await page.getByRole("button", { name: "Remove image" }).click();

  await expect(page.getByAltText("scan-a.png")).toHaveCount(0);
  await expect(page.getByText("No file selected")).toBeVisible();
  await expect(page.getByText("-", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Run prediction" }),
  ).toBeDisabled();
});

test("replaces selected image preview and metadata", async ({ page }) => {
  await openMockedDashboard(page);

  await page
    .locator('input[type="file"]')
    .setInputFiles(makeFile("scan-a.png", "image/png", 1536));
  await expect(page.getByAltText("scan-a.png")).toBeVisible();
  await expect(page.getByText("1.5 KB")).toBeVisible();

  await page
    .locator('input[type="file"]')
    .setInputFiles(makeFile("scan-b.webp", "image/webp", 4096));

  await expect(page.getByAltText("scan-b.webp")).toBeVisible();
  await expect(page.getByAltText("scan-a.png")).toHaveCount(0);
  await expect(page.getByText("scan-b.webp", { exact: true })).toBeVisible();
  await expect(page.getByText("4.0 KB")).toBeVisible();
});

test("shows processing state and locks image controls while prediction runs", async ({
  page,
}) => {
  let releasePrediction!: () => void;
  const predictionReleased = new Promise<void>((resolve) => {
    releasePrediction = resolve;
  });

  await page.route(predictionRoutePattern(), async (route) => {
    await predictionReleased;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        request_id: "request-processing",
        mode: "effnetb0",
        upload: { status: "ok", image_s3_key: "uploads/processing.png" },
        results: {
          effnetb0: {
            status: "ok",
            prediction: "Normal",
            confidence: 0.82,
          },
        },
      }),
    });
  });
  await openMockedDashboard(page);

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(makeFile("processing.png", "image/png"));
  await page.getByRole("button", { name: "Run prediction" }).click();

  await expect(
    page.getByRole("button", { name: "Processing..." }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Remove image" }),
  ).toBeDisabled();
  await expect(fileInput).toBeDisabled();

  releasePrediction();
  await expect(page.getByText("uploads/processing.png")).toBeVisible();
});

test("clears token and redirects to login when prediction returns 401", async ({
  page,
}) => {
  await mockApiJson(page, "/user/me", mockUser);
  await mockApiJson(page, "/model/", mockModels);
  await page.route(predictionRoutePattern(), async (route) => {
    await route.fulfill({
      status: 401,
      contentType: "text/plain",
      body: "Expired",
    });
  });

  await gotoAuthenticatedDashboard(page);
  await page
    .locator('input[type="file"]')
    .setInputFiles(makeFile("scan-a.png", "image/png"));
  await page.getByRole("button", { name: "Run prediction" }).click();

  await expect(page).toHaveURL(/\/login$/);
  await expect(await readTokenState(page)).toEqual({
    local: null,
    session: null,
  });
});

test("shows image-size toast when prediction returns 413", async ({ page }) => {
  await page.route(predictionRoutePattern(), async (route) => {
    await route.fulfill({
      status: 413,
      contentType: "text/plain",
      body: "too large",
    });
  });
  await openMockedDashboard(page);

  await page
    .locator('input[type="file"]')
    .setInputFiles(makeFile("scan-a.png", "image/png"));
  await page.getByRole("button", { name: "Run prediction" }).click();

  await expect(toastByText(page, "Image exceeds 2 MB limit.")).toHaveCount(1);
});

test("shows fallback toast for generic prediction failure", async ({
  page,
}) => {
  await page.route(predictionRoutePattern(), async (route) => {
    await route.abort("failed");
  });
  await openMockedDashboard(page);

  await page
    .locator('input[type="file"]')
    .setInputFiles(makeFile("scan-a.png", "image/png"));
  await page.getByRole("button", { name: "Run prediction" }).click();

  await expect(toastByText(page, "Network error. Try again.")).toHaveCount(1);
});

test("sends prediction request with active tab model", async ({ page }) => {
  let requestedPredictionUrl = "";

  await page.route(predictionRoutePattern(), async (route) => {
    requestedPredictionUrl = route.request().url();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        request_id: "request-1",
        mode: "vitb16",
        upload: { status: "ok", image_s3_key: "uploads/scan-b.webp" },
        results: {
          vitb16: {
            status: "ok",
            prediction: "Normal",
            confidence: 0.91,
          },
        },
      }),
    });
  });
  await openMockedDashboard(page);

  const secondTab = page.getByRole("tab", { name: mockModels[1].name });
  await secondTab.click();
  await expect(secondTab).toHaveAttribute("aria-selected", "true");

  await page
    .locator('input[type="file"]')
    .setInputFiles(makeFile("scan-b.webp", "image/webp"));
  await page.getByRole("button", { name: "Run prediction" }).click();

  expect(requestedPredictionUrl).toContain("/predict?model=vitb16");
  await expect(page.getByText("Normal", { exact: true })).toBeVisible();
});

test("overwrites previous prediction result after new upload", async ({
  page,
}) => {
  let predictionRequests = 0;

  await page.route(predictionRoutePattern(), async (route) => {
    predictionRequests += 1;

    const body =
      predictionRequests === 1
        ? {
            request_id: "request-1",
            mode: "effnetb0",
            upload: { status: "ok", image_s3_key: "uploads/scan-a.png" },
            results: {
              effnetb0: {
                status: "ok",
                prediction: "Pneumonia",
                confidence: 0.88,
              },
            },
          }
        : {
            request_id: "request-2",
            mode: "effnetb0",
            upload: { status: "ok", image_s3_key: "uploads/scan-b.png" },
            results: {
              effnetb0: {
                status: "ok",
                prediction: "Normal",
                confidence: 0.67,
              },
            },
          };

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
  await openMockedDashboard(page);

  await page
    .locator('input[type="file"]')
    .setInputFiles(makeFile("scan-a.png", "image/png"));
  await page.getByRole("button", { name: "Run prediction" }).click();
  await expect(page.getByText("Pneumonia", { exact: true })).toBeVisible();
  await expect(page.getByText("uploads/scan-a.png")).toBeVisible();

  await page
    .locator('input[type="file"]')
    .setInputFiles(makeFile("scan-b.png", "image/png"));
  await page.getByRole("button", { name: "Run prediction" }).click();

  await expect(page.getByText("Normal", { exact: true })).toBeVisible();
  await expect(page.getByText("uploads/scan-b.png")).toBeVisible();
  await expect(page.getByText("uploads/scan-a.png")).toHaveCount(0);
});

test("supports drag-and-drop upload path", async ({ page }) => {
  const dragFile = makeFile("dragged.png", "image/png");

  await openMockedDashboard(page);

  const dataTransfer = await page.evaluateHandle(
    ({ fileName, fileType, fileBytes }) => {
      const dataTransfer = new DataTransfer();
      const file = new File([Uint8Array.from(fileBytes)], fileName, {
        type: fileType,
      });
      dataTransfer.items.add(file);
      return dataTransfer;
    },
    {
      fileName: dragFile.name,
      fileType: dragFile.mimeType,
      fileBytes: Array.from(dragFile.buffer),
    },
  );

  const dropzone = page
    .locator("label")
    .filter({ hasText: "Drop chest X-ray image here" })
    .first();

  await dropzone.dispatchEvent("dragover", { dataTransfer });
  await dropzone.dispatchEvent("drop", { dataTransfer });

  await expect(page.getByText("dragged.png", { exact: true })).toBeVisible();
  await expect(
    page.getByText(
      "Image ready. Review details below and run prediction when ready.",
    ),
  ).toBeVisible();
});

test("shows both model cards in compare mode", async ({ page }) => {
  await page.route(predictionRoutePattern(), async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        request_id: "request-compare",
        mode: "both",
        upload: { status: "ok", image_s3_key: "uploads/scan-compare.png" },
        results: {
          effnetb0: {
            status: "ok",
            prediction: "Normal",
            confidence: 0.93,
          },
          vitb16: {
            status: "error",
            error: "timeout",
          },
        },
      }),
    });
  });
  await openMockedDashboard(page);

  await page.getByRole("tab", { name: "Compare both" }).click();
  await page
    .locator('input[type="file"]')
    .setInputFiles(makeFile("scan-compare.png", "image/png"));
  await page.getByRole("button", { name: "Run prediction" }).click();

  const resultPanel = page
    .locator('[aria-live="polite"]')
    .filter({ hasText: "Classification result" });

  await expect(
    resultPanel.getByText("EffNetB0", { exact: true }),
  ).toBeVisible();
  await expect(resultPanel.getByText("ViTB16", { exact: true })).toBeVisible();
  await expect(resultPanel.getByText("timeout")).toBeVisible();
  await expect(toastByText(page, "Compare run complete.")).toHaveCount(1);
});

test("keeps Prediction result content inside its panel at responsive widths", async ({
  page,
}) => {
  await page.route(predictionRoutePattern(), async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        request_id: "request-overflow",
        mode: "both",
        upload: {
          status: "ok",
          image_s3_key:
            "uploads/patient-study-with-long-reference-name-2026-05-02.png",
        },
        results: {
          effnetb0: {
            status: "ok",
            prediction: "Pneumonia",
            confidence: 1.24,
          },
          vitb16: {
            status: "error",
            error: "runtime-timeout-after-model-warmup",
          },
        },
      }),
    });
  });

  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await openMockedDashboard(page);

    await page.getByRole("tab", { name: "Compare both" }).click();
    await page
      .locator('input[type="file"]')
      .setInputFiles(makeFile("scan-overflow.png", "image/png"));
    await page.getByRole("button", { name: "Run prediction" }).click();

    const resultPanel = page
      .locator('[aria-live="polite"]')
      .filter({ hasText: "Classification result" });

    await expect(resultPanel).toBeVisible();
    await expect(page.getByText("124.0%", { exact: true })).toBeVisible();

    const overflow = await resultPanel.evaluate((panel) => {
      const viewportOverflow =
        document.documentElement.scrollWidth -
        document.documentElement.clientWidth;
      const panelOverflow = panel.scrollWidth - panel.clientWidth;
      const panelRect = panel.getBoundingClientRect();
      const progressBars = Array.from(
        panel.querySelectorAll('[role="progressbar"]'),
      );

      return {
        viewportOverflow,
        panelOverflow,
        progressBarsInsidePanel: progressBars.every((progressBar) => {
          const rect = progressBar.getBoundingClientRect();
          return (
            rect.left >= panelRect.left - 1 && rect.right <= panelRect.right + 1
          );
        }),
      };
    });

    expect(overflow.viewportOverflow).toBeLessThanOrEqual(1);
    expect(overflow.panelOverflow).toBeLessThanOrEqual(1);
    expect(overflow.progressBarsInsidePanel).toBe(true);
  }
});

test("shows upload persistence warning when prediction succeeds without stored upload", async ({
  page,
}) => {
  await page.route(predictionRoutePattern(), async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        request_id: "request-upload-warning",
        mode: "effnetb0",
        upload: { status: "error" },
        results: {
          effnetb0: {
            status: "ok",
            prediction: "Pneumonia",
            confidence: 0.74,
          },
        },
      }),
    });
  });
  await openMockedDashboard(page);

  await page
    .locator('input[type="file"]')
    .setInputFiles(makeFile("not-persisted.webp", "image/webp"));
  await page.getByRole("button", { name: "Run prediction" }).click();

  await expect(page.getByText("Pneumonia", { exact: true })).toBeVisible();
  await expect(page.getByText("Upload not persisted")).toBeVisible();
});
