/** A PG as the API returns it (`GET /pg`, and the body of a successful `PATCH /pg`). */
export type Pg = {
  id: string;
  name: string;
  address: string | null;
  /** Day of the month rent is due, 1–28. Copied into each new tenant's own due day. */
  default_rent_due_day: number;
  /** ISO-8601 instant; the offset depends on the server's session timezone. */
  created_at: string;
};

/**
 * Body of `PATCH /pg`. Every field is optional and only the ones sent are
 * changed; `address: null` clears the address, while omitting it leaves it be.
 */
export type PgUpdateBody = {
  name?: string;
  address?: string | null;
  default_rent_due_day?: number;
};
