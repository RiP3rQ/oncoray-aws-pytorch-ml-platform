const TOKEN_KEY = "oncoray_token";

interface TokenStorage {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

interface TokenStoragePair {
  local: TokenStorage;
  session: TokenStorage;
}

export function getToken(): string | null {
  return getLocalToken(getBrowserTokenStorage());
}

export function setToken(token: string, persistent = true): void {
  setStoredToken(getBrowserTokenStorage(), token, persistent);
}

export function removeToken(): void {
  removeStoredToken(getBrowserTokenStorage());
}

export function getStoredToken(): string | null {
  return getAnyStoredToken(getBrowserTokenStorage());
}

export function hasStoredToken(): boolean {
  return Boolean(getStoredToken());
}

export function expireBrowserSession(): void {
  removeToken();
  window.location.href = "/login";
}

export function getLocalToken(storage: TokenStoragePair): string | null {
  return storage.local.getItem(TOKEN_KEY);
}

export function getAnyStoredToken(storage: TokenStoragePair): string | null {
  return storage.local.getItem(TOKEN_KEY) || storage.session.getItem(TOKEN_KEY);
}

export function setStoredToken(
  storage: TokenStoragePair,
  token: string,
  persistent = true,
): void {
  if (persistent) {
    storage.session.removeItem(TOKEN_KEY);
    storage.local.setItem(TOKEN_KEY, token);
    return;
  }

  storage.local.removeItem(TOKEN_KEY);
  storage.session.setItem(TOKEN_KEY, token);
}

export function removeStoredToken(storage: TokenStoragePair): void {
  storage.local.removeItem(TOKEN_KEY);
  storage.session.removeItem(TOKEN_KEY);
  removeTokenCookie();
}

function getBrowserTokenStorage(): TokenStoragePair {
  return {
    local: localStorage,
    session: sessionStorage,
  };
}

function removeTokenCookie(): void {
  if (typeof document === "undefined") {
    return;
  }

  document.cookie = `${TOKEN_KEY}=; Max-Age=0; path=/; SameSite=Lax`;
}
