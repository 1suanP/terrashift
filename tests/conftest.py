"""Shared pytest fixtures: synthetic series and mock granules. No network access."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modules.models import BoundingBox


@pytest.fixture
def sample_bounds() -> BoundingBox:
    return BoundingBox(-124.5, 32.5, -114.0, 42.0)


@pytest.fixture
def synthetic_series() -> pd.Series:
    """20 years of monthly data with a known upward trend of 0.5 units/year plus noise."""
    idx = pd.date_range("2000-01-01", periods=240, freq="MS")
    rng = np.random.default_rng(42)
    years = np.arange(240) / 12.0
    return pd.Series(10.0 + 0.5 * years + rng.normal(0, 0.3, 240), index=idx, name="value")


@pytest.fixture
def flat_series() -> pd.Series:
    """Noise around a constant, with no trend."""
    idx = pd.date_range("2000-01-01", periods=240, freq="MS")
    rng = np.random.default_rng(7)
    return pd.Series(5.0 + rng.normal(0, 0.5, 240), index=idx, name="value")


@pytest.fixture
def seasonal_series() -> pd.Series:
    """Strong seasonal cycle plus a small trend (0.2 units/year)."""
    idx = pd.date_range("2000-01-01", periods=240, freq="MS")
    months = np.arange(240)
    seasonal = 10.0 * np.sin(2 * np.pi * months / 12.0)
    rng = np.random.default_rng(3)
    return pd.Series(seasonal + 0.2 * months / 12.0 + rng.normal(0, 0.2, 240), index=idx, name="value")


class FakeGranule(dict):
    """Minimal stand-in for ``earthaccess.results.DataGranule`` (a dict subclass)."""


def make_granule(*urls_with_desc: tuple[str, str]) -> FakeGranule:
    return FakeGranule(
        {"umm": {"RelatedUrls": [{"URL": u, "Description": d, "Type": "GET DATA"} for u, d in urls_with_desc]}}
    )


@pytest.fixture
def mock_granules() -> list[FakeGranule]:
    return [
        make_granule(
            ("https://data.gesdisc.earthdata.nasa.gov/data/a.nc4", "Download a.nc4"),
            ("https://opendap.earthdata.nasa.gov/collections/C1/granules/a", "OPeNDAP request URL"),
        ),
        make_granule(("https://data.gesdisc.earthdata.nasa.gov/data/b.nc4", "Download b.nc4")),
        make_granule(
            ("https://opendap.earthdata.nasa.gov/collections/C1/granules/c", "OPENDAP link"),
            ("https://opendap.earthdata.nasa.gov/collections/C1/granules/c2", "opendap second"),
        ),
    ]


@pytest.fixture
def temp_meta():
    """A VariableMeta for tests that need one."""
    from modules.models import VariableMeta

    return VariableMeta(
        variable_id="T2M", dataset_key="M2TMNXSLV", long_name="2-meter air temperature",
        short_description="Air temperature near the ground.", units="\u00b0C",
        plain_language="This is the temperature of the air at about head height, like a weather forecast number.",
        category="atmosphere", trend_direction_hint="higher means warmer",
    )
