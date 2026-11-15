"""Properties 14 and 9: analyze() completeness, significance override, and no input mutation.

Validates Requirements 19.1, 19.4, 19.5, 19.6, 28.1.
"""
import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings, strategies as st

import config
from modules.errors import InsufficientDataError
from modules.trend_analysis import analyze

idx = pd.date_range("2000-01-01", periods=120, freq="MS")
META = config.VARIABLES["M2TMNXSLV/T2M"]


@settings(max_examples=40, deadline=None)
@given(st.floats(-3, 3), st.integers(0, 10_000), st.booleans(), st.floats(0.01, 5))
def test_complete_result_and_no_mutation(slope, seed, anomalies, noise):
    rng = np.random.default_rng(seed)
    s = pd.Series(slope * np.arange(120) / 12 + rng.normal(0, noise, 120), index=idx, name="v")
    s.iloc[rng.integers(0, 120, 5)] = np.nan
    before = s.copy()
    res = analyze(s, META, "Test region", use_anomalies=anomalies)
    pd.testing.assert_series_equal(s, before)
    assert res.linear and res.mann_kendall and res.interpretation and res.region_name == "Test region"
    assert res.significance in {"increasing", "decreasing", "none"}
    assert res.n_points == int(s.notna().sum())
    if res.significance != "none":
        lin_dir = "increasing" if res.linear.slope > 0 else "decreasing"
        assert res.linear.p_value < 0.05 and res.mann_kendall.trend == lin_dir == res.significance
    assert (res.time_series.anomalies is not None) == anomalies
    assert res.time_series.is_anomaly == anomalies


def test_significant_trend(synthetic_series, temp_meta):
    res = analyze(synthetic_series, temp_meta, "R")
    assert res.significance == "increasing" and res.linear.slope == pytest.approx(0.5, abs=0.05)
    assert res.sens_slope_value == pytest.approx(0.5, abs=0.05)


def test_flat_series_not_significant(flat_series, temp_meta):
    assert analyze(flat_series, temp_meta, "R").significance == "none"


def test_anomalies_reveal_trend_under_seasonality(seasonal_series, temp_meta):
    res = analyze(seasonal_series, temp_meta, "R", use_anomalies=True)
    assert res.significance == "increasing" and res.linear.slope == pytest.approx(0.2, abs=0.05)


def test_insufficient_data_reports_count(temp_meta):
    s = pd.Series([1.0] + [np.nan] * 5, index=pd.date_range("2000-01-01", periods=6, freq="MS"))
    with pytest.raises(InsufficientDataError, match="1"):
        analyze(s, temp_meta, "R")


def test_two_points_still_returns_result(temp_meta):
    s = pd.Series([1.0, 2.0], index=pd.date_range("2000-01-01", periods=2, freq="MS"))
    res = analyze(s, temp_meta, "R")
    assert res.significance == "none" and res.n_points == 2


def test_nan_input_not_filled(temp_meta):
    s = pd.Series(np.arange(24.0), index=pd.date_range("2000-01-01", periods=24, freq="MS"))
    s.iloc[3] = np.nan
    analyze(s, temp_meta, "R")
    assert np.isnan(s.iloc[3])
