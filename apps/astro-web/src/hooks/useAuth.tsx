import { useCallback, useEffect, useState, type ReactNode } from "react";
import { AuthContext } from "../lib/auth.js";
import type { User } from "../lib/auth.js";
import * as api from "../lib/api.js";
import { getStoredToken, setToken, removeToken } from "../lib/auth.js";
import { toast } from "sonner";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const authenticated = !!user && !!getStoredToken();

  const fetchUser = useCallback(async () => {
    try {
      const me = await api.getMe();
      setUser(me);
    } catch {
      removeToken();
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (getStoredToken()) {
      void fetchUser();
    } else {
      setIsLoading(false);
    }
  }, [fetchUser]);

  const login = useCallback(
    async (email: string, password: string, persistent = true) => {
      const tokenData = await api.login(email, password);
      setToken(tokenData.access_token, persistent);
      const me = await api.getMe();
      setUser(me);
      toast.success("Welcome back!");
    },
    [],
  );

  const register = useCallback(async (email: string, password: string) => {
    await api.signup(email, password);
    toast.success("Verification email sent. Check your inbox.");
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // proceed with local cleanup even if API call fails
    }
    removeToken();
    setUser(null);
    toast.success("Successfully logged out.");
    window.location.href = "/login";
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: authenticated,
        isLoading,
        login,
        logout,
        register,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}
