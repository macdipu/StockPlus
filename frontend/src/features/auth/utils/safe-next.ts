/** Where to go after signing in. Only same-site paths: `?next=//evil.example` must not become an open redirect. */
export function safeNext(next: string | null | undefined, fallback = "/"): string {
  if (!next || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return fallback;
  if (/[\u0000-\u001f]/.test(next)) return fallback; // control characters (header/CRLF tricks)
  return next;
}
