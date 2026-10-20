import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';

import { fetchMe, login, signup } from '@/api/auth';
import { ApiError } from '@/api/client';
import { useAuth } from '@/components/auth-provider';
import type { AuthResponse } from '@/types/auth';

const ME_KEY = ['me'] as const;

/** The logged-in owner. Idle while nobody is logged in. */
export function useMe() {
  const { token, signOut } = useAuth();
  const query = useQuery({
    queryKey: ME_KEY,
    queryFn: fetchMe,
    enabled: token !== null,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  // A stored token the server rejects — expired, or the account is gone — must
  // send the owner back to Login rather than leave them on a dashboard that
  // cannot load anything.
  useEffect(() => {
    if (query.error instanceof ApiError && query.error.status === 401) {
      void signOut();
    }
  }, [query.error, signOut]);

  return query;
}

function useAuthMutation<TBody>(mutationFn: (body: TBody) => Promise<AuthResponse>) {
  const { signIn } = useAuth();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn,
    onSuccess: async (data: AuthResponse) => {
      await signIn(data.access_token);
      // The response already carries the owner, so the dashboard can render
      // without waiting for a /auth/me round trip.
      queryClient.setQueryData(ME_KEY, data.owner);
    },
  });
}

export function useLogin() {
  return useAuthMutation(login);
}

export function useSignup() {
  return useAuthMutation(signup);
}
