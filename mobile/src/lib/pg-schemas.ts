import { z } from 'zod';

/** Messages are what the owner reads, so they are phrased for a person. */
export const pgSchema = z.object({
  name: z.string().trim().min(1, 'Enter a name for your PG').max(120, 'That name is too long'),
  // Optional: an empty field means "no address" and is sent as null.
  address: z.string().max(500, 'That address is too long'),
  // Deliberately a string, not transformed to a number: a zod transform would
  // split this schema's input and output types, which @hookform/resolvers v3
  // only handles through a three-generic useForm. The caller converts on submit.
  dueDay: z
    .string()
    .trim()
    .refine(
      (value) => /^\d{1,2}$/.test(value) && Number(value) >= 1 && Number(value) <= 28,
      'Enter a day from 1 to 28',
    ),
});

export type PgValues = z.infer<typeof pgSchema>;
