import type { Metadata } from "next";
import { Card } from "@/shared/ui/Card";

export const metadata: Metadata = { title: "Stock" };

/** No symbol chosen yet: point at the search box instead of guessing a stock. */
export default function Page() {
  return (
    <Card title="Pick a stock">
      <p style={{ margin: 0 }}>
        Search a trading code in the box above, click any row on the Dashboard, or open a symbol from your watchlist.
      </p>
    </Card>
  );
}
