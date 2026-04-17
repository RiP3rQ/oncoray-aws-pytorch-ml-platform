import {
  expect,
  type APIRequestContext,
  type Locator,
  type Page,
} from "@playwright/test";

export const apiBaseUrl = (
  process.env.E2E_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");
export const tokenKey = "oncoray_token";
export const e2eUserPassword = "E2E-password-123";
export const mockToken = "mock-access-token";
export const frontendUrl = "http://localhost:4321";

export const mockUser = Object.freeze({
  id: "e2e-user-1",
  email: "e2e+mock@example.com",
  created_at: "2026-04-06T18:00:00Z",
  updated_at: "2026-04-06T18:00:00Z",
});

export const mockModels = Object.freeze([
  {
    id: "22222222-2222-2222-2222-222222222222",
    name: "EffNetB0",
    slug: "effnetb0",
    description: "EfficientNet-B0 classifier for chest X-ray inference.",
    version: "1.0.0",
    created_at: "2026-04-06T18:00:00Z",
    updated_at: "2026-04-06T18:00:00Z",
  },
  {
    id: "11111111-1111-1111-1111-111111111111",
    name: "ViTB16",
    slug: "vitb16",
    description:
      "Vision Transformer B/16 classifier for chest X-ray inference.",
    version: "1.0.0",
    created_at: "2026-04-06T18:00:00Z",
    updated_at: "2026-04-06T18:00:00Z",
  },
]);

export const authenticatedStorageState = {
  cookies: [],
  origins: [
    {
      origin: frontendUrl,
      localStorage: [{ name: tokenKey, value: mockToken }],
    },
  ],
} as const;

export function apiUrl(path: string): string {
  return new URL(path, apiBaseUrl).toString();
}

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function predictionRoutePattern(): RegExp {
  return new RegExp(
    `^${escapeRegex(apiBaseUrl)}/predict\\?model=(effnetb0|vitb16|both)$`,
  );
}

export async function waitForAstroHydration(page: Page) {
  await page.waitForFunction(() =>
    Array.from(document.querySelectorAll("astro-island")).every(
      (element) => !element.hasAttribute("ssr"),
    ),
  );
}

export async function gotoDashboard(page: Page) {
  await page.goto("/");
  await waitForAstroHydration(page);
}

export async function gotoAuthenticatedDashboard(page: Page) {
  await gotoDashboard(page);

  if (!page.url().endsWith("/login")) {
    return;
  }

  const tokenState = await readTokenState(page);
  if (!tokenState.local && !tokenState.session) {
    return;
  }

  await gotoDashboard(page);
}

export async function gotoLogin(page: Page) {
  await page.goto("/login");
  await waitForAstroHydration(page);
}

export async function gotoRegister(page: Page) {
  await page.goto("/register");
  await waitForAstroHydration(page);
}

export function createUniqueE2EEmail() {
  return `e2e+${Date.now()}-${Math.random().toString(36).slice(2, 10)}@example.com`;
}

export async function createVerifiedTestUser(
  request: APIRequestContext,
  email: string,
) {
  const response = await request.post(apiUrl("/user/e2e/test-user"), {
    data: {
      email,
      password: e2eUserPassword,
    },
  });

  expect(response.ok()).toBeTruthy();
}

export async function cleanupTestUser(
  request: APIRequestContext,
  email: string,
) {
  await request.delete(apiUrl("/user/e2e/test-user"), {
    params: { email },
  });
}

export async function seedToken(
  page: Page,
  token = mockToken,
  persistent = true,
) {
  await page.goto("/login");
  await waitForAstroHydration(page);
  await page.evaluate(
    ({ storedToken, keepSignedIn, storageKey }) => {
      const storage = keepSignedIn
        ? window.localStorage
        : window.sessionStorage;
      storage.setItem(storageKey, storedToken);
    },
    {
      storedToken: token,
      keepSignedIn: persistent,
      storageKey: tokenKey,
    },
  );
  await expect(await readTokenState(page)).toEqual({
    local: persistent ? token : null,
    session: persistent ? null : token,
  });
}

export async function readTokenState(page: Page) {
  return page.evaluate(
    ({ storageKey }) => ({
      local: window.localStorage.getItem(storageKey),
      session: window.sessionStorage.getItem(storageKey),
    }),
    { storageKey: tokenKey },
  );
}

export async function mockApiJson(
  page: Page,
  path: string,
  body: unknown,
  status = 200,
) {
  await page.route(apiUrl(path), async (route) => {
    await route.fulfill({
      status,
      contentType: "application/json",
      body: JSON.stringify(body),
    });
  });
}

export async function mockApiText(
  page: Page,
  path: string,
  status: number,
  body = "",
) {
  await page.route(apiUrl(path), async (route) => {
    await route.fulfill({
      status,
      contentType: "text/plain",
      body,
    });
  });
}

export async function mockApiNoContent(page: Page, path: string, status = 204) {
  await page.route(apiUrl(path), async (route) => {
    await route.fulfill({
      status,
      body: "",
    });
  });
}

export async function abortApiRequest(page: Page, path: string) {
  await page.route(apiUrl(path), async (route) => {
    await route.abort("failed");
  });
}

export async function mockAuthenticatedDashboard(
  page: Page,
  options: {
    user?: typeof mockUser;
    models?: typeof mockModels | [];
  } = {},
) {
  await mockApiJson(page, "/user/me", options.user ?? mockUser);
  await mockApiJson(page, "/model/", options.models ?? mockModels);
  await mockApiNoContent(page, "/user/logout");
}

export function toastByText(page: Page, message: string): Locator {
  return page.locator("[data-sonner-toast]").filter({ hasText: message });
}

export function makeFile(
  name: string,
  mimeType: string,
  size = 1536,
): {
  name: string;
  mimeType: string;
  buffer: Buffer;
} {
  return {
    name,
    mimeType,
    buffer: Buffer.alloc(size, 65),
  };
}

export async function tabUntilFocused(
  page: Page,
  target: Locator,
  maxTabs = 12,
) {
  for (let index = 0; index < maxTabs; index += 1) {
    await page.keyboard.press("Tab");

    const focused = await target.evaluate(
      (element) => element === document.activeElement,
    );
    if (focused) {
      return;
    }
  }

  throw new Error("Failed to focus target with keyboard navigation.");
}
