import { expect, test } from "@playwright/test";
import {
  authenticatedStorageState,
  gotoAuthenticatedDashboard,
  makeFile,
  mockApiJson,
  mockApiNoContent,
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

// TODO: Replace mocked prediction coverage below with real API E2E coverage
// once prediction endpoint, model runtime, and storage flow are stable locally.
test.skip("runs real prediction happy path once prediction backend is ready for E2E", async () => {});

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

test("clears token and redirects to login when prediction returns 401", async ({
  page,
}) => {
  await mockApiJson(page, "/user/me", mockUser);
  await mockApiJson(page, "/model/", mockModels);
  await mockApiNoContent(page, "/user/logout");
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
        model_id: mockModels[1].id,
        prediction: "Normal",
        confidence: 0.91,
        image_s3_key: "uploads/scan-b.webp",
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

  expect(requestedPredictionUrl).toContain(
    `/model/${mockModels[1].id}/predict`,
  );
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
            model_id: mockModels[0].id,
            prediction: "Pneumonia",
            confidence: 0.88,
            image_s3_key: "uploads/scan-a.png",
          }
        : {
            model_id: mockModels[0].id,
            prediction: "Normal",
            confidence: 0.67,
            image_s3_key: "uploads/scan-b.png",
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
