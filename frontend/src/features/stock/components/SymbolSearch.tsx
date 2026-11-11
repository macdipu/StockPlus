"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { useAllQuotes } from "@/features/live";

/** Header search: type a trading code, pick from the datalist, go to its page. */
export function SymbolSearch() {
  const router = useRouter();
  const quotes = useAllQuotes();
  const [value, setValue] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    const code = value.trim().toUpperCase();
    if (!code) return;
    router.push(`/stock/${encodeURIComponent(code)}`);
    setValue("");
  }

  return (
    <form className="search" onSubmit={submit} role="search">
      <label className="sr-only" htmlFor="symbol-search">Trading code</label>
      <input
        id="symbol-search"
        className="inp"
        list="symbols"
        placeholder="Symbol e.g. GP"
        autoComplete="off"
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
      <datalist id="symbols">
        {(quotes.data ?? []).map((q) => (
          <option key={q.symbol} value={q.symbol} />
        ))}
      </datalist>
      <button className="btn" type="submit">Analyze</button>
    </form>
  );
}
