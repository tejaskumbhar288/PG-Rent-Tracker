const SEPARATORS = /[\s \-().]/g;
const TEN_DIGITS = /^[6-9]\d{9}$/;

export const COUNTRY_CODE = '+91';

/**
 * Strip separators and any `+91` / `91` / trunk `0` prefix, leaving what should
 * be the 10-digit subscriber number.
 *
 * Exported so a form can explain *why* a number was rejected instead of just
 * saying it was.
 */
export function subscriberNumber(raw: string): string {
  const cleaned = (raw ?? '').replace(SEPARATORS, '');

  if (cleaned.startsWith(COUNTRY_CODE)) {
    return cleaned.slice(COUNTRY_CODE.length);
  }
  if (cleaned.length === 12 && cleaned.startsWith('91')) {
    return cleaned.slice(2);
  }
  if (cleaned.length === 11 && cleaned.startsWith('0')) {
    return cleaned.slice(1);
  }
  return cleaned;
}

/**
 * Normalise an Indian mobile number to E.164 (`+91XXXXXXXXXX`), or return
 * `null` if it is not one.
 *
 * Mirrors `normalize_phone` in the backend (`app/services/phone.py`). The
 * backend stays the authority on what is stored; this exists so the form can
 * flag a typo without a round trip.
 */
export function normalizePhone(raw: string): string | null {
  const digits = subscriberNumber(raw);
  return TEN_DIGITS.test(digits) ? COUNTRY_CODE + digits : null;
}

/**
 * Why `raw` is not a usable mobile number, phrased for the owner — or `null`
 * when it is fine.
 *
 * Indian mobile numbers always begin 6, 7, 8 or 9, so "10 digits" alone is not
 * a useful thing to say to someone who typed ten of them.
 */
export function phoneProblem(raw: string): string | null {
  if (normalizePhone(raw) !== null) {
    return null;
  }

  const digits = subscriberNumber(raw);
  if (digits.length === 0) {
    return 'Enter a mobile number';
  }
  if (!/^\d+$/.test(digits)) {
    return 'Use digits only, like 98765 43210';
  }
  if (digits.length !== 10) {
    return `That is ${digits.length} digits — a mobile number has 10`;
  }
  return 'An Indian mobile number starts with 6, 7, 8 or 9';
}
