import type { Analysis } from "../schemas/analysis";
import {
  ChecklistCard,
  IndicatorsCard,
  LevelsCard,
  PatternsCard,
  SummaryCard,
  TrendCard,
} from "./AnalysisCards";
import { AnnouncementsCard, FundamentalsCard, ValuationCard } from "./FundamentalsCards";
import { IntradayCard } from "./IntradayCard";
import { VpaCard } from "./VpaCard";

/** The cards below the chart, in reading order. */
export function AnalysisCards({ analysis, symbol, day }: { analysis: Analysis; symbol: string; day: string }) {
  return (
    <>
      <div className="grid2">
        <ChecklistCard analysis={analysis} />
        <LevelsCard analysis={analysis} />
        <TrendCard analysis={analysis} />
        <IndicatorsCard analysis={analysis} />
        <PatternsCard analysis={analysis} />
      </div>
      <div style={{ marginTop: 16 }}>
        <SummaryCard analysis={analysis} />
      </div>
      <div className="grid2" style={{ marginBottom: 16 }}>
        <VpaCard symbol={symbol} />
        <IntradayCard symbol={symbol} day={day} />
      </div>
      <ValuationCard analysis={analysis} />
      <div className="grid2">
        <FundamentalsCard analysis={analysis} />
        <AnnouncementsCard analysis={analysis} />
      </div>
    </>
  );
}
