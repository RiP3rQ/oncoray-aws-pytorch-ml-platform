import * as Sentry from "@sentry/astro";
import { expireBrowserSession, getStoredToken } from "./auth-session.js";
import type { components } from "./generated/api-types";

const configuredApiBaseUrl = (import.meta.env.PUBLIC_API_BASE_URL ?? "")
  .trim()
  .replace(/\/$/, "");
const API_BASE_URL = configuredApiBaseUrl || "http://localhost:8000";

// Paths that should bypass the 401 auto-redirect (they handle errors themselves)
const AUTH_PATHS = ["/user/token", "/user/signup"];
const BAD_CREDENTIALS_PATH = "/user/token";

interface ApiOptions extends RequestInit {
  params?: Record<string, string>;
}

export interface ApiRequestErrorContext {
  method: string;
  path: string;
  url: string;
  status?: number;
}

type ApiRequestErrorReporter = (
  error: unknown,
  context: ApiRequestErrorContext,
) => void;

let reportApiRequestError: ApiRequestErrorReporter = (
  error,
  { method, path, url, status },
) => {
  Sentry.captureException(error, {
    tags: {
      api_request_failed: "true",
      api_request_method: method,
      api_request_path: path,
    },
    extra: {
      url,
      status,
    },
  });
};

export function setApiRequestErrorReporterForTests(
  reporter: ApiRequestErrorReporter,
): () => void {
  const previous = reportApiRequestError;
  reportApiRequestError = reporter;
  return () => {
    reportApiRequestError = previous;
  };
}

async function request<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { params, headers: customHeaders, ...rest } = options;

  const url = new URL(path, API_BASE_URL || window.location.origin);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      url.searchParams.set(key, value);
    });
  }

  const token = getStoredToken();
  const headers = new Headers(customHeaders);

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  if (!headers.has("Content-Type") && !(rest.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const method = rest.method ?? "GET";
  const requestContext: ApiRequestErrorContext = {
    method,
    path,
    url: url.toString(),
  };

  let response: Response;
  try {
    response = await fetch(url.toString(), {
      ...rest,
      headers,
    });
  } catch (error) {
    reportApiRequestError(error, requestContext);
    throw error;
  }

  if (response.status === 401) {
    // Auth endpoints handle their own 401s — let the error propagate
    const isAuthPath = AUTH_PATHS.some((p) => path.startsWith(p));

    if (!isAuthPath) {
      expireBrowserSession();
    }

    const message = path.startsWith(BAD_CREDENTIALS_PATH)
      ? "Bad credentials login failure."
      : "Session expired. Please log in again.";
    const error = new ApiError(response.status, message, requestContext);
    reportApiRequestError(error, {
      ...requestContext,
      status: response.status,
    });
    throw error;
  }

  if (!response.ok) {
    const errorBody = await response.text().catch(() => "");
    const error = new ApiError(
      response.status,
      errorBody || response.statusText,
      requestContext,
    );
    reportApiRequestError(error, {
      ...requestContext,
      status: response.status,
    });
    throw error;
  }

  if (
    response.status === 204 ||
    response.headers.get("content-length") === "0"
  ) {
    return undefined as T;
  }

  try {
    return await response.json();
  } catch (error) {
    reportApiRequestError(error, {
      ...requestContext,
      status: response.status,
    });
    throw error;
  }
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public request?: ApiRequestErrorContext,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// Auth endpoints
export function login(
  email: string,
  password: string,
): Promise<{ access_token: string; token_type: string }> {
  return request("/user/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username: email, password }),
  });
}

export function signup(email: string, password: string): Promise<void> {
  return request("/user/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export function getMe(): Promise<{
  id: string;
  email: string;
  created_at: string;
  updated_at: string;
}> {
  return request("/user/me", { method: "GET" });
}

// Model endpoints
export type ModelRead = components["schemas"]["ModelRead"];

export function getModels(): Promise<ModelRead[]> {
  return request("/model/", { method: "GET" });
}

export function getModel(modelId: string): Promise<ModelRead> {
  return request(`/model/${modelId}`, { method: "GET" });
}

export type ModelSlug = components["schemas"]["ModelSlug"];
export type PredictionMode = components["schemas"]["PredictionMode"];
export type PredictionUploadStatus =
  components["schemas"]["PredictionUploadStatus"];
export type PredictionResultStatus =
  components["schemas"]["PredictionResultStatus"];
export type UnifiedPredictionResponse =
  components["schemas"]["UnifiedPredictionResponse"];
export type Prediction = UnifiedPredictionResponse;

export function predict(
  mode: PredictionMode,
  file: File,
): Promise<UnifiedPredictionResponse> {
  const formData = new FormData();
  formData.append("image", file);

  return request("/predict", {
    method: "POST",
    params: { model: mode },
    headers: new Headers(), // intentionally empty so browser sets multipart boundary
    body: formData,
  });
}
