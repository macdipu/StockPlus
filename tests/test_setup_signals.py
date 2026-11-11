import numpy as np
import pandas as pd

import indicators as I
import setup_score as S
import signals as G


def uptrend(n=260):
    rng = np.random.default_rng(0)
    c = 100 * np.cumprod(1 + 0.004 + rng.normal(0, 0.01, n))
    df = pd.DataFrame({"open": c * 0.995, "high": c * 1.01, "low": c * 0.985, "close": c,
                       "volume": 1000.0}, index=pd.date_range("2024-01-01", periods=n, freq="B"))
    return I.add_indicators(df)


def test_score_and_plan():
    ind = uptrend()
    sr = I.support_resistance(ind)
    s = S.score(ind, "A", sr)
    assert s["max"] == 6 and 0 <= s["score"] <= 6
    p = s["plan"]
    assert p["stop"] < p["entry_zone"][0] <= p["entry_zone"][1] == p["entry"] < p["target"]
    assert p["rr"] == (p["target"] - p["entry"]) / (p["entry"] - p["stop"])


def test_z_category_fails_and_avoids():
    ind = uptrend()
    sr = I.support_resistance(ind)
    s = S.score(ind, "Z", sr)
    assert not next(c for c in s["checks"] if c["key"] == "not_z")["pass"]
    assert G.signal(ind, s, [], "Z")["action"] == "AVOID"


def test_hit_target_first():
    df = pd.DataFrame({"close": [100, 100, 100], "high": [100, 106, 100], "low": [100, 99, 90]})
    assert G._hit_target_first(df, 0, 5, 5, 2) is True
    df2 = pd.DataFrame({"close": [100, 100], "high": [100, 106], "low": [100, 94]})
    assert G._hit_target_first(df2, 0, 5, 5, 1) is False  # both on same bar -> loss


def test_probability_shape():
    ind = uptrend()
    sr = I.support_resistance(ind)
    crit = S.criteria_frame(ind, "A")
    s = S.score(ind, "A", sr, crit)
    pr = G.profit_probability(ind, crit, s)
    sim = pr["similar_setups"]
    assert sim["wins"] + sim["losses"] + sim["unresolved"] == sim["n"]
    assert pr["all_days_baseline"]["n"] >= sim["n"]
