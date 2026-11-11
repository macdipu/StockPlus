import json

import pandas as pd
import pytest

import scraper


def flight_html(obj):
    """Mimic Next.js: the JSON is split across several escaped self.__next_f.push chunks."""
    text = "9:X " + json.dumps(obj)
    parts = [text[i:i + 40] for i in range(0, len(text), 40)]
    return "".join(f'<script>self.__next_f.push([1,{json.dumps(p)}])</script>' for p in parts)


COMPANY = {"code": "TEST", "name": "Test Ltd", "category": "A", "price": 50, "prevClose": 48, "nav": 20,
           "faceValue": 10, "paidUpCapital": 1_000_000, "freeFloat": 55.5, "weekHigh52": 60, "weekLow52": 30,
           "interimFinancials": {"periodEnds": {"annual": "202606", "nine": "202603", "half": "202512", "q1": "202509"},
                                 "rows": [{"metric": "EPS - Continuing Operations Basic", "q1": 0.5, "half": 1.1,
                                           "nine": 1.6, "annual": 2.0}]},
           "sharePattern": [{"date": "Oct 31, 2026", "pattern": {"sponsor": 40, "government": 0, "institution": 10,
                                                                 "foreign": 1, "public": 49}}],
           "dividendHistory": [{"year": 2025, "cash": 25, "stock": 5}], "description": "$undefined",
           "recentAnnouncements": [{"id": "1", "date": "10 Nov 2026", "summary": "AGM", "body": "Body"}]}
SERIES = [{"date": f"2026-01-{d:02d}", "price": 40 + d, "open": 39 + d, "high": 41 + d, "low": 38 + d,
           "volume": 1000 * d, "trades": d} for d in range(1, 11)]


def test_parse_flight_extracts_company_and_series_across_chunks():
    out = scraper.parse_flight(flight_html({"company": COMPANY, "series": SERIES}))
    assert out["company"]["code"] == "TEST" and len(out["series"]) == 10
    assert out["company"]["description"] is None  # "$undefined" normalised


def test_parse_flight_without_payload_is_a_clear_error():
    with pytest.raises(scraper.ScrapeError, match="flight payload"):
        scraper.parse_flight("<html></html>")


def test_parse_snapshot():
    snap = {"market": {"totals": {"tradeTime": "Nov 11, 2026 at 10:58 AM"}, "session": {"date": "2026-11-11",
                                                                                         "isOpen": True}},
            "prices": {"cols": ["code", "ltp", "ycp", "close", "volume"], "rows": [["AAA", 11, 10, 0, 500]]}}
    p = scraper.parse_snapshot(snap)
    q = p["quotes"]["AAA"]
    assert q["symbol"] == "AAA" and q["close"] is None and q["change"] == 1 and q["tradeTime"].endswith("10:58 AM")
    with pytest.raises(scraper.ScrapeError):
        scraper.parse_snapshot({"prices": {}})


def payload():
    return {"symbol": "TEST", "company": COMPANY, "series": SERIES, "fetched_at": "2026-01-10T15:00:00+06:00"}


def test_to_ohlcv_and_merge_live():
    df = scraper.to_ohlcv(payload())
    assert list(df.columns) == ["open", "high", "low", "close", "volume", "trades"] and df["close"].iloc[-1] == 50
    q = {"ltp": 52, "open": 50, "high": 53, "low": 49, "close": None, "volume": 700, "trades": 9}
    live = scraper.merge_live(df, q, {"date": "2026-01-11"})
    assert len(live) == 11 and live["close"].iloc[-1] == 52 and live.index[-1] == pd.Timestamp("2026-01-11")
    again = scraper.merge_live(live, {**q, "ltp": 53, "high": 54}, {"date": "2026-01-11"})
    assert len(again) == 11 and again["high"].iloc[-1] == 54           # refreshed, not duplicated
    assert len(scraper.merge_live(df, {**q, "volume": 0}, {"date": "2026-01-11"})) == 10   # not traded: no bar
    assert len(scraper.merge_live(df, q, {"date": "2026-01-05"})) == 10                    # stale session: no-op


def test_fundamentals_ttm_and_derived_fields():
    f = scraper.fundamentals(payload(), {"ltp": 50, "ycp": 48})
    assert f["eps_ttm"] == 2.0 and "annual" in f["eps_ttm_basis"]       # annual (202606) is the newest report
    assert f["pe"] == 25 and f["total_shares"] == 100_000 and f["sponsor_pct"] == 40
    assert f["dps"] == 2.5 and "25% cash" in f["last_dividend"]
    newer = json.loads(json.dumps(COMPANY))
    newer["interimFinancials"]["periodEnds"]["q1"] = "202609"
    f2 = scraper.fundamentals({**payload(), "company": newer})
    assert f2["eps_ttm"] == 2.0 and "Q1" in f2["eps_ttm_basis"]        # 0.5 × 4, annualised


def test_symbol_validation():
    assert scraper.normalize_symbol(" amcl(pran) ") == "AMCL(PRAN)"
    with pytest.raises(scraper.InvalidInput):
        scraper.normalize_symbol("bad sym!")
