"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { describeError } from "@/shared/api";
import { safeNext } from "../utils/safe-next";
import { useAuth } from "./AuthProvider";

interface Props {
  mode: "login" | "register";
}

export function AuthForm({ mode }: Props) {
  const { login, register } = useAuth();
  const router = useRouter();
  const next = safeNext(useSearchParams().get("next"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isRegister = mode === "register";

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await (isRegister ? register : login)(email, password);
      router.push(next);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card auth">
      <h3>{isRegister ? "Create an account" : "Sign in"}</h3>
      <form onSubmit={submit}>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" className="inp" type="email" autoComplete="email" required value={email}
            onChange={(e) => setEmail(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="password">Password{isRegister ? " (at least 10 characters)" : ""}</label>
          <input id="password" className="inp" type="password" required maxLength={256}
            autoComplete={isRegister ? "new-password" : "current-password"} minLength={isRegister ? 10 : undefined}
            value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        {error ? <div className="notice error" role="alert">{error}</div> : null}
        <button className="btn" type="submit" disabled={busy}>
          {busy ? "Please wait…" : isRegister ? "Create account" : "Sign in"}
        </button>
      </form>
      <p className="small mute">
        {isRegister ? (
          <>Already registered? <Link href={`/login?next=${encodeURIComponent(next)}`}>Sign in</Link></>
        ) : (
          <>New here? <Link href={`/register?next=${encodeURIComponent(next)}`}>Create an account</Link></>
        )}
      </p>
    </div>
  );
}
