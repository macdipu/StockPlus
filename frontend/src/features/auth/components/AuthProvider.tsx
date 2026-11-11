"use client";

import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { refreshSession, setRefreshHandler, tokenStore } from "@/shared/api";
import type { Session, User } from "../schemas/auth";
import { authApi } from "../services/auth-api";

type AuthState =
  | { status: "loading"; user: null }
  | { status: "anonymous"; user: null }
  | { status: "authenticated"; user: User };

interface AuthContextValue {
  state: AuthState;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<AuthState>({ status: "loading", user: null });

  const adopt = useCallback((s: Session) => {
    tokenStore.set(s.access_token);
    setState({ status: "authenticated", user: s.user });
  }, []);

  const drop = useCallback(() => {
    tokenStore.set(null);
    setState({ status: "anonymous", user: null });
    queryClient.removeQueries({ queryKey: ["me"] }); // user-owned data must not outlive the session
  }, [queryClient]);

  useEffect(() => {
    // The shared client calls this when an authenticated request gets a 401 (access token expired).
    setRefreshHandler(async () => {
      try {
        adopt((await authApi.refresh()).data);
        return true;
      } catch {
        drop();
        return false;
      }
    });
    void refreshSession(); // restore the session from the refresh cookie (single-flight: StrictMode-safe)
    return () => setRefreshHandler(null);
  }, [adopt, drop]);

  const login = useCallback(
    async (email: string, password: string) => adopt((await authApi.login(email, password)).data),
    [adopt],
  );

  const register = useCallback(
    async (email: string, password: string) => {
      await authApi.register(email, password);
      await login(email, password);
    },
    [login],
  );

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      drop(); // sign out locally even if the request failed
    }
  }, [drop]);

  const value = useMemo(() => ({ state, login, register, logout }), [state, login, register, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
