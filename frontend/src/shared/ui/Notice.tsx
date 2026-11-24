"use client";

import { useEffect, useState } from "react";
import { ApiError, describeError } from "@/shared/api";

/** How long a load can take before we say so. Most answers arrive well inside this. */
export const SLOW_AFTER_MS = 8_000;

/** True once `ms` have passed since this mounted (so a spinner that has run too long can explain itself). */
function useAfter(ms: number): boolean {
  const [late, setLate] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setLate(true), ms);
    return () => clearTimeout(t);
  }, [ms]);
  return late;
}

/** A spinner and what is loading. After a few seconds it says it is slow, and offers to retry when it can. */
export function Loading({ what = "Loading", onRetry }: { what?: string; onRetry?: () => void }) {
  const slow = useAfter(SLOW_AFTER_MS);
  return (
    <div className="notice loading" role="status" aria-live="polite">
      <span className="loadrow">
        <span className="spinner" aria-hidden="true" />
        <span>{what}…</span>
      </span>
      {slow ? (
        <p className="small slow">
          Still loading. This is taking longer than usual: the server may be busy or unreachable.{" "}
          {onRetry ? (
            <button type="button" className="btn ghost small" onClick={onRetry}>Try again</button>
          ) : null}
        </p>
      ) : null}
    </div>
  );
}

/** What went wrong, in words, with the way out: a retry button, and a note when it was the connection itself. */
export function ErrorNotice({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const unreachable = error instanceof ApiError && error.status === 0;
  return (
    <div className="notice error" role="alert">
      <p style={{ margin: 0 }}>{describeError(error)}</p>
      {unreachable ? <p className="small" style={{ margin: "4px 0 0" }}>This is a connection problem, not a problem with your request.</p> : null}
      {onRetry ? (
        <p style={{ margin: "8px 0 0" }}>
          <button type="button" className="btn ghost small" onClick={onRetry}>Try again</button>
        </p>
      ) : null}
    </div>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="notice">{children}</div>;
}
