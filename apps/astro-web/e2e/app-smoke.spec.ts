import { expect, test } from "@playwright/test";
import {
  createUniqueE2EEmail,
  e2eUserPassword,
  mockApiJson,
  mockModels,
  readTokenState,
  waitForAstroHydration,
} from "./helpers";

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

test("logs in, loads models, and logs out", async ({ page }) => {
  const e2eUserEmail = createUniqueE2EEmail();

  await mockApiJson(page, "/user/token", {
    access_token: "smoke-test-token",
    token_type: "bearer",
  });
  await mockApiJson(page, "/user/me", {
    id: "smoke-user-1",
    email: e2eUserEmail,
    created_at: "2026-04-06T18:00:00Z",
    updated_at: "2026-04-06T18:00:00Z",
  });
  await mockApiJson(page, "/model/", mockModels);

  await page.goto("/login");
  await waitForAstroHydration(page);

  await page.getByLabel("Email").fill(e2eUserEmail);
  await page.getByLabel("Password").fill(e2eUserPassword);
  await page.getByRole("button", { name: "Log in to workspace" }).click();

  await expect(page).toHaveURL("/");
  await expect(page.getByText(e2eUserEmail)).toBeVisible();
  await expect(page.getByRole("tab", { name: "EffNetB0" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "EffNetB0" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(page.getByRole("tab", { name: "ViTB16" })).toBeVisible();

  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(
    page.getByRole("heading", {
      name: "Step back into chest X-ray review.",
    }),
  ).toBeVisible();
  await expect(await readTokenState(page)).toEqual({
    local: null,
    session: null,
  });
});
