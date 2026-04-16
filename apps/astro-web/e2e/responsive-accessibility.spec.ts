import { expect, test } from "@playwright/test";
import {
  gotoAuthenticatedDashboard,
  gotoLogin,
  gotoRegister,
  mockApiJson,
  mockApiText,
  mockModels,
  mockUser,
  seedToken,
  tabUntilFocused,
  toastByText,
} from "./helpers";

test.describe("mobile smoke", () => {
  test.use({
    viewport: { width: 390, height: 844 },
    hasTouch: true,
    isMobile: true,
  });

  test("renders login, register, and dashboard shell on mobile", async ({
    page,
  }) => {
    await gotoLogin(page);
    await expect(
      page.getByRole("heading", {
        name: "Step back into chest X-ray review.",
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Log in to workspace" }),
    ).toBeVisible();

    await gotoRegister(page);
    await expect(
      page.getByRole("heading", {
        name: "Open a secure lane for incoming chest X-rays.",
      }),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Create workspace account" }),
    ).toBeVisible();

    await seedToken(page);
    await mockApiJson(page, "/user/me", mockUser);
    await mockApiJson(page, "/model/", mockModels);
    await gotoAuthenticatedDashboard(page);
    await expect(page.getByText(mockUser.email)).toBeVisible();
    await expect(page.getByText("Chest X-ray upload")).toBeVisible();
  });
});

test("supports keyboard-only login flow", async ({ page }) => {
  await mockApiJson(page, "/user/token", {
    access_token: "mock-access-token",
    token_type: "bearer",
  });
  await mockApiJson(page, "/user/me", mockUser);
  await mockApiJson(page, "/model/", mockModels);
  await gotoLogin(page);

  const emailInput = page.getByLabel("Email");
  const passwordInput = page.getByLabel("Password");
  const submitButton = page.getByRole("button", {
    name: "Log in to workspace",
  });

  await tabUntilFocused(page, emailInput);
  await page.keyboard.type(mockUser.email);
  await tabUntilFocused(page, passwordInput);
  await page.keyboard.type("Password123");
  await tabUntilFocused(page, submitButton);
  await page.keyboard.press("Enter");

  await expect(page).toHaveURL("/");
  await expect(page.getByText(mockUser.email)).toBeVisible();
});

test("shows one toast per failed login action without duplicates after rerender", async ({
  page,
}) => {
  await mockApiText(page, "/user/token", 401, "Unauthorized");
  await gotoLogin(page);

  await page.getByLabel("Email").fill("e2e+toast@example.com");
  await page.getByLabel("Password").fill("wrong-password");
  await page.getByRole("button", { name: "Log in to workspace" }).click();

  const invalidToast = toastByText(page, "Invalid credentials");
  await expect(invalidToast).toHaveCount(1);

  await page.getByLabel("Password").fill("wrong-password-2");
  await expect(invalidToast).toHaveCount(1);
});
