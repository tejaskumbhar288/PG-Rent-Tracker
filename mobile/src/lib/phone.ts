const SEPARATORS = /[\s \-().]/g;
const TEN_DIGITS = /^[6-9]\d{9}$/;

export const COUNTRY_CODE = '+91';

/**
 * Normalise an Indian mobile number to E.164 (`+91XXXXXXXXXX`), or return
 * `null` if it is not one.
 *
 * Mirrors `normalize_phone` in the backend (`app/services/phone.py`). The
 * backend stays the authority on what is stored; this exists so the form can
 * flag a typo without a round trip.
 */
export function normalizePhone(raw: string): string | null {
  const cleaned = (raw ?? '').replace(SEPARATORS, '');

  let digits: string;
  if (cleaned.startsWith(COUNTRY_CODE)) {
    digits = cleaned.slice(COUNTRY_CODE.length);
  } else if (cleaned.length === 12 && cleaned.startsWith('91')) {
    digits = cleaned.slice(2);
  } else if (cleaned.length === 11 && cleaned.startsWith('0')) {
    digits = cleaned.slice(1);
  } else {
    digits = cleaned;
  }

  return TEN_DIGITS.test(digits) ? COUNTRY_CODE + digits : null;
}
