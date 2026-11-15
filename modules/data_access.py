"""Load NASA gridded data over OPeNDAP and reduce it to regional monthly time series."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Sequence

import numpy as np
import pandas as pd
import xarray as xr

from modules.errors import DataAccessError
from modules.models import BoundingBox, TimeRange, TimeSeriesResult, VariableMeta

OPENDAP_TIMEOUT_SECONDS = 300  # 5 minutes for slow NASA servers
MAX_URLS = 500
DEFAULT_DIMS = ("lat", "lon", "time")  # (lat_dim, lon_dim, time_dim)


# --------------------------------------------------------------------------- loading
def _http_status(exc: BaseException) -> str | None:
    response = getattr(exc, "response", None)
    code = getattr(response, "status_code", None)
    if code:
        return str(code)
    match = re.search(r"\b([45]\d{2})\b", str(exc))
    return match.group(1) if match else None


def _validate_load_args(urls: Sequence[str], variable: str, bounds: object, time_range: object) -> None:
    if not urls:
        raise DataAccessError("No OPeNDAP URLs were provided.")
    if len(urls) > MAX_URLS:
        raise DataAccessError(f"Too many OPeNDAP URLs ({len(urls)}); the maximum is {MAX_URLS}.")
    if not isinstance(variable, str) or not variable.strip():
        raise DataAccessError("The variable name must be a non-empty string.")
    if not isinstance(bounds, BoundingBox):
        raise DataAccessError("bounds must be a valid BoundingBox.")
    if not isinstance(time_range, TimeRange):
        raise DataAccessError("time_range must be a valid TimeRange.")


def mask_fill_values(da: xr.DataArray, source: xr.DataArray) -> xr.DataArray:
    """Public alias of ``_mask_fill_values`` for other modules (e.g. globe maps)."""
    return _mask_fill_values(da, source)


def _mask_fill_values(da: xr.DataArray, source: xr.DataArray) -> xr.DataArray:
    """Replace fill values that decoding left in place with NaN.

    Over pydap, MERRA-2 declares a float64 fill (999999987000000.0) for float32 data, so
    the stored value (999999986991104.0) never matches and is not masked. Casting the fill
    to the data's dtype before comparing makes the match exact.
    """
    if not np.issubdtype(da.dtype, np.floating):
        return da
    for key in ("_FillValue", "missing_value"):
        for meta in (source.encoding, source.attrs):
            fill = meta.get(key)
            if fill is None:
                continue
            for value in np.atleast_1d(fill):
                da = da.where(da != da.dtype.type(value))
    return da


def _slice_for(index: pd.Index, lo: float, hi: float) -> slice:
    """Label slice that respects ascending or descending coordinates."""
    if len(index) > 1 and index[0] > index[-1]:
        return slice(hi, lo)
    return slice(lo, hi)


def load_granules(
    opendap_urls: list[str],
    variable: str,
    bounds: BoundingBox,
    time_range: TimeRange,
    session: object | None = None,
    dims: tuple[str, str, str] = DEFAULT_DIMS,
    group: str | None = None,
    engine: str = "pydap",
    mask_variable: str | None = None,
) -> xr.Dataset:
    """Open OPeNDAP granules lazily and return only the requested subset in memory.

    If ``mask_variable`` is given, cells where that variable is missing are also set to
    missing in the result (for variables that store a real-looking value over ocean).

    Subsetting is expressed on the lazily opened dataset, so only the selected
    variable, region, and months are transferred when the data is loaded.
    """
    _validate_load_args(opendap_urls, variable, bounds, time_range)
    lat_dim, lon_dim, time_dim = dims

    def _open_and_subset() -> xr.Dataset:
        # parallel=True opens granules concurrently; each remote open costs ~10 s.
        kwargs: dict = {"engine": engine, "combine": "by_coords", "chunks": {}, "parallel": True}
        if engine == "pydap":
            kwargs["session"] = session
        if group:
            kwargs["group"] = group
        ds = xr.open_mfdataset(opendap_urls, **kwargs)
        if variable not in ds.data_vars:
            available = sorted(ds.data_vars)
            ds.close()
            raise DataAccessError(
                f"Variable {variable!r} was not found in the dataset. Available variables: {available}"
            )
        selection = {
            lat_dim: _slice_for(ds.indexes[lat_dim], bounds.min_lat, bounds.max_lat),
            lon_dim: _slice_for(ds.indexes[lon_dim], bounds.min_lon, bounds.max_lon),
            time_dim: slice(time_range.start, time_range.end),
        }
        da = ds[variable]
        subset = da.sel(selection)
        if 0 in subset.shape:
            raise DataAccessError("The requested region and time range selected no data (empty subset).")
        subset = _mask_fill_values(subset, da)
        if mask_variable and mask_variable in ds.data_vars:
            mask_source = ds[mask_variable]
            mask = _mask_fill_values(mask_source.sel(selection), mask_source)
            subset = subset.where(mask.notnull())
        return subset.to_dataset(name=variable).load()

    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_open_and_subset)
    try:
        return future.result(timeout=OPENDAP_TIMEOUT_SECONDS)
    except DataAccessError:
        raise
    except FutureTimeout as exc:
        raise DataAccessError(
            f"The OPeNDAP server did not respond within {OPENDAP_TIMEOUT_SECONDS} seconds "
            f"(timeout) for {opendap_urls[0]}."
        ) from exc
    except KeyError as exc:
        raise DataAccessError(f"Expected coordinate {exc} was not found in the dataset {opendap_urls[0]}.") from exc
    except Exception as exc:
        status = _http_status(exc)
        detail = f"HTTP status {status}" if status else "connection failure"
        raise DataAccessError(f"Could not read data from {opendap_urls[0]} ({detail}).") from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


# --------------------------------------------------------------------------- reduction
def compute_regional_average(
    ds: xr.Dataset,
    variable: str,
    bounds: BoundingBox,
    dims: tuple[str, str, str] = DEFAULT_DIMS,
) -> pd.Series:
    """Spatial mean (NaN cells skipped) per time step, as a chronologically ordered Series."""
    lat_dim, lon_dim, time_dim = dims
    if variable not in ds.data_vars:
        raise DataAccessError(f"Variable {variable!r} is not present in the dataset.")
    da = ds[variable]
    region = da.sel(
        {
            lat_dim: _slice_for(ds.indexes[lat_dim], bounds.min_lat, bounds.max_lat),
            lon_dim: _slice_for(ds.indexes[lon_dim], bounds.min_lon, bounds.max_lon),
        }
    )
    if region.sizes[lat_dim] == 0 or region.sizes[lon_dim] == 0:
        raise DataAccessError("The region contains no data: the bounding box selects zero grid cells.")

    mean = region.mean(dim=[lat_dim, lon_dim], skipna=True)  # new object; input untouched
    times = ds.indexes[time_dim]
    if hasattr(times, "to_datetimeindex"):  # cftime calendars
        times = times.to_datetimeindex()
    series = pd.Series(np.asarray(mean.values, dtype=float), index=pd.DatetimeIndex(times), name=variable)
    return series.sort_index()


def compute_monthly_anomalies(series: pd.Series) -> pd.Series:
    """Subtract each calendar month's mean (over all years) from the series."""
    if not isinstance(series, pd.Series) or len(series) == 0:
        raise ValueError("compute_monthly_anomalies requires a non-empty pandas Series.")
    if not isinstance(series.index, pd.DatetimeIndex):
        raise ValueError("compute_monthly_anomalies requires a Series with a DatetimeIndex.")
    if len(series) < 12:
        raise ValueError(f"At least 12 data points are required to compute anomalies, got {len(series)}.")
    values = series.astype(float)
    climatology = values.groupby(values.index.month).transform("mean")
    anomalies = values - climatology
    anomalies.name = series.name
    return anomalies


def apply_unit_conversion(series: pd.Series, meta: VariableMeta) -> pd.Series:
    """Convert raw dataset units to the display units in ``meta`` (returns a new Series)."""
    if meta.unit_scale == 1.0 and meta.unit_offset == 0.0:
        return series.copy()
    return series * meta.unit_scale + meta.unit_offset


def to_time_series_result(
    series: pd.Series,
    variable_meta: VariableMeta,
    region_name: str,
    source_short_name: str,
    anomaly: bool,
    anomalies: pd.Series | None = None,
) -> TimeSeriesResult:
    """Package a regional series (already in display units) for analysis and plotting."""
    return TimeSeriesResult(
        series=series,
        units=variable_meta.units,
        variable_id=variable_meta.variable_id,
        region_name=region_name,
        source=source_short_name,
        is_anomaly=anomaly,
        anomalies=anomalies,
    )
