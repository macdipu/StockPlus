"use client";

import Link from "next/link";
import { useAuth } from "./AuthProvider";

export function UserMenu() {
  const { state, logout } = useAuth();
  if (state.status === "loading") return null;
  if (state.status === "anonymous") {
    return (
      <span className="small">
        <Link href="/login">Sign in</Link> · <Link href="/register">Register</Link>
      </span>
    );
  }
  return (
    <span className="small" data-testid="user-menu">
      <span title={`Role: ${state.user.role}`}>{state.user.email}</span>{" "}
      <button className="btn ghost small" type="button" onClick={() => void logout()}>Sign out</button>
    </span>
  );
}
