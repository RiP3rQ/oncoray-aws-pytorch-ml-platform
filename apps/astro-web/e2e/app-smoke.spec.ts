import { expect, test } from "@playwright/test";

const apiBaseUrl = process.env.E2E_API_BASE_URL ?? "http://localhost:8000";
const e2eUserPassword = "E2E-password-123";

async function waitForAstroHydration(page: import("@playwright/test").Page) {
  await page.waitForFunction(() =>
    Array.from(document.querySelectorAll("astro-island")).every(
      (element) => !element.hasAttribute("ssr"),
    ),
  );
}

function createUniqueE2EEmail() {
  return `e2e+${Date.now()}-${Math.random().toString(36).slice(2, 10)}@example.com`;
}

async function createVerifiedTestUser(
  request: import("@playwright/test").APIRequestContext,
  email: string,
) {
  const response = await request.post(`${apiBaseUrl}/user/e2e/test-user`, {
    data: {
      email,
      password: e2eUserPassword,
    },
  });

  expect(response.ok()).toBeTruthy();
}

async function cleanupTestUser(
  request: import("@playwright/test").APIRequestContext,
  email: string,
) {
  await request.delete(`${apiBaseUrl}/user/e2e/test-user`, {
    params: { email },
  });
}

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
      page.getByRole("tab", { name: "EffectiveNetB2" }),
    ).toBeVisible();

    await page.getByRole("button", { name: "Log out" }).click();
    await expect(page).toHaveURL(/\/login$/);
  } finally {
    await cleanupTestUser(request, e2eUserEmail);
  }
});
