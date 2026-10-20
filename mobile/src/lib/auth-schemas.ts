import { z } from 'zod';

import { normalizePhone } from '@/lib/phone';

/** Messages are what the owner reads, so they are phrased for a person. */
export const loginSchema = z.object({
  identifier: z.string().trim().min(1, 'Enter your phone number or email'),
  // Length is deliberately not checked: a wrong password must come back from
  // the server as one generic error, not be guessed at on the device.
  password: z.string().min(1, 'Enter your password'),
});

export const signupSchema = z.object({
  name: z.string().trim().min(1, 'Enter your name').max(120, 'That name is too long'),
  phone: z
    .string()
    .refine((value) => normalizePhone(value) !== null, 'Enter a 10-digit mobile number'),
  email: z.union([z.literal(''), z.string().email('Enter a valid email address')]),
  password: z.string().min(8, 'Use at least 8 characters').max(128, 'That password is too long'),
});

export type LoginValues = z.infer<typeof loginSchema>;
export type SignupValues = z.infer<typeof signupSchema>;
