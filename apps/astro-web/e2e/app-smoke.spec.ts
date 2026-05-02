import { expect, test } from "@playwright/test";
import {
  cleanupTestUser,
  createUniqueE2EEmail,
  createVerifiedTestUser,
  e2eUserPassword,
  readTokenState,
  requireRealApi,
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

test("logs in against real API, loads models, and logs out", async ({
  page,
  request,
}) => {
  await requireRealApi(request);

  const e2eUserEmail = createUniqueE2EEmail();

  await createVerifiedTestUser(request, e2eUserEmail);

  try {
    await page.goto("/login");
    await waitForAstroHydration(page);

    await page.getByLabel("Email").fill(e2eUserEmail);
    await page.getByLabel("Password").fill(e2eUserPassword);
    await page.getByRole("button", { name: "Log in to workspace" }).click();

    await expect(page).toHaveURL("/");
    await expect(page.getByText(e2eUserEmail)).toBeVisible();
    await expect(
      page.getByRole("tab", { name: "VIT optical model" }),
    ).toBeVisible();
    await expect(
      page.getByRole("tab", { name: "VIT optical model" }),
    ).toHaveAttribute("aria-selected", "true");
    await expect(
      page.getByRole("tab", { name: "EffectiveNetB2" }),
    ).toBeVisible();

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
  } finally {
    await cleanupTestUser(request, e2eUserEmail);
  }
});
