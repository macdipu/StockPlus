import type { Metadata } from "next";
import { MarketPage } from "@/features/market";

export const metadata: Metadata = { title: "Market" };

export default function Page() {
  return <MarketPage />;
}
