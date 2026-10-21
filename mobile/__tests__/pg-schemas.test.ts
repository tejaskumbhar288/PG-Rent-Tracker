import { pgSchema } from '@/lib/pg-schemas';

type Values = { name: string; address: string; dueDay: string };

const valid: Values = { name: 'Sri Sai PG', address: '', dueDay: '5' };

function problem(overrides: Partial<Values>): string | undefined {
  const result = pgSchema.safeParse({ ...valid, ...overrides });
  return result.success ? undefined : result.error.issues[0].message;
}

describe('pgSchema', () => {
  it('accepts a name, an optional address and a due day in range', () => {
    expect(problem({})).toBeUndefined();
    expect(problem({ address: '12, 4th Cross, Koramangala' })).toBeUndefined();
  });

  it('trims the name', () => {
    const result = pgSchema.parse({ ...valid, name: '  Sri Sai PG  ' });
    expect(result.name).toBe('Sri Sai PG');
  });

  it.each([
    ['', 'Enter a name for your PG'],
    ['   ', 'Enter a name for your PG'],
    ['x'.repeat(121), 'That name is too long'],
  ])('rejects the name %p', (name, message) => {
    expect(problem({ name })).toBe(message);
  });

  it('rejects an address over 500 characters', () => {
    expect(problem({ address: 'x'.repeat(501) })).toBe('That address is too long');
    expect(problem({ address: 'x'.repeat(500) })).toBeUndefined();
  });

  it.each(['0', '29', '30', '100', 'abc', '', '-1', '5.5'])(
    'rejects the due day %p',
    (dueDay) => {
      expect(problem({ dueDay })).toBe('Enter a day from 1 to 28');
    },
  );

  it.each(['1', '28', '10'])('accepts the due day %p', (dueDay) => {
    expect(problem({ dueDay })).toBeUndefined();
  });
});
