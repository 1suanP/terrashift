"""Properties 5 and 12: Mann-Kendall direction matches slope; Sen's slope on linear data.

Validates Requirements 14.1, 14.5, 14.6, 15.1, 15.2.
"""
import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings, strategies as st

from modules.trend_analysis import mann_kendall, sens_slope


def make(values):
    return pd.Series(values, index=pd.date_range("2000-01-01", periods=len(values), freq="MS"))


@settings(max_examples=50, deadline=None)
@given(st.floats(0.01, 10), st.floats(-100, 100), st.integers(12, 120))
def test_monotonic_increasing_detected(slope, intercept, n):
    res = mann_kendall(make(intercept + slope * np.arange(n)))
    assert res.trend == "increasing" and res.h is True and res.p < 0.05 and res.z > 0


@settings(max_examples=50, deadline=None)
@given(st.floats(0.01, 10), st.floats(-100, 100), st.integers(12, 120))
def test_monotonic_decreasing_detected(slope, intercept, n):
    res = mann_kendall(make(intercept - slope * np.arange(n)))
    assert res.trend == "decreasing" and res.h is True and res.z < 0


@settings(max_examples=50, deadline=None)
@given(st.lists(st.floats(-100, 100), min_size=3, max_size=60), st.floats(0.01, 0.5))
def test_h_iff_p_below_alpha_and_trend_label(values, alpha):
    res = mann_kendall(make(values), alpha=alpha)
    assert res.h == (res.p < alpha)
    expected = "no trend" if not res.h else ("increasing" if res.z > 0 else "decreasing")
    assert res.trend == expected


@settings(max_examples=50, deadline=None)
@given(st.floats(-20, 20), st.floats(-100, 100), st.integers(2, 100))
def test_sens_slope_exact_for_linear_data(slope, intercept, n):
    assert sens_slope(make(intercept + slope * np.arange(n))) == pytest.approx(slope, abs=1e-8)


def test_sens_slope_drops_nan_and_validates():
    s = make([1.0, np.nan, 3.0, 5.0])
    before = s.copy()
    assert sens_slope(s) == pytest.approx(2.0)
    pd.testing.assert_series_equal(s, before)
    with pytest.raises(ValueError):
        sens_slope(make([1.0, np.nan]))
    with pytest.raises(TypeError):
        sens_slope(pd.Series(["a", "b", "c"]))


def test_mann_kendall_validation_and_seasonal(seasonal_series):
    with pytest.raises(ValueError):
        mann_kendall(make([1.0, 2.0]))
    with pytest.raises(ValueError):
        mann_kendall(make(range(20)), alpha=0.9)
    with pytest.raises(ValueError):
        mann_kendall(make(range(20)), seasonal=True, period=12)  # < 2 * period
    with pytest.raises(ValueError):
        mann_kendall(make(range(40)), seasonal=True, period=1)
    res = mann_kendall(seasonal_series, seasonal=True, period=12)
    assert res.trend == "increasing"


def test_constant_series_is_no_trend():
    res = mann_kendall(make([3.0] * 20))
    assert res.trend == "no trend" and res.h is False
