"""Property 21 and unit tests for load_granules. Validates Requirements 10.1-10.7."""
from unittest import mock

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from hypothesis import HealthCheck, given, settings, strategies as st

from modules import data_access as da
from modules.data_access import DataAccessError, load_granules
from modules.models import BoundingBox, TimeRange

URLS = ["dap4://example.org/a.nc4"]


def global_ds(descending_lat=False) -> xr.Dataset:
    lat = np.arange(-89.5, 90, 1.0)
    if descending_lat:
        lat = lat[::-1]
    lon = np.arange(-179.5, 180, 1.0)
    time = pd.date_range("2000-01-01", periods=36, freq="MS")
    rng = np.random.default_rng(0)
    return xr.Dataset(
        {
            "precipitation": (("time", "lon", "lat"), rng.random((36, lon.size, lat.size))),
            "other": (("time", "lon", "lat"), rng.random((36, lon.size, lat.size))),
        },
        coords={"time": time, "lat": lat, "lon": lon},
    )


@pytest.mark.parametrize("descending", [False, True])
def test_subset_matches_request(descending):
    box, tr = BoundingBox(-20, -10, 30, 15), TimeRange("2000-06-01", "2001-05-31")
    with mock.patch.object(da.xr, "open_mfdataset", return_value=global_ds(descending)):
        out = load_granules(URLS, "precipitation", box, tr)
    assert list(out.data_vars) == ["precipitation"]
    assert out.lat.min() >= -10 and out.lat.max() <= 15
    assert out.lon.min() >= -20 and out.lon.max() <= 30
    assert str(out.time.min().values)[:10] >= "2000-06-01" and str(out.time.max().values)[:10] <= "2001-05-31"
    assert out.sizes["time"] == 12


lon_ = st.floats(-170, 170)
lat_ = st.floats(-80, 80)


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(lon_, lon_, lat_, lat_)
def test_property_only_requested_variable_and_bounds(a, b, c, d):
    if abs(a - b) < 2 or abs(c - d) < 2:
        return
    box = BoundingBox(min(a, b), min(c, d), max(a, b), max(c, d))
    with mock.patch.object(da.xr, "open_mfdataset", return_value=global_ds()):
        out = load_granules(URLS, "precipitation", box, TimeRange("2000-01-01", "2002-12-31"))
    assert set(out.data_vars) == {"precipitation"}
    assert out.lat.min() >= box.min_lat and out.lat.max() <= box.max_lat
    assert out.lon.min() >= box.min_lon and out.lon.max() <= box.max_lon


BOX, TR = BoundingBox(0, 0, 10, 10), TimeRange("2000-01-01", "2000-12-31")


def test_missing_variable_lists_available():
    with mock.patch.object(da.xr, "open_mfdataset", return_value=global_ds()):
        with pytest.raises(DataAccessError) as err:
            load_granules(URLS, "nope", BOX, TR)
    assert "nope" in str(err.value) and "precipitation" in str(err.value)


def test_empty_subset():
    with mock.patch.object(da.xr, "open_mfdataset", return_value=global_ds()):
        with pytest.raises(DataAccessError, match="empty"):
            load_granules(URLS, "precipitation", BOX, TimeRange("2030-01-01", "2030-12-31"))


def test_http_error_reports_url_and_status():
    with mock.patch.object(da.xr, "open_mfdataset", side_effect=OSError("HTTP Error 503: Service Unavailable")):
        with pytest.raises(DataAccessError) as err:
            load_granules(URLS, "precipitation", BOX, TR)
    assert URLS[0] in str(err.value) and "503" in str(err.value)


def test_connection_failure_message():
    with mock.patch.object(da.xr, "open_mfdataset", side_effect=ConnectionError("refused")):
        with pytest.raises(DataAccessError, match="connection failure"):
            load_granules(URLS, "precipitation", BOX, TR)


def test_timeout(monkeypatch):
    import time

    monkeypatch.setattr(da, "OPENDAP_TIMEOUT_SECONDS", 0.05)
    with mock.patch.object(da.xr, "open_mfdataset", side_effect=lambda *a, **k: time.sleep(0.5)):
        with pytest.raises(DataAccessError, match="timeout"):
            load_granules(URLS, "precipitation", BOX, TR)


@pytest.mark.parametrize(
    "args",
    [([], "precipitation", BOX, TR), (URLS, "", BOX, TR), (URLS, "precipitation", None, TR), (URLS, "precipitation", BOX, None)],
)
def test_invalid_args_never_contact_server(args):
    with mock.patch.object(da.xr, "open_mfdataset") as opener:
        with pytest.raises(DataAccessError):
            load_granules(*args)
    opener.assert_not_called()


def test_real_open_mfdataset_on_local_files(tmp_path):
    """No mocks: exercise xarray.open_mfdataset + dask with real netCDF files and a group."""
    paths = []
    full = global_ds()
    for year, chunk in full.groupby("time.year"):
        path = tmp_path / f"granule_{year}.nc"
        chunk.to_netcdf(path, group="Grid", engine="netcdf4")
        paths.append(str(path))
    out = load_granules(paths, "precipitation", BoundingBox(-20, -10, 30, 15), TimeRange("2000-06-01", "2001-05-31"),
                        engine="netcdf4", group="Grid")
    assert list(out.data_vars) == ["precipitation"] and out.sizes["time"] == 12
    assert float(out.lat.min()) >= -10 and float(out.lon.max()) <= 30
