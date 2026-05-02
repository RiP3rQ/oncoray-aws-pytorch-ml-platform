import { expect, test } from "@playwright/test";
import {
  abortApiRequest,
  createUniqueE2EEmail,
  e2eUserPassword,
  gotoLogin,
  gotoRegister,
  mockApiNoContent,
  mockApiText,
  toastByText,
} from "./helpers";

async function submitLoginForm(
  page: import("@playwright/test").Page,
  email: string,
  password: string,
) {
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Log in to workspace" }).click();
}

async function submitRegisterForm(
  page: import("@playwright/test").Page,
  email: string,
  password: string,
) {
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill(password);
  await page.getByRole("button", { name: "Create workspace account" }).click();
}

test("shows invalid-credentials toast for login 401", async ({ page }) => {
  await mockApiText(page, "/user/token", 401, "Unauthorized");
  await gotoLogin(page);

  await submitLoginForm(page, "e2e+invalid@example.com", "wrong-password");

  await expect(page).toHaveURL(/\/login$/);
  await expect(toastByText(page, "Invalid credentials")).toHaveCount(1);
});

test("shows inline validation errors for empty and malformed login input", async ({
  page,
}) => {
  await gotoLogin(page);

  await page.getByRole("button", { name: "Log in to workspace" }).click();
  await expect(page.getByText("Enter a valid email address")).toBeVisible();
  await expect(page.getByText("Enter your password")).toBeVisible();

  await page.getByLabel("Email").fill("not-an-email");
  await page.getByLabel("Password").fill("valid-password");
  await page.getByRole("button", { name: "Log in to workspace" }).click();

  await expect(page.getByText("Enter a valid email address")).toBeVisible();
  await expect(page.getByText("Enter your password")).toHaveCount(0);
});

test("shows fallback toast for generic login network failure", async ({
  page,
}) => {
  await abortApiRequest(page, "/user/token");
  await gotoLogin(page);

  await submitLoginForm(page, "e2e+network@example.com", "valid-password");

  await expect(toastByText(page, "Network error. Try again.")).toHaveCount(1);
});

test("shows conflict toast for duplicate registration", async ({ page }) => {
  await mockApiText(page, "/user/signup", 409, "Email already registered");
  await gotoRegister(page);

  await submitRegisterForm(page, "e2e+duplicate@example.com", "Password123");

  await expect(toastByText(page, "Email already registered")).toHaveCount(1);
});

test("shows fallback toast for generic registration network failure", async ({
  page,
}) => {
  await abortApiRequest(page, "/user/signup");
  await gotoRegister(page);

  await submitRegisterForm(page, "e2e+register@example.com", "Password123");

  await expect(toastByText(page, "Network error. Try again.")).toHaveCount(1);
});

test("registers and redirects to login after accepted signup", async ({
  page,
}) => {
  const e2eUserEmail = createUniqueE2EEmail();

  await mockApiNoContent(page, "/user/signup");
  await gotoRegister(page);

  await submitRegisterForm(page, e2eUserEmail, e2eUserPassword);

  await expect(page).toHaveURL(/\/login$/, { timeout: 20_000 });
  await expect(
    page.getByRole("heading", {
      name: "Step back into chest X-ray review.",
    }),
  ).toBeVisible();
});
