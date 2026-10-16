import { z } from 'zod';

/*
 * Validation messages are i18n keys; `useFieldError` translates them at render
 * time, so the UI never holds hardcoded English text.
 */
const email = z.string().trim().min(1, 'validation.required').email('validation.email');
const requiredText = z.string().trim().min(1, 'validation.required');
const newPassword = z.string().min(8, 'validation.passwordLength');

export const loginSchema = z.object({
  email,
  password: z.string().min(1, 'validation.required'),
});
export type LoginValues = z.infer<typeof loginSchema>;

export const signupSchema = z.object({
  full_name: requiredText,
  email,
  password: newPassword,
  workspace_name: requiredText,
  timezone: z.string().min(1, 'validation.required'),
  dedupe_key: z.enum(['phone', 'email']),
});
export type SignupValues = z.infer<typeof signupSchema>;

export const forgotPasswordSchema = z.object({ email });
export type ForgotPasswordValues = z.infer<typeof forgotPasswordSchema>;

export const resetPasswordSchema = z
  .object({ password: newPassword, confirm: z.string() })
  .refine((v) => v.password === v.confirm, {
    message: 'validation.passwordMatch',
    path: ['confirm'],
  });
export type ResetPasswordValues = z.infer<typeof resetPasswordSchema>;

export const acceptInviteSchema = z.object({
  full_name: z.string().trim().optional(),
  password: z.string().min(1, 'validation.required'),
});
export type AcceptInviteValues = z.infer<typeof acceptInviteSchema>;
