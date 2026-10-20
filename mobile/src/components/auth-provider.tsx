import { useQueryClient } from '@tanstack/react-query';
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

import { setAuthToken } from '@/api/client';
import { clearToken, getToken, saveToken } from '@/lib/auth-storage';

type AuthState = {
  /** The current access token, or `null` when nobody is logged in. */
  token: string | null;
  /** True until the stored token has been read back on launch. */
  isHydrating: boolean;
  signIn: (token: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [token, setToken] = useState<string | null>(null);
  const [isHydrating, setIsHydrating] = useState(true);

  // Read the token back once on launch so a returning owner goes straight to
  // the dashboard (FEATURES.md F1: "kill the app, reopen — still logged in").
  useEffect(() => {
    let cancelled = false;
    void getToken().then((stored) => {
      if (cancelled) return;
      setAuthToken(stored);
      setToken(stored);
      setIsHydrating(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (next: string) => {
    setAuthToken(next);
    setToken(next);
    await saveToken(next);
  }, []);

  const signOut = useCallback(async () => {
    setAuthToken(null);
    setToken(null);
    await clearToken();
    // Drop every cached response so the next owner never sees the last one's data.
    queryClient.clear();
  }, [queryClient]);

  const value = useMemo<AuthState>(
    () => ({ token, isHydrating, signIn, signOut }),
    [token, isHydrating, signIn, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const state = useContext(AuthContext);
  if (state === null) {
    throw new Error('useAuth must be used inside <AuthProvider>');
  }
  return state;
}
