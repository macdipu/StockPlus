"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef } from "react";
import { useLiveSymbols, useMarket, useQuote } from "@/features/live";
import { Card } from "@/shared/ui/Card";
import { ErrorNotice, Loading } from "@/shared/ui/Notice";
import { analysisKey, useAnalysis, useTechnicals } from "../hooks/use-stock-queries";
import { applyQuote } from "../utils/chart-model";
import { AnalysisCards } from "./AnalysisSections";
import { PriceChart } from "./PriceChart";
import { SignalCard } from "./SignalCard";
import { StockHero } from "./StockHero";

const REFRESH_EVERY_MS = 20_000;

export function StockPage({ symbol }: { symbol: string }) {
  const code = symbol.toUpperCase();
  useLiveSymbols([code], { primary: true });
  const queryClient = useQueryClient();
  const analysis = useAnalysis(code);
  const technicals = useTechnicals(code);
  const quote = useQuote(code);
  const sessionDay = useMarket()?.session.day ?? null;

  // The signal, plan and indicators are recomputed server-side. Refresh them when the price actually moves,
  // at most every 20 s, and never for the first quote we see (that is just the initial seed).
  const seen = useRef<string | null>(null);
  const lastRefresh = useRef(0);
  useEffect(() => {
    if (!quote) return;
    const key = `${quote.ltp}|${quote.volume}`;
    const previous = seen.current;
    seen.current = key;
    if (previous === null || previous === key || Date.now() - lastRefresh.current < REFRESH_EVERY_MS) return;
    lastRefresh.current = Date.now();
    void queryClient.invalidateQueries({ queryKey: analysisKey(code) });
    void queryClient.invalidateQueries({ queryKey: ["stock", code, "technicals"] });
  }, [quote, code, queryClient]);

  const bars = useMemo(() => applyQuote(technicals.data ?? [], quote, sessionDay), [technicals.data, quote, sessionDay]);

  useEffect(() => {
    const ltp = quote?.ltp ?? analysis.data?.price.ltp;
    document.title = ltp != null ? `${code} ${ltp} · DSE Live` : `${code} · DSE Live`;
  }, [code, quote?.ltp, analysis.data?.price.ltp]);

  if (analysis.isPending) return <Card label="Loading"><Loading what={`Loading ${code}`} /></Card>;
  if (analysis.isError) {
    return (
      <Card label="Error">
        <ErrorNotice error={analysis.error} />
      </Card>
    );
  }
  const a = analysis.data;
  return (
    <>
      <StockHero analysis={a} />
      <SignalCard analysis={a} />
      <Card label="Chart">
        {technicals.isError ? <ErrorNotice error={technicals.error} /> : <PriceChart bars={bars} patterns={a.candles.patterns} levels={a.levels} />}
      </Card>
      <AnalysisCards analysis={a} symbol={code} day={sessionDay ?? a.price.last_bar_date} />
    </>
  );
}
