"use client";

import { useIsFetching } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { startsNavigation } from "@/shared/lib/nav-progress";

const SHOW_AFTER_MS = 250; // quick loads never flash the bar
const NAV_GIVE_UP_MS = 15_000;

/**
 * A thin bar across the top of the window while something is loading: a page change that has not arrived yet, or data a
 * screen is still waiting for for the first time. Background refreshes of data already on screen do not count, or the
 * bar would flash every time a live panel refreshed.
 */
export function TopProgress() {
  const pathname = usePathname();
  const loadingFirst = useIsFetching({ predicate: (q) => q.state.data === undefined }) > 0;
  // The page the click started from. While the address is still that page, the new one has not arrived.
  const [leaving, setLeaving] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let giveUp: ReturnType<typeof setTimeout> | undefined;
    const onClick = (e: MouseEvent) => {
      const a = (e.target as Element | null)?.closest?.("a");
      if (!a) return;
      const go = startsNavigation(
        { href: a.getAttribute("href"), target: a.getAttribute("target"), download: a.hasAttribute("download"), defaultPrevented: e.defaultPrevented, button: e.button, modifier: e.ctrlKey || e.metaKey || e.shiftKey || e.altKey },
        { pathname: window.location.pathname, origin: window.location.origin },
      );
      if (!go) return;
      setLeaving(window.location.pathname);
      clearTimeout(giveUp);
      giveUp = setTimeout(() => setLeaving(null), NAV_GIVE_UP_MS);
    };
    document.addEventListener("click", onClick);
    return () => {
      document.removeEventListener("click", onClick);
      clearTimeout(giveUp);
    };
  }, []);

  const busy = (leaving !== null && leaving === pathname) || loadingFirst;
  useEffect(() => {
    if (!busy) return;
    const t = setTimeout(() => setReady(true), SHOW_AFTER_MS);
    return () => {
      clearTimeout(t);
      setReady(false);
    };
  }, [busy]);

  return busy && ready ? <div className="topprogress" role="progressbar" aria-label="Loading" /> : null;
}
