import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { AgentFacts, StockPage, loadFacts } from "@/features/stock";

// Same shape the API accepts for a DSE trading code.
const TRADING_CODE = /^[A-Za-z0-9&().-]{1,24}$/;

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ symbol: string }> }): Promise<Metadata> {
  const code = decodeURIComponent((await params).symbol).toUpperCase();
  if (!TRADING_CODE.test(code)) return {};
  const data = await loadFacts(code);
  const get = (f: string) => data?.facts.find((x) => x.field === f)?.value;
  const description = data
    ? `${code}${data.name ? ` (${data.name})` : ""}: price ${get("price")} BDT, signal ${get("signal")}, P/E ${get("pe")}, buy zone ${get("buy_zone_low")}–${get("buy_zone_high")}, stop ${get("stop")}, target ${get("target")}. ${data.headline ?? ""}`
    : `${code} on the Dhaka Stock Exchange: price, candle analysis, trade plan and company details.`;
  return {
    title: code,
    description,
    alternates: {
      types: {
        "application/json": `/api/v1/stocks/${code}/analysis`,
        "text/markdown": `/api/v1/stocks/${code}/brief`,
      },
    },
  };
}

export default async function Page({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  const code = decodeURIComponent(symbol);
  if (!TRADING_CODE.test(code)) notFound();
  return (
    <>
      <StockPage symbol={code} />
      <Suspense fallback={null}>
        <AgentFacts symbol={code.toUpperCase()} />
      </Suspense>
    </>
  );
}
