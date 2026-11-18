"use client";

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useSyncExternalStore } from "react";
import { CompanyDetails } from "@/features/company";
import { useLiveSymbols, useMarket, useQuote } from "@/features/live";
import { Card } from "@/shared/ui/Card";
import { ErrorNotice, Loading } from "@/shared/ui/Notice";
import { TabBar } from "@/shared/ui/TabBar";
import { analysisKey, useAnalysis, useTechnicals } from "../hooks/use-stock-queries";
import { pushRecent } from "../store/recent-store";
import { applyQuote } from "../utils/chart-model";
import { AnalysisCards } from "./AnalysisSections";
import { TradePlanCard } from "./TradePlanCard";
import { FundamentalsCard, ValuationCard } from "./FundamentalsCards";
import { SignalCard } from "./SignalCard";
import { StockHero } from "./StockHero";
import { TradingChart } from "./TradingChart";

const REFRESH_EVERY_MS = 20_000;

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "technicals", label: "Technicals" },
  { key: "company", label: "Company" },
] as const;
type TabKey = (typeof TABS)[number]["key"];
const isTab = (v: string): v is TabKey => TABS.some((t) => t.key === v);

/** The chosen tab lives in the URL hash, so a link or reload lands on the same view. The server snapshot is
 * "overview", which keeps server and client markup identical during hydration. */
function useHashTab(): TabKey {
  const hash = useSyncExternalStore(
    (notify) => {
      window.addEventListener("hashchange", notify);
      return () => window.removeEventListener("hashchange", notify);
    },
    () => window.location.hash.slice(1),
    () => "",
  );
  return isTab(hash) ? hash : "overview";
}

export function StockPage({ symbol }: { symbol: string }) {
  const code = symbol.toUpperCase();
  useLiveSymbols([code], { primary: true });
  const queryClient = useQueryClient();
  const analysis = useAnalysis(code);
  const technicals = useTechnicals(code);
  const quote = useQuote(code);
  const sessionDay = useMarket()?.session.day ?? null;
  const tab = useHashTab();
  const known = analysis.isSuccess;
  useEffect(() => {
    if (known) pushRecent(code); // only real symbols make the recent list
  }, [known, code]);
  const selectTab = (key: TabKey) => {
    window.history.replaceState(null, "", `#${key}`);
    window.dispatchEvent(new HashChangeEvent("hashchange")); // replaceState is silent; tell subscribers
  };

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
      <TabBar tabs={TABS} value={tab} onChange={selectTab} label="Stock sections" idPrefix="stock" />
      <div role="tabpanel" id={`stock-panel-${tab}`} aria-labelledby={`stock-tab-${tab}`}>
        {tab === "overview" && (
          <>
            <SignalCard analysis={a} />
            <Card label="Chart">
              {technicals.isError ? <ErrorNotice error={technicals.error} /> : <TradingChart symbol={code} bars={bars} analysis={a} />}
            </Card>
            <TradePlanCard analysis={a} />
          </>
        )}
        {tab === "technicals" && <AnalysisCards analysis={a} symbol={code} day={sessionDay ?? a.price.last_bar_date} />}
        {tab === "company" && (
          <>
            <ValuationCard analysis={a} />
            <FundamentalsCard analysis={a} />
            <CompanyDetails symbol={code} />
          </>
        )}
      </div>
    </>
  );
}
