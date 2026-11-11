import numpy as np
import pandas as pd
import pytest

from dse.features.analysis.domain import vpa


def bars(closes, vol=1000.0, spread=1.0):
    c = pd.Series(closes, dtype=float, index=pd.date_range("2025-01-01", periods=len(closes), freq="B"))
    return pd.DataFrame({"open": c - 0.2, "high": c + spread, "low": c - spread, "close": c, "volume": vol,
                         "trades": 10.0})


def test_vpa_strong_buying_and_no_supply():
    df = bars(np.linspace(100, 110, 30))
    df.iloc[-1] = [110, 116, 109.5, 115.8, 5000, 10]                    # wide up bar, high vol, closes at high
    assert vpa.classify(df)["vpa"].iloc[-1] == "Strong buying"
    df2 = bars(np.linspace(100, 110, 30))
    df2.iloc[-3:, df2.columns.get_loc("volume")] = [900, 800, 300]
    df2.iloc[-1, :4] = [110.2, 110.3, 109.9, 110.0 - 0.15]              # narrow down bar, lowest volume
    df2.iloc[-1, df2.columns.get_loc("close")] = df2["close"].iloc[-2] - 0.1
    assert vpa.classify(df2)["vpa"].iloc[-1] == "No supply"
