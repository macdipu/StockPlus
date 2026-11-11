"""Volume-price analysis: label each bar from its spread, close position and relative volume.
Ported unchanged from legacy `vpa.py`.

Works on daily bars and on 1-minute bars. Thresholds are explicit and tunable:
  spread  = (high - low) / average spread of the previous N bars
  rel_vol = volume / average volume of the previous N bars
  close position = (close - low) / (high - low)     (1 = closed at the high)
"""

import numpy as np
import pandas as pd

VT: dict[str, float] = {
    "N": 20,
    "WIDE": 1.3,
    "NARROW": 0.7,
    "HIGH_VOL": 1.5,
    "ULTRA_VOL": 2.2,
    "LOW_VOL": 0.7,
    "CLOSE_HIGH": 0.7,
    "CLOSE_LOW": 0.3,
}

LABELS: dict[str, tuple[str, str]] = {  # label -> (bias, meaning)
    "Strong buying": ("bullish", "Wide up bar on high volume closing near the high: demand in control"),
    "Strong selling": ("bearish", "Wide down bar on high volume closing near the low: supply in control"),
    "Stopping volume": ("bullish", "Down bar on very high volume that closed off its lows: selling absorbed"),
    "Upthrust": ("bearish", "Push higher on very high volume rejected into a close near the low"),
    "Effort, no result": ("neutral", "Very high volume with a narrow spread: absorption, watch next bar"),
    "No demand": ("bearish", "Narrow up bar on low volume, less than the prior 2 bars: buyers absent"),
    "No supply": ("bullish", "Narrow down bar on low volume, less than the prior 2 bars: sellers absent"),
}


def classify(df: pd.DataFrame) -> pd.DataFrame:
    n = int(VT["N"])
    rng = (df["high"] - df["low"]).astype(float)
    avg_rng = rng.shift(1).rolling(n, min_periods=max(5, n // 2)).mean()
    avg_vol = df["volume"].shift(1).rolling(n, min_periods=max(5, n // 2)).mean()
    spread = rng / avg_rng
    rel_vol = df["volume"] / avg_vol
    cpos = ((df["close"] - df["low"]) / rng.replace(0, np.nan)).fillna(0.5)
    up = df["close"] > df["close"].shift(1)
    down = df["close"] < df["close"].shift(1)
    lower_vol_2 = (df["volume"] < df["volume"].shift(1)) & (df["volume"] < df["volume"].shift(2))

    label = pd.Series(None, index=df.index, dtype=object)
    rules = [  # order matters: first match wins
        (
            "Upthrust",
            (rel_vol >= VT["ULTRA_VOL"]) & (df["high"] > df["high"].shift(1)) & (cpos <= VT["CLOSE_LOW"]),
        ),
        ("Stopping volume", down & (rel_vol >= VT["ULTRA_VOL"]) & (cpos >= 0.5)),
        (
            "Strong buying",
            up & (spread >= VT["WIDE"]) & (rel_vol >= VT["HIGH_VOL"]) & (cpos >= VT["CLOSE_HIGH"]),
        ),
        (
            "Strong selling",
            down & (spread >= VT["WIDE"]) & (rel_vol >= VT["HIGH_VOL"]) & (cpos <= VT["CLOSE_LOW"]),
        ),
        ("Effort, no result", (rel_vol >= VT["ULTRA_VOL"]) & (spread <= VT["NARROW"])),
        ("No demand", up & (spread <= VT["NARROW"]) & (rel_vol <= VT["LOW_VOL"]) & lower_vol_2),
        ("No supply", down & (spread <= VT["NARROW"]) & (rel_vol <= VT["LOW_VOL"]) & lower_vol_2),
    ]
    for name, mask in rules:
        label = label.where(label.notna() | ~mask.fillna(False), name)
    label = label.where(label.notna(), None)
    bias = label.map(lambda x: LABELS[x][0] if isinstance(x, str) else None)
    return pd.DataFrame(
        {"vpa": label, "vpa_bias": bias, "spread_rel": spread, "vol_rel": rel_vol, "close_pos": cpos},
        index=df.index,
    )
