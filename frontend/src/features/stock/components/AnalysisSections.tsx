import type { Analysis } from "../schemas/analysis";
import { ChecklistCard, IndicatorsCard, LevelsCard, PatternsCard, TechnicalReadingCard, TrendCard } from "./AnalysisCards";
import { IntradayCard } from "./IntradayCard";
import { VpaCard } from "./VpaCard";

/** The Technicals tab: a plain reading first, then the numbers behind it (indicators, levels, trend, patterns, volume). */
export function AnalysisCards({ analysis, symbol, day }: { analysis: Analysis; symbol: string; day: string }) {
  return (
    <>
      <TechnicalReadingCard analysis={analysis} />
      <IndicatorsCard analysis={analysis} />
      <div className="grid2" style={{ marginTop: 16 }}>
        <ChecklistCard analysis={analysis} />
        <LevelsCard analysis={analysis} />
        <TrendCard analysis={analysis} />
        <PatternsCard analysis={analysis} />
      </div>
      <div className="grid2">
        <VpaCard symbol={symbol} />
        <IntradayCard symbol={symbol} day={day} />
      </div>
    </>
  );
}
