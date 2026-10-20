import { normalizePhone } from '@/lib/phone';

const E164 = '+919876543210';

describe('normalizePhone', () => {
  // The same table the backend's test_phone_normalisation_unit uses, so the two
  // implementations cannot drift apart unnoticed.
  it.each([
    '9876543210',
    '98765 43210',
    '09876543210',
    '919876543210',
    E164,
    '+91-98765-43210',
    '+91 (98765) 43210',
    '98765 43210',
  ])('normalises %p to E.164', (raw) => {
    expect(normalizePhone(raw)).toBe(E164);
  });

  it.each([
    '',
    '12345',
    '0512345678',
    '98765432100',
    'abcdefghij',
    '+91',
    '5876543210',
    '+1 234 567 8901',
  ])('rejects %p', (raw) => {
    expect(normalizePhone(raw)).toBeNull();
  });
});
