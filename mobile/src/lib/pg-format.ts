/**
 * "Rent due on the 5th of each month" — the due day reads as a date, not a
 * number. Only days 1–28 are possible (CLAUDE.md §7), but 11th/12th/13th still
 * need the general rule rather than "always add the last digit's suffix".
 */
export function dueDayLabel(day: number): string {
  return `Rent due on the ${ordinal(day)} of each month`;
}

function ordinal(day: number): string {
  if (day % 100 >= 11 && day % 100 <= 13) {
    return `${day}th`;
  }
  switch (day % 10) {
    case 1:
      return `${day}st`;
    case 2:
      return `${day}nd`;
    case 3:
      return `${day}rd`;
    default:
      return `${day}th`;
  }
}
