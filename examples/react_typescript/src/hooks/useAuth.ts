import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { AuthState, User } from "../types";

const TOKEN_KEY = "ctx_token";

export function useAuth(): AuthState & {
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
} {
  const [state, setState] = useState<AuthState>({
    user: null,
    token: localStorage.getItem(TOKEN_KEY),
    isLoading: false,
    error: null,
  });

  // Hydrate user from stored token on mount.
  useEffect(() => {
    if (!state.token) return;
    setState((s) => ({ ...s, isLoading: true }));
    api
      .me(state.token)
      .then((user: User) => setState((s) => ({ ...s, user, isLoading: false })))
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY);
        setState({ user: null, token: null, isLoading: false, error: null });
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const login = useCallback(async (username: string, password: string) => {
    setState((s) => ({ ...s, isLoading: true, error: null }));
    try {
      const { access_token } = await api.login(username, password);
      localStorage.setItem(TOKEN_KEY, access_token);
      const user = await api.me(access_token);
      setState({ user, token: access_token, isLoading: false, error: null });
    } catch (err) {
      setState((s) => ({
        ...s,
        isLoading: false,
        error: err instanceof Error ? err.message : "Login failed",
      }));
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setState({ user: null, token: null, isLoading: false, error: null });
  }, []);

  return { ...state, login, logout };
}
