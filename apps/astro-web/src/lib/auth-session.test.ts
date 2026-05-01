import { describe, expect, test } from "bun:test";
import {
  getAnyStoredToken,
  getLocalToken,
  removeStoredToken,
  setStoredToken,
} from "./auth-session";

class MemoryTokenStorage {
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
}

function storagePair() {
  return {
    local: new MemoryTokenStorage(),
    session: new MemoryTokenStorage(),
  };
}

describe("auth session token storage", () => {
  test("stores persistent token only in local storage", () => {
    const storage = storagePair();

    setStoredToken(storage, "old-session", false);
    setStoredToken(storage, "local-token", true);

    expect(getLocalToken(storage)).toBe("local-token");
    expect(storage.session.getItem("oncoray_token")).toBeNull();
    expect(getAnyStoredToken(storage)).toBe("local-token");
  });

  test("stores non-persistent token only in session storage", () => {
    const storage = storagePair();

    setStoredToken(storage, "old-local", true);
    setStoredToken(storage, "session-token", false);

    expect(getLocalToken(storage)).toBeNull();
    expect(storage.session.getItem("oncoray_token")).toBe("session-token");
    expect(getAnyStoredToken(storage)).toBe("session-token");
  });

  test("removes token from both storage locations", () => {
    const storage = storagePair();

    setStoredToken(storage, "local-token", true);
    setStoredToken(storage, "session-token", false);
    removeStoredToken(storage);

    expect(getAnyStoredToken(storage)).toBeNull();
  });
});
