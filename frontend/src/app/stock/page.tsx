import type { Metadata } from "next";
import { StockLauncher } from "@/features/stock";

export const metadata: Metadata = { title: "Stock", description: "Look up any DSE share: signal, chart, trade plan and company details." };

/** No symbol chosen yet: search, recent and watchlist shortcuts, and what is moving today. */
export default function Page() {
  return <StockLauncher />;
}
