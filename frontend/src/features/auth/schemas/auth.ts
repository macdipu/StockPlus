import { z } from "zod";

export const userSchema = z.object({
  id: z.string(),
  email: z.string(),
  role: z.enum(["user", "admin"]),
  created_at: z.string(),
});
export type User = z.infer<typeof userSchema>;

export const sessionSchema = z.object({
  access_token: z.string(),
  token_type: z.literal("Bearer"),
  expires_at: z.string(),
  user: userSchema,
});
export type Session = z.infer<typeof sessionSchema>;
