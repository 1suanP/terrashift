"""Property 16 and pipeline unit tests. Validates Requirements 4.3, 6.1, 6.2, 34.1, 34.2, 34.3 and the happy path."""
from unittest import mock

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from hypothesis import HealthCheck, given, settings, strategies as st

import config
from modules import data_access, data_discovery, pipeline
from modules.errors import DataDiscoveryError
from modules.models import BoundingBox, TimeRange
from tests.conftest import make_granule

BOX = BoundingBox(-10, -10, 10, 10)
GOOD_TR = TimeRange("2001-01-01", "2003-12-31")


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    dataset=st.one_of(st.text(max_size=12), st.sampled_from(list(config.DATASETS)), st.none()),
    variable=st.one_of(st.text(max_size=12), st.sampled_from(["precipitation", "T2M", "t2m"]), st.none()),
    start=st.dates(min_value=__import__("datetime").date(1970, 1, 1), max_value=__import__("datetime").date(2035, 1, 1)),
    span=st.integers(0, 4000),
)
def test_invalid_requests_never_reach_external_services(dataset, variable, start, span):
    end = start + __import__("datetime").timedelta(days=span)
    tr = TimeRange(start.isoformat(), end.isoformat())
    valid = True
    try:
        config.validate_request(dataset, variable, tr)
    except ValueError:
        valid = False
    with mock.patch("earthaccess.search_data") as search, mock.patch.object(xr, "open_mfdataset") as opener:
        if valid:
            return
        with pytest.raises(ValueError):
            pipeline.build_request(dataset, variable, BOX, tr)
    search.assert_not_called()
    opener.assert_not_called()


def test_build_request_accepts_tuples_and_names_fields():
    req = pipeline.build_request("GPM_3IMERGM", "precipitation", (-10, -10, 10, 10), ("2001-01-01", "2002-01-01"), True, "Here")
    assert req.use_anomalies is True and req.region_name == "Here" and req.bounds == BOX
    with pytest.raises(ValueError, match="dataset_key"):
        pipeline.build_request("nope", "precipitation", BOX, GOOD_TR)
    with pytest.raises(ValueError, match="variable_id"):
        pipeline.build_request("GPM_3IMERGM", "T2M", BOX, GOOD_TR)
    with pytest.raises(ValueError, match="2000-06-01"):
        pipeline.build_request("GPM_3IMERGM", "precipitation", BOX, TimeRange("1990-01-01", "1991-01-01"))
    with pytest.raises(ValueError):
        pipeline.build_request("GPM_3IMERGM", "precipitation", (10, 0, -10, 5), GOOD_TR)


def fake_dataset(variable="precipitation", months=60, trend_per_year=0.0, scale=1.0):
    time = pd.date_range("2001-01-01", periods=months, freq="MS")
    lat, lon = np.arange(-9.5, 10, 1.0), np.arange(-9.5, 10, 1.0)
    base = (np.sin(np.arange(months) * 2 * np.pi / 12) + trend_per_year * np.arange(months) / 12) / scale
    data = np.broadcast_to(base[:, None, None], (months, lat.size, lon.size)).copy()
    return xr.Dataset({variable: (("time", "lat", "lon"), data)}, coords={"time": time, "lat": lat, "lon": lon})


def test_full_pipeline_with_mocks_and_unit_conversion():
    req = pipeline.build_request("GPM_3IMERGM", "precipitation", BOX, TimeRange("2001-01-01", "2020-12-31"), True, "Test box")
    granules = [make_granule(("https://h.example/x", "OPeNDAP request URL"))]
    ds = fake_dataset(months=240, trend_per_year=0.5, scale=24.0)  # raw mm/hr; +0.5 mm/day per year after x24
    with mock.patch.object(data_discovery.earthaccess, "search_data", return_value=granules), \
         mock.patch.object(data_access.xr, "open_mfdataset", return_value=ds), \
         mock.patch.object(pipeline, "_get_session", return_value=None):
        res = pipeline.run_pipeline(req)
    assert res.region_name == "Test box" and res.time_series.units == "mm/day"
    assert res.significance == "increasing" and res.linear.slope == pytest.approx(0.5, abs=0.05)
    assert res.time_series.source == "GPM_3IMERGM" and res.time_series.is_anomaly


def test_pipeline_error_when_no_opendap_links():
    req = pipeline.build_request("GPM_3IMERGM", "precipitation", BOX, GOOD_TR)
    with mock.patch.object(data_discovery.earthaccess, "search_data", return_value=[make_granule(("https://h/x", "Download"))]):
        with pytest.raises(DataDiscoveryError, match="OPeNDAP"):
            pipeline.run_pipeline(req)


def test_each_run_repeats_discovery():
    req = pipeline.build_request("GPM_3IMERGM", "precipitation", BOX, GOOD_TR)
    granules = [make_granule(("https://h.example/x", "OPeNDAP"))]
    with mock.patch.object(data_discovery.earthaccess, "search_data", return_value=granules) as search, \
         mock.patch.object(data_access.xr, "open_mfdataset", return_value=fake_dataset()), \
         mock.patch.object(pipeline, "_get_session", return_value=None):
        pipeline.run_pipeline(req)
        pipeline.run_pipeline(req)
    assert search.call_count == 2
