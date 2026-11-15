"""Property 6: regional average preserves count and excludes NaN. Validates Requirements 11.1-11.4, 28.3."""
import numpy as np
import pandas as pd
import pytest
import xarray as xr
from hypothesis import given, settings, strategies as st

from modules.data_access import DataAccessError, compute_regional_average
from modules.models import BoundingBox

BOX = BoundingBox(-10, -10, 10, 10)


def make_ds(data: np.ndarray) -> xr.Dataset:
    t, ny, nx = data.shape
    return xr.Dataset(
        {"v": (("time", "lat", "lon"), data)},
        coords={
            "time": pd.date_range("2000-01-01", periods=t, freq="MS"),
            "lat": np.linspace(-5, 5, ny),
            "lon": np.linspace(-5, 5, nx),
        },
    )


cells = st.one_of(st.floats(-100, 100, allow_nan=False), st.just(np.nan))


@settings(max_examples=60, deadline=None)
@given(
    st.integers(1, 8).flatmap(
        lambda t: st.lists(
            st.lists(st.lists(cells, min_size=3, max_size=3), min_size=2, max_size=2),
            min_size=t,
            max_size=t,
        )
    )
)
def test_matches_nanmean_and_preserves_steps(raw):
    data = np.array(raw, dtype=float)
    ds = make_ds(data)
    before = ds.copy(deep=True)
    out = compute_regional_average(ds, "v", BOX)
    assert len(out) == data.shape[0]
    assert out.index.is_monotonic_increasing
    for i in range(data.shape[0]):
        block = data[i]
        if np.isnan(block).all():
            assert np.isnan(out.iloc[i])
        else:
            assert out.iloc[i] == pytest.approx(np.nanmean(block))
    xr.testing.assert_identical(ds, before)  # input not mutated


def test_missing_variable_and_empty_region():
    ds = make_ds(np.ones((2, 2, 3)))
    with pytest.raises(DataAccessError, match="nope"):
        compute_regional_average(ds, "nope", BOX)
    with pytest.raises(DataAccessError, match="no data"):
        compute_regional_average(ds, "v", BoundingBox(50, 50, 60, 60))
