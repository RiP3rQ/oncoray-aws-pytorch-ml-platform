import { describe, expect, test } from "bun:test";
import {
  ApiError,
  getModels,
  setApiRequestErrorReporterForTests,
  type ApiRequestErrorContext,
} from "./api";

const originalFetch = globalThis.fetch;

class MemoryStorage {
  private readonly values = new Map<string, string>();

  getItem(key: string): string | null {
    return this.values.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.values.set(key, value);
  }

  removeItem(key: string): void {
    this.values.delete(key);
  }

  clear(): void {
    this.values.clear();
  }
}

Object.defineProperty(globalThis, "localStorage", {
  value: new MemoryStorage(),
  configurable: true,
});
Object.defineProperty(globalThis, "sessionStorage", {
  value: new MemoryStorage(),
  configurable: true,
});

function resetBrowserMocks(): void {
  globalThis.fetch = originalFetch;
  localStorage.clear();
  sessionStorage.clear();
}

describe("API request errors", () => {
  test("reports and throws non-2xx responses", async () => {
    const reported: Array<{
      error: unknown;
      context: ApiRequestErrorContext;
    }> = [];
    const restoreReporter = setApiRequestErrorReporterForTests(
      (error, context) => {
        reported.push({ error, context });
      },
    );

    globalThis.fetch = (async () =>
      new Response("upstream unavailable", {
        status: 503,
        statusText: "Service Unavailable",
      })) as typeof fetch;

    try {
      let thrown: unknown;
      try {
        await getModels();
      } catch (error) {
        thrown = error;
      }

      expect(thrown instanceof ApiError).toBe(true);
      expect(reported.length).toBe(1);
      expect(reported[0]?.error instanceof ApiError).toBe(true);
      expect(reported[0]?.context).toMatchObject({
        method: "GET",
        path: "/model/",
        status: 503,
      });
    } finally {
      restoreReporter();
      resetBrowserMocks();
    }
  });

  test("reports and rethrows network failures", async () => {
    const networkError = new TypeError("fetch failed");
    const reported: Array<{
      error: unknown;
      context: ApiRequestErrorContext;
    }> = [];
    const restoreReporter = setApiRequestErrorReporterForTests(
      (error, context) => {
        reported.push({ error, context });
      },
    );

    globalThis.fetch = (async () => {
      throw networkError;
    }) as typeof fetch;

    try {
      let thrown: unknown;
      try {
        await getModels();
      } catch (error) {
        thrown = error;
      }

      expect(thrown).toBe(networkError);
      expect(reported.length).toBe(1);
      expect(reported[0]?.error).toBe(networkError);
      expect(reported[0]?.context).toMatchObject({
        method: "GET",
        path: "/model/",
      });
    } finally {
      restoreReporter();
      resetBrowserMocks();
    }
  });
});
