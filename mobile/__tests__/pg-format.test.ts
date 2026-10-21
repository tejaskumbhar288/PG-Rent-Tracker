import { dueDayLabel } from '@/lib/pg-format';

describe('dueDayLabel', () => {
  it.each([
    [1, 'Rent due on the 1st of each month'],
    [2, 'Rent due on the 2nd of each month'],
    [3, 'Rent due on the 3rd of each month'],
    [5, 'Rent due on the 5th of each month'],
    // 11-13 take "th" despite ending in 1, 2 and 3.
    [11, 'Rent due on the 11th of each month'],
    [12, 'Rent due on the 12th of each month'],
    [13, 'Rent due on the 13th of each month'],
    [21, 'Rent due on the 21st of each month'],
    [22, 'Rent due on the 22nd of each month'],
    [23, 'Rent due on the 23rd of each month'],
    [28, 'Rent due on the 28th of each month'],
  ])('renders day %p', (day, expected) => {
    expect(dueDayLabel(day)).toBe(expected);
  });
});
