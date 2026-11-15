"""Properties 3 and 11: CI brackets slope; linear slope accuracy and NaN handling.

Validates Requirements 13.1, 13.2, 13.3, 16.1, 16.2, 16.3.
"""
import math

import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings, strategies as st
from scipy import stats

from modules.errors import InsufficientDataError
from modules.trend_analysis import _fractional_years, linear_trend, slope_confidence_interval

finite = st.floats(-1e6, 1e6, allow_nan=False, allow_infinity=False)


@given(finite, st.floats(0, 1e6), st.integers(3, 1000), st.floats(0.001, 0.999))
def test_ci_brackets_slope_and_matches_formula(slope, stderr, n, conf):
    lo, hi = slope_confidence_interval(slope, stderr, n, conf)
    assert lo <= slope <= hi
    t = stats.t.ppf(1 - (1 - conf) / 2, n - 2)
    assert lo == pytest.approx(slope - t * stderr, rel=1e-9, abs=1e-9)
    assert hi == pytest.approx(slope + t * stderr, rel=1e-9, abs=1e-9)


def test_ci_zero_stderr_and_invalid_args():
    assert slope_confidence_interval(2.0, 0.0, 10) == (2.0, 2.0)
    for args in [(float("nan"), 1, 10), (1, -1, 10), (1, float("inf"), 10), (1, 1, 2), (1, 1, 10.5), (1, 1, 10, 0.0), (1, 1, 10, 1.0)]:
        with pytest.raises(ValueError):
            slope_confidence_interval(*args)


@settings(max_examples=50, deadline=None)
@given(st.floats(-50, 50), st.floats(-100, 100), st.integers(24, 240))
def test_recovers_exact_slope(slope, intercept, n):
    idx = pd.date_range("2000-01-01", periods=n, freq="MS")
    x = _fractional_years(idx)
    series = pd.Series(intercept + slope * x, index=idx)
    res = linear_trend(series)
    assert res.slope == pytest.approx(slope, abs=1e-6)
    assert res.ci_lower <= res.slope <= res.ci_upper
    assert -1.0 <= res.r_value <= 1.0 and 0.0 <= res.p_value <= 1.0 and res.std_err >= 0.0


@settings(max_examples=40, deadline=None)
@given(st.lists(st.booleans(), min_size=36, max_size=36).filter(lambda m: sum(m) <= 30))
def test_nans_dropped_and_input_unchanged(mask):
    idx = pd.date_range("2000-01-01", periods=36, freq="MS")
    series = pd.Series(np.arange(36, dtype=float) * 0.3, index=idx)
    series[np.array(mask)] = np.nan
    before = series.copy()
    res = linear_trend(series)
    pd.testing.assert_series_equal(series, before)
    assert res.slope == pytest.approx(linear_trend(series.dropna()).slope)


def test_insufficient_data():
    idx = pd.date_range("2000-01-01", periods=3, freq="MS")
    with pytest.raises(InsufficientDataError, match="1"):
        linear_trend(pd.Series([1.0, np.nan, np.nan], index=idx))
    same = pd.DatetimeIndex(["2000-01-01", "2000-01-01"])
    with pytest.raises(InsufficientDataError, match="distinct"):
        linear_trend(pd.Series([1.0, 2.0], index=same))


def test_flat_series_has_no_trend(flat_series):
    res = linear_trend(flat_series)
    assert abs(res.slope) < 0.1 and res.p_value > 0.05
