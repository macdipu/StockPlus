import type { Metadata } from "next";
import { MarketPage } from "@/features/market";

export const metadata: Metadata = { title: "Market" };

/** Landing page: market overview (sectors, movers, P/E, 52-week range). */
export default function Home() {
  return <MarketPage />;
}
