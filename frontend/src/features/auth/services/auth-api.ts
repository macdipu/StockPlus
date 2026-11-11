import { envelope, nothing, request } from "@/shared/api";
import { sessionSchema, userSchema } from "../schemas/auth";

export const authApi = {
  register: (email: string, password: string) =>
    request("/auth/register", { method: "POST", body: { email, password }, schema: envelope(userSchema) }),
  login: (email: string, password: string) =>
    request("/auth/login", { method: "POST", body: { email, password }, schema: envelope(sessionSchema) }),
  /** Uses the HttpOnly refresh cookie; rotates it. */
  refresh: () => request("/auth/refresh", { method: "POST", schema: envelope(sessionSchema) }),
  logout: () => request("/auth/logout", { method: "POST", schema: nothing }),
};
