"""Properties 1 and 2: anomaly idempotence and mean neutrality. Validates Requirements 12.1, 12.2."""
import numpy as np
import pandas as pd
import pytest
from hypothesis import given, settings, strategies as st

from modules.data_access import compute_monthly_anomalies

finite = st.floats(min_value=-1e3, max_value=1e3, allow_nan=False, allow_infinity=False)


@st.composite
def monthly_series(draw):
    years = draw(st.integers(min_value=2, max_value=12))
    values = draw(st.lists(finite, min_size=years * 12, max_size=years * 12))
    idx = pd.date_range("2000-01-01", periods=years * 12, freq="MS")
    return pd.Series(values, index=idx)


@settings(max_examples=60, deadline=None)
@given(monthly_series())
def test_idempotent(series):
    once = compute_monthly_anomalies(series)
    twice = compute_monthly_anomalies(once)
    np.testing.assert_allclose(twice.values, once.values, atol=1e-6)
    assert once.index.equals(series.index) and len(once) == len(series)


@settings(max_examples=60, deadline=None)
@given(monthly_series())
def test_each_calendar_month_mean_is_zero(series):
    anomalies = compute_monthly_anomalies(series)
    means = anomalies.groupby(anomalies.index.month).mean()
    np.testing.assert_allclose(means.values, 0.0, atol=1e-6)


def test_input_not_mutated_and_nans_preserved():
    idx = pd.date_range("2000-01-01", periods=36, freq="MS")
    s = pd.Series(np.arange(36, dtype=float), index=idx, name="x")
    s.iloc[5] = np.nan
    before = s.copy()
    out = compute_monthly_anomalies(s)
    pd.testing.assert_series_equal(s, before)
    assert np.isnan(out.iloc[5])


def test_all_nan_month_gives_nan_and_others_unaffected():
    idx = pd.date_range("2000-01-01", periods=36, freq="MS")
    s = pd.Series(np.arange(36, dtype=float), index=idx)
    s[s.index.month == 3] = np.nan
    out = compute_monthly_anomalies(s)
    assert out[out.index.month == 3].isna().all()
    assert out[out.index.month != 3].notna().all()


@pytest.mark.parametrize(
    "bad",
    [
        pd.Series([], dtype=float),
        pd.Series(np.arange(5.0), index=pd.date_range("2000-01-01", periods=5, freq="MS")),
        pd.Series(np.arange(24.0)),
    ],
)
def test_invalid_inputs_raise(bad):
    with pytest.raises(ValueError):
        compute_monthly_anomalies(bad)
