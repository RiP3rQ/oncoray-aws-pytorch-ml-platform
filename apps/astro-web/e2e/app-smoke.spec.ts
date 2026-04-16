import { Buffer } from "node:buffer";
import { expect, test } from "@playwright/test";
import { mockWorkspaceApi } from "./utils/oncoray-api";

const samplePngBase64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9sWwae8AAAAASUVORK5CYII=";

test("redirects unauthenticated workspace access to login", async ({
  page,
}) => {
  await page.goto("/");

  await expect(page).toHaveURL(/\/login$/);
  await expect(
    page.getByRole("heading", {
      name: "Step back into chest X-ray review.",
    }),
  ).toBeVisible();
});

test("logs in and completes prediction flow against mocked API", async ({
  page,
}) => {
  await mockWorkspaceApi(page);
  await page.goto("/login");

  await page.getByLabel("Email").fill("radiology.team@hospital.org");
  await page.getByLabel("Password").fill("StrongPass123!");
  await page.getByRole("button", { name: "Log in to workspace" }).click();

  await expect(page).toHaveURL("/");
  await expect(page.getByText("radiology.team@hospital.org")).toBeVisible();
  await expect(
    page.getByRole("tab", { name: "PneumoniaNet v2" }),
  ).toBeVisible();

  await page.locator('input[type="file"]').setInputFiles({
    name: "chest-xray.png",
    mimeType: "image/png",
    buffer: Buffer.from(samplePngBase64, "base64"),
  });

  await expect(page.getByText("chest-xray.png")).toBeVisible();
  const runPredictionButton = page.getByRole("button", {
    name: "Run prediction",
  });

  await expect(runPredictionButton).toBeEnabled();
  await runPredictionButton.click();

  const predictionCard = page.locator(".prediction-card");

  await expect(
    predictionCard.getByText("Latest upload scored and stored."),
  ).toBeVisible();
  await expect(predictionCard.getByText("Pneumonia")).toBeVisible();
  await expect(predictionCard.getByText("92.0%")).toBeVisible();
  await expect(
    predictionCard.getByText("uploads/test/chest-xray.png"),
  ).toBeVisible();
});
