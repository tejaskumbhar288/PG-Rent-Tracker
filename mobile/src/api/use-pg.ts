import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { fetchPg, updatePg } from '@/api/pg';
import { useAuth } from '@/components/auth-provider';
import type { Pg } from '@/types/pg';

const PG_KEY = ['pg'] as const;

/** The owner's PG. Idle while nobody is logged in, so it never fires on Login. */
export function usePg() {
  const { token } = useAuth();

  return useQuery({
    queryKey: PG_KEY,
    queryFn: fetchPg,
    enabled: token !== null,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}

/** Save PG details. The response is the whole PG, so the cache is set, not invalidated. */
export function useUpdatePg() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updatePg,
    onSuccess: (data: Pg) => {
      // PATCH returns the complete PG, so there is nothing left to refetch —
      // one less round trip on mobile data.
      queryClient.setQueryData(PG_KEY, data);
    },
  });
}
