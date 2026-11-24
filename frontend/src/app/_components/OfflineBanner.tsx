"use client";

import { useOffline } from "@/shared/lib/connection";

/** Says plainly when the server cannot be reached, so a page that will not load has an explanation. */
export function OfflineBanner() {
  const offline = useOffline();
  if (!offline) return null;
  return (
    <div className="offlinebanner" role="alert">
      <b>Can&apos;t reach the server.</b> Pages may stay empty or out of date. We keep trying and this message goes away when it answers.
    </div>
  );
}
