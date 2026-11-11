import type { Metadata } from "next";
import { ToolsPage } from "@/features/tools";

export const metadata: Metadata = { title: "Tools" };

export default function Page() {
  return <ToolsPage />;
}
