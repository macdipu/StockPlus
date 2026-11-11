import { notFound } from "next/navigation";
import { StockPage } from "@/features/stock";

// Same shape the API accepts for a DSE trading code.
const TRADING_CODE = /^[A-Za-z0-9&().-]{1,24}$/;

export default async function Page({ params }: { params: Promise<{ symbol: string }> }) {
  const { symbol } = await params;
  const code = decodeURIComponent(symbol);
  if (!TRADING_CODE.test(code)) notFound();
  return <StockPage symbol={code} />;
}
