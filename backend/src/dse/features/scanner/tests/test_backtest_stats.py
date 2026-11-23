from datetime import date, timedelta

import pandas as pd

from dse.features.scanner.domain.backtest_stats import PriceBook, PriceSeries, add_excess, summarise

D0 = date(2026, 1, 4)


def book() -> PriceBook:
    days = tuple(D0 + timedelta(days=i) for i in range(6))
    return PriceBook(
        {
            "UP": PriceSeries(days, (100,) * 6, (100, 101, 102, 103, 104, 110), (5,) * 6),
            "QUIET": PriceSeries(days, (50,) * 6, (50,) * 6, (0,) + (5,) * 5),
        }
    )


def test_forward_return_is_open_of_the_day_to_close_h_sessions_later() -> None:
    b = book()
    assert b.forward_return("UP", D0, 3) == 103 / 100 - 1
    assert b.forward_return("UP", D0 + timedelta(days=1), 4) == 110 / 100 - 1


def test_forward_return_is_none_when_it_cannot_be_measured() -> None:
    b = book()
    assert b.forward_return("UP", D0 + timedelta(days=4), 3) is None  # history ends first
    assert b.forward_return("QUIET", D0, 2) is None  # no volume on the entry day
    assert b.forward_return("NOPE", D0, 1) is None
    assert b.forward_return("UP", D0 - timedelta(days=1), 1) is None  # not a trading day for it


def test_average_turnover_uses_only_the_sessions_before_the_day() -> None:
    days = tuple(D0 + timedelta(days=i) for i in range(5))
    b = PriceBook(
        {"X": PriceSeries(days, (10,) * 5, (10, 10, 10, 10, 1000), (1_000_000,) * 4 + (9_000_000,))}
    )
    assert (
        b.avg_turnover_mn("X", days[3], window=3) == 10.0
    )  # 10 * 1,000,000 / 1e6, the big bar is not counted
    assert b.avg_turnover_mn("X", days[1], window=3) is None  # not enough history yet


def test_excess_is_relative_to_the_average_share_that_day() -> None:
    r = pd.DataFrame({"date": ["a", "a", "b", "b"], "ret_5": [0.10, 0.00, 0.02, 0.04]})
    ex = add_excess(r, [5])["ex_5"].round(4).tolist()
    assert ex == [0.05, -0.05, -0.01, 0.01]


def test_summary_reports_each_bucket_and_correlates_score_with_return() -> None:
    rows = []
    for day in range(10):
        for i in range(30):  # a score that really does predict the return
            rows.append(
                {
                    "date": D0 + timedelta(days=day),
                    "symbol": f"S{i}",
                    "bucket": "buy_zone" if i >= 20 else "watch",
                    "pick_score": float(i),
                    "value_score": float(i % 7),
                    "entry_score": float(i),
                    "ret_5": i / 1000,
                }
            )
    out = summarise(pd.DataFrame(rows), [5])
    assert (out["rows"], out["days"], out["shares"]) == (300, 10, 30)
    buy, watch = out["by_bucket"][5]["buy_zone"], out["by_bucket"][5]["watch"]
    assert buy["mean_pct"] > watch["mean_pct"]
    assert buy["excess_pct"] > 0 > watch["excess_pct"]
    assert out["rank_correlation"][5]["pick_score"]["mean_ic"] == 1.0
    q = out["by_pick_quintile"][5]
    assert q["Q5"]["mean_pct"] > q["Q1"]["mean_pct"]


def test_empty_input_is_reported_not_raised() -> None:
    assert summarise(pd.DataFrame(), [5]) == {"rows": 0}
