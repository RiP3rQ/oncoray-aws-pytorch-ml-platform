import { expect, test } from "@playwright/test";
import {
  authenticatedStorageState,
  apiUrl,
  abortApiRequest,
  gotoAuthenticatedDashboard,
  mockApiJson,
  mockApiNoContent,
  mockApiText,
  mockAuthenticatedDashboard,
  mockModels,
  mockUser,
  readTokenState,
} from "./helpers";

test.use({ storageState: authenticatedStorageState });

test("shows current user email and selects first model by default", async ({
  page,
}) => {
  await mockAuthenticatedDashboard(page);
  await gotoAuthenticatedDashboard(page);

  await expect(page.getByText(mockUser.email)).toBeVisible();
  await expect(
    page.getByRole("tab", { name: mockModels[0].name }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText(mockModels[0].description)).toBeVisible();
  await expect(page.getByRole("tab", { name: "Compare both" })).toBeVisible();
});

test("clears session and redirects to login on logout", async ({ page }) => {
  await mockAuthenticatedDashboard(page);
  await gotoAuthenticatedDashboard(page);

  await page.getByRole("button", { name: "Log out" }).click();

  await expect(page).toHaveURL(/\/login$/);
  await expect(await readTokenState(page)).toEqual({
    local: null,
    session: null,
  });
});

test("shows clear fallback state when model API is down", async ({ page }) => {
  await mockApiJson(page, "/user/me", mockUser);
  await abortApiRequest(page, "/model/");
  await mockApiNoContent(page, "/user/logout");

  await gotoAuthenticatedDashboard(page);

  await expect(page.getByText(mockUser.email)).toBeVisible();
  await expect(page.getByText("Failed to load models")).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
});

test("clears token and redirects to login when current user request returns 401", async ({
  page,
}) => {
  await mockApiText(page, "/user/me", 401, "Expired");
  await mockApiJson(page, "/model/", mockModels);

  await gotoAuthenticatedDashboard(page);

  await expect(page).toHaveURL(/\/login$/);
  await expect(await readTokenState(page)).toEqual({
    local: null,
    session: null,
  });
});

test("clears token and redirects to login when model request returns 401", async ({
  page,
}) => {
  await mockApiJson(page, "/user/me", mockUser);
  await mockApiText(page, "/model/", 401, "Expired");
  await mockApiNoContent(page, "/user/logout");

  await gotoAuthenticatedDashboard(page);

  await expect(page).toHaveURL(/\/login$/);
  await expect(await readTokenState(page)).toEqual({
    local: null,
    session: null,
  });
});

test("shows retry state for model list failure and recovers after reload", async ({
  page,
}) => {
  let modelRequests = 0;

  await mockApiJson(page, "/user/me", mockUser);
  await page.route(apiUrl("/model/"), async (route) => {
    modelRequests += 1;

    if (modelRequests === 1) {
      await route.fulfill({
        status: 500,
        contentType: "text/plain",
        body: "Internal Server Error",
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mockModels),
    });
  });
  await mockApiNoContent(page, "/user/logout");

  await gotoAuthenticatedDashboard(page);

  await expect(page.getByText("Failed to load models")).toBeVisible();
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(
    page.getByRole("tab", { name: mockModels[0].name }),
  ).toBeVisible();
});

test("shows empty-state when no models are available", async ({ page }) => {
  await mockAuthenticatedDashboard(page, { models: [] });
  await gotoAuthenticatedDashboard(page);

  await expect(page.getByText("No models available")).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
});

test("hides compare mode and keeps upload runnable when only one model is available", async ({
  page,
}) => {
  await mockAuthenticatedDashboard(page, { models: [mockModels[0]] });
  await gotoAuthenticatedDashboard(page);

  await expect(
    page.getByRole("tab", { name: mockModels[0].name }),
  ).toBeVisible();
  await expect(page.getByRole("tab", { name: "Compare both" })).toHaveCount(0);

  await page.locator('input[type="file"]').setInputFiles({
    name: "single-model.png",
    mimeType: "image/png",
    buffer: Buffer.alloc(1536, 65),
  });
  await expect(
    page.getByRole("button", { name: "Run prediction" }),
  ).toBeEnabled();
});

test("switches model tabs and shows selected model description", async ({
  page,
}) => {
  await mockAuthenticatedDashboard(page);
  await gotoAuthenticatedDashboard(page);

  await page.getByRole("tab", { name: mockModels[1].name }).click();

  await expect(
    page.getByRole("tab", { name: mockModels[1].name }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(page.getByText(mockModels[1].description)).toBeVisible();
});

test("reloads user and models cleanly on authenticated refresh", async ({
  page,
}) => {
  let meRequests = 0;
  let modelRequests = 0;

  await page.route(apiUrl("/user/me"), async (route) => {
    meRequests += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mockUser),
    });
  });
  await page.route(apiUrl("/model/"), async (route) => {
    modelRequests += 1;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(mockModels),
    });
  });
  await mockApiNoContent(page, "/user/logout");

  await gotoAuthenticatedDashboard(page);
  await expect(page.getByText(mockUser.email)).toBeVisible();
  await expect(
    page.getByRole("tab", { name: mockModels[0].name }),
  ).toBeVisible();

  await page.reload();
  await expect(page.getByText(mockUser.email)).toBeVisible();
  await expect(
    page.getByRole("tab", { name: mockModels[0].name }),
  ).toBeVisible();
  expect(meRequests).toBeGreaterThanOrEqual(2);
  expect(modelRequests).toBeGreaterThanOrEqual(2);
});
