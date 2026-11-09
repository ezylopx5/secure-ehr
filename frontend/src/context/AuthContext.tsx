import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, clearTokens, getAccessToken, saveTokens } from "../api/client";
import type { UserView } from "../types";

interface AuthContextValue {
  user: UserView | null;
  loading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserView | null>(null);
  const [loading, setLoading] = useState<boolean>(Boolean(getAccessToken()));
  const [error, setError] = useState<string | null>(null);

  const hydrate = useCallback(async () => {
    if (!getAccessToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const profile = await api.me();
      setUser(profile);
      setError(null);
    } catch {
      clearTokens();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void hydrate();
  }, [hydrate]);

  const login = useCallback(async (username: string, password: string) => {
    setLoading(true);
    setError(null);
    try {
      const tokens = await api.login(username, password);
      saveTokens(tokens);
      const profile = await api.me();
      setUser(profile);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Authentication failed";
      setError(msg);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    clearTokens();
    setUser(null);
    setError(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, error, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside an AuthProvider");
  }
  return ctx;
}
