import { normalizePhone, phoneProblem } from '@/lib/phone';

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

describe('phoneProblem', () => {
  it('accepts a valid number', () => {
    expect(phoneProblem('98765 43210')).toBeNull();
  });

  it("says what is wrong when the first digit cannot start an Indian mobile", () => {
    // The complaint that prompted this: ten digits, but not a mobile number.
    for (const raw of ['1234567890', '0123456789', '5876543210']) {
      expect(phoneProblem(raw)).toBe('An Indian mobile number starts with 6, 7, 8 or 9');
    }
  });

  it('counts the digits back when there are the wrong number of them', () => {
    expect(phoneProblem('98765')).toBe('That is 5 digits — a mobile number has 10');
    expect(phoneProblem('98765432100')).toBe('That is 11 digits — a mobile number has 10');
  });

  it('asks for digits when given letters', () => {
    expect(phoneProblem('abcdefghij')).toBe('Use digits only, like 98765 43210');
  });

  it('asks for a number when given nothing', () => {
    expect(phoneProblem('')).toBe('Enter a mobile number');
    expect(phoneProblem('   ')).toBe('Enter a mobile number');
  });
});
