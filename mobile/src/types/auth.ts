/** An owner as the API returns them (`GET /auth/me`, and inside `AuthResponse`). */
export type Owner = {
  id: string;
  name: string;
  phone: string;
  email: string | null;
  /** ISO-8601 instant; the offset depends on the server's session timezone. */
  created_at: string;
};

/** Body of a successful `POST /auth/signup` (201) or `POST /auth/login` (200). */
export type AuthResponse = {
  access_token: string;
  token_type: 'bearer';
  owner: Owner;
};

export type SignupBody = {
  name: string;
  phone: string;
  /** Optional; omitted rather than sent empty. */
  email?: string;
  password: string;
};

/** The backend takes one field for either a phone or an email. */
export type LoginBody = {
  identifier: string;
  password: string;
};
