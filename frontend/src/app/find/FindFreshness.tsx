"use client";

import { usePathname } from "next/navigation";
import { FreshnessBar, FreshnessLabel } from "@/features/universe";
import { routes } from "@/shared/lib/navigation";

/** Picks puts its Rescan button beside its own actions, so there only the label shows up here. */
export function FindFreshness() {
  return usePathname() === routes.find ? (
    <div className="row freshness"><FreshnessLabel /></div>
  ) : (
    <FreshnessBar />
  );
}
