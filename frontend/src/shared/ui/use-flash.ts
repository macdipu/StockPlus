"use client";

import { useEffect, useRef, useState } from "react";

/** "flash-up" / "flash-dn" for ~0.9 s after `value` changes, else "". The first value never flashes. */
export function useFlash(value: number | null | undefined, ms = 900): "flash-up" | "flash-dn" | "" {
  const previous = useRef<number | null | undefined>(undefined);
  const [flash, setFlash] = useState<"flash-up" | "flash-dn" | "">("");

  useEffect(() => {
    const before = previous.current;
    previous.current = value;
    if (before == null || value == null || before === value) return;
    setFlash(value > before ? "flash-up" : "flash-dn");
    const t = setTimeout(() => setFlash(""), ms);
    return () => clearTimeout(t);
  }, [value, ms]);

  return flash;
}
