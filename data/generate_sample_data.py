"""Generates the SYNTHETIC demo dataset (geometric Brownian motion, fixed seed).
This is NOT real market data."""
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
dates = pd.bdate_range("2024-01-02", "2025-12-31")
n = len(dates)
ret = rng.normal(0.10 / 252, 0.25 / np.sqrt(252), n)
close = 150 * np.exp(np.cumsum(ret))
open_ = np.concatenate([[150], close[:-1]]) * (1 + rng.normal(0, 0.003, n))
high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.006, n)))
low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.006, n)))
vol = rng.lognormal(16.5, 0.35, n).astype(int)
pd.DataFrame({"Date": dates.date, "Open": open_.round(2), "High": high.round(2),
              "Low": low.round(2), "Close": close.round(2), "Volume": vol}
             ).to_csv("data/sample_stock_data.csv", index=False)
