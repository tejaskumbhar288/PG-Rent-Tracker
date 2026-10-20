import { loginSchema, signupSchema } from '@/lib/auth-schemas';

const validSignup = {
  name: 'Suresh Kumar',
  phone: '98765 43210',
  email: '',
  password: 'hunter2hunter2',
};

describe('signupSchema', () => {
  it('accepts a signup with no email', () => {
    expect(signupSchema.safeParse(validSignup).success).toBe(true);
  });

  it('accepts a signup with an email', () => {
    expect(signupSchema.safeParse({ ...validSignup, email: 'suresh@example.com' }).success).toBe(
      true,
    );
  });

  it('rejects a password under 8 characters', () => {
    expect(signupSchema.safeParse({ ...validSignup, password: 'short' }).success).toBe(false);
  });

  it('rejects an unparseable phone', () => {
    expect(signupSchema.safeParse({ ...validSignup, phone: '12345' }).success).toBe(false);
  });

  it('rejects a blank name', () => {
    expect(signupSchema.safeParse({ ...validSignup, name: '   ' }).success).toBe(false);
  });

  it('rejects a malformed email', () => {
    expect(signupSchema.safeParse({ ...validSignup, email: 'not-an-email' }).success).toBe(false);
  });
});

describe('loginSchema', () => {
  it('accepts a phone and password', () => {
    expect(loginSchema.safeParse({ identifier: '98765 43210', password: 'hunter2' }).success).toBe(
      true,
    );
  });

  it('leaves password length to the server, so a short one still submits', () => {
    expect(loginSchema.safeParse({ identifier: '98765 43210', password: 'x' }).success).toBe(true);
  });

  it('rejects an empty identifier', () => {
    expect(loginSchema.safeParse({ identifier: '  ', password: 'hunter2' }).success).toBe(false);
  });
});
