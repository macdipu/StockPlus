import type { Metadata } from "next";
import { ScannerPage } from "@/features/scanner";

export const metadata: Metadata = {
  title: "Custom rules",
  description: "Scan every DSE share with ready-made presets or your own rules.",
};

export default async function Page({ params }: { params: Promise<{ preset?: string[] }> }) {
  const { preset } = await params;
  return <ScannerPage presetKey={preset?.[0] ?? null} />;
}
