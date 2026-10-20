import { apiGet, apiPost } from '@/api/client';
import type { AuthResponse, LoginBody, Owner, SignupBody } from '@/types/auth';

export function signup(body: SignupBody): Promise<AuthResponse> {
  return apiPost<AuthResponse>('/auth/signup', body);
}

export function login(body: LoginBody): Promise<AuthResponse> {
  return apiPost<AuthResponse>('/auth/login', body);
}

export function fetchMe(): Promise<Owner> {
  return apiGet<Owner>('/auth/me');
}
