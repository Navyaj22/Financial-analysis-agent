import math
import numpy as np
import pandas as pd
import pytest
from services import metrics_service as ms


def s(vals):
    return pd.Series(vals, index=pd.date_range("2024-01-01", periods=len(vals), freq="B"), dtype=float)


def test_period_return():
    assert ms.period_return(s([100, 110, 121])) == pytest.approx(21.0)
    assert ms.period_return(s([100])) is None


def test_daily_returns():
    r = ms.daily_returns(s([100, 110, 99]))
    assert r.iloc[0] == pytest.approx(10.0) and r.iloc[1] == pytest.approx(-10.0)


def test_annualized_volatility():
    c = s([100, 101, 99, 102, 100, 103])
    expected = ms.daily_returns(c).std(ddof=1) * math.sqrt(252)
    assert ms.annualized_volatility(c) == pytest.approx(expected)
    assert ms.annualized_volatility(s([100, 101])) is None


def test_constant_prices_zero_vol_zero_drawdown():
    c = s([50] * 10)
    assert ms.annualized_volatility(c) == pytest.approx(0)
    assert ms.max_drawdown(c) == pytest.approx(0)


def test_max_drawdown():
    assert ms.max_drawdown(s([100, 120, 90, 110, 60])) == pytest.approx(-50.0)


def test_moving_average():
    ma = ms.moving_average(s([1, 2, 3, 4, 5]), 3)
    assert math.isnan(ma.iloc[1]) and ma.iloc[2] == pytest.approx(2) and ma.iloc[4] == pytest.approx(4)


def test_volume_trend():
    v = s([100] * 30 + [200] * 20)
    assert ms.volume_trend(v, 20) == pytest.approx(100.0 * (200 / ((100 * 30 + 200 * 0) / 30)) / 1 - 100.0)
    assert ms.volume_trend(s([1, 2, 3]), 20) is None


def test_compute_kpis_handles_missing():
    df = pd.DataFrame({"Close": [100.0, 105.0], "Volume": [np.nan, np.nan]}, index=pd.date_range("2024-01-01", periods=2))
    k = ms.compute_kpis(df)
    assert k["period_return_pct"] == pytest.approx(5.0)
    assert k["avg_volume"] is None and k["ma20_latest"] is None
