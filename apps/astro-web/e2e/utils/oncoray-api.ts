import type { Page, Route } from "@playwright/test";
import type { ModelRead, PredictionResponse } from "@/lib/api";
import type { User } from "@/lib/auth";

const timestamp = "2026-04-16T10:00:00.000Z";

export const defaultUser: User = {
  id: "user-1",
  email: "radiology.team@hospital.org",
  created_at: timestamp,
  updated_at: timestamp,
};

export const defaultModels: ModelRead[] = [
  {
    id: "model-1",
    name: "PneumoniaNet v2",
    description:
      "Primary chest X-ray pneumonia classifier for workspace triage.",
    version: "2.1.0",
    created_at: timestamp,
    updated_at: timestamp,
  },
  {
    id: "model-2",
    name: "PneumoniaNet v1",
    description: "Fallback baseline model kept for regression comparison.",
    version: "1.6.4",
    created_at: timestamp,
    updated_at: timestamp,
  },
];

export const defaultPrediction: PredictionResponse = {
  model_id: "model-1",
  prediction: "Pneumonia",
  confidence: 0.92,
  image_s3_key: "uploads/test/chest-xray.png",
};

async function fulfillJson(route: Route, body: unknown, status = 200) {
  if (status === 204 || body === undefined) {
    await route.fulfill({ status, body: "" });
    return;
  }

  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

interface MockWorkspaceApiOptions {
  user?: User;
  models?: ModelRead[];
  prediction?: PredictionResponse;
}

export async function mockWorkspaceApi(
  page: Page,
  options: MockWorkspaceApiOptions = {},
) {
  const user = options.user ?? defaultUser;
  const models = options.models ?? defaultModels;
  const prediction = options.prediction ?? defaultPrediction;

  await page.route("**/*", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const { pathname } = url;

    if (pathname === "/user/token" && request.method() === "POST") {
      await fulfillJson(route, {
        access_token: "playwright-token",
        token_type: "bearer",
      });
      return;
    }

    if (pathname === "/user/me" && request.method() === "GET") {
      await fulfillJson(route, user);
      return;
    }

    if (pathname === "/user/logout" && request.method() === "GET") {
      await fulfillJson(route, undefined, 204);
      return;
    }

    if (pathname === "/user/signup" && request.method() === "POST") {
      await fulfillJson(route, undefined, 201);
      return;
    }

    if (pathname === "/model/" && request.method() === "GET") {
      await fulfillJson(route, models);
      return;
    }

    if (
      pathname.startsWith("/model/") &&
      pathname.endsWith("/predict") &&
      request.method() === "POST"
    ) {
      await fulfillJson(route, prediction);
      return;
    }

    await route.continue();
  });
}

export async function seedAuthenticatedSession(
  page: Page,
  token = "playwright-token",
) {
  await page.addInitScript(
    ({ storedToken }) => {
      window.localStorage.setItem("oncoray_token", storedToken);
    },
    { storedToken: token },
  );
}
