import { apiGet, apiPatch } from '@/api/client';
import type { Pg, PgUpdateBody } from '@/types/pg';

export function fetchPg(): Promise<Pg> {
  return apiGet<Pg>('/pg');
}

export function updatePg(body: PgUpdateBody): Promise<Pg> {
  return apiPatch<Pg>('/pg', body);
}
