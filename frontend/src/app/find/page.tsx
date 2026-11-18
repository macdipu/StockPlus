import type { Metadata } from "next";
import { PicksPage } from "@/features/picks";

export const metadata: Metadata = {
  title: "Picks",
  description: "Every DSE share scored for value for money and entry timing, with sector filters (e.g. all except banks and insurance).",
};

export default function Page() {
  return <PicksPage />;
}
