"""Coarse global monthly maps for the 3D globe overlay.

Only real NASA data is served. Each map is one monthly granule read over OPeNDAP with a
stride (e.g. every 5th cell of GPM's 0.1 degree grid = 0.5 degrees), so a whole-world map
is ~260k values instead of 6.5M. Strided cells are a *sample*, not a block average; the
API reports the effective resolution so the UI can say so.

Maps are cached on disk (``backend/cache/maps``) because each NASA read costs ~8 s.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import xarray as xr

import config
from modules import data_access, data_discovery
from modules.errors import DataAccessError, DataDiscoveryError

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent / "backend" / "cache" / "maps"
MONTHS_TTL_SECONDS = 6 * 3600
GLOBAL_BOX = (-180.0, -90.0, 180.0, 90.0)


@dataclass(frozen=True)
class MapLayer:
    """A variable that can be drawn on the globe."""

    key: str  # "dataset/variable"
    stride: int
    month_pattern: str  # regex with (year)(month) groups, matched against the OPeNDAP URL
    native_resolution_deg: float
    legend_max: float  # top of the color scale, in display units
    resolution_label: str = ""
    decimals: int = 1


_MERRA2_MONTH = r"_Nx\.(\d{4})(\d{2})\.nc4"

MAP_LAYERS: dict[str, MapLayer] = {
    "GPM_3IMERGM/precipitation": MapLayer(
        key="GPM_3IMERGM/precipitation",
        stride=5,
        month_pattern=r"3IMERG\.(\d{4})(\d{2})01-S",
        native_resolution_deg=0.1,
        legend_max=20.0,
        resolution_label="0.5\u00b0 sample of the 0.1\u00b0 grid",
    ),
    # MERRA-2 grids are small (576 x 361), so they are served at full resolution.
    "M2TMNXSLV/T2M": MapLayer(
        key="M2TMNXSLV/T2M",
        stride=1,
        month_pattern=_MERRA2_MONTH,
        native_resolution_deg=0.5,
        legend_max=40.0,
        resolution_label="0.5\u00b0 \u00d7 0.625\u00b0 (full grid)",
    ),
    "M2TMNXLND/GWETROOT": MapLayer(
        key="M2TMNXLND/GWETROOT",
        stride=1,
        month_pattern=_MERRA2_MONTH,
        native_resolution_deg=0.5,
        legend_max=100.0,
        resolution_label="0.5\u00b0 \u00d7 0.625\u00b0 (full grid, land only)",
        decimals=0,
    ),
    "M2TMNXLND/GWETTOP": MapLayer(
        key="M2TMNXLND/GWETTOP",
        stride=1,
        month_pattern=_MERRA2_MONTH,
        native_resolution_deg=0.5,
        legend_max=100.0,
        resolution_label="0.5\u00b0 \u00d7 0.625\u00b0 (full grid, land only)",
        decimals=0,
    ),
    # Used by the coverage check (open-water mask); not drawn as a globe layer yet.
    "M2TMNXOCN/TSKINWTR": MapLayer(
        key="M2TMNXOCN/TSKINWTR",
        stride=1,
        month_pattern=_MERRA2_MONTH,
        native_resolution_deg=0.5,
        legend_max=35.0,
        resolution_label="0.5\u00b0 \u00d7 0.625\u00b0 (full grid, open water only)",
    ),
    "M2TMNXFLX/EVAP": MapLayer(
        key="M2TMNXFLX/EVAP",
        stride=1,
        month_pattern=_MERRA2_MONTH,
        native_resolution_deg=0.5,
        legend_max=8.0,
        resolution_label="0.5\u00b0 \u00d7 0.625\u00b0 (full grid)",
        decimals=2,
    ),
}


@dataclass
class MapGrid:
    lat: np.ndarray  # ascending
    lon: np.ndarray  # ascending
    values: np.ndarray  # shape (lat, lon), display units, NaN = no data


# --------------------------------------------------------------------------- auth / session
_auth_lock = threading.Lock()
_authenticated = False


def _session():
    global _authenticated
    with _auth_lock:
        if not _authenticated:
            data_discovery.authenticate(persist=False)
            _authenticated = True
    import earthaccess

    return earthaccess.get_requests_https_session()


def _reset_auth() -> None:
    global _authenticated
    with _auth_lock:
        _authenticated = False


# --------------------------------------------------------------------------- availability
_months_lock = threading.Lock()
_months_cache: dict[tuple[str, int], tuple[float, dict[int, str]]] = {}


def get_layer(key: str) -> MapLayer:
    if key not in MAP_LAYERS:
        raise KeyError(f"No globe map layer for {key!r}; available: {sorted(MAP_LAYERS)}")
    return MAP_LAYERS[key]


def _validate_year(dataset_key: str, year: int) -> None:
    start, end = config.dataset_period(dataset_key)
    if not isinstance(year, int) or not start.year <= year <= end.year:
        raise ValueError(f"year must be between {start.year} and {end.year}")


def available_months(key: str, year: int) -> dict[int, str]:
    """Map of month number -> OPeNDAP URL for granules NASA has published in ``year``."""
    layer = get_layer(key)
    dataset_key = key.split("/", 1)[0]
    _validate_year(dataset_key, year)
    cache_key = (key, year)
    with _months_lock:  # one CMR search per year even when 12 map requests arrive at once
        cached = _months_cache.get(cache_key)
        if cached and time.time() - cached[0] < MONTHS_TTL_SECONDS:
            return cached[1]
        dataset = config.DATASETS[dataset_key]
        start, end = config.dataset_period(dataset_key)
        first = max(date(year, 1, 1), start)
        last = min(date(year, 12, 31), end)
        try:
            granules = data_discovery.search_granules(
                dataset.short_name, (first.isoformat(), last.isoformat()), GLOBAL_BOX, version=dataset.version
            )
        except DataDiscoveryError as exc:
            if "No granules were found" not in str(exc):
                raise
            granules = []  # nothing published for this year yet (e.g. the current year)
        months: dict[int, str] = {}
        pattern = re.compile(layer.month_pattern)
        for url in data_discovery.get_opendap_urls(granules):
            match = pattern.search(url)
            if match and int(match.group(1)) == year:
                months[int(match.group(2))] = url
        _months_cache[cache_key] = (time.time(), months)
        return months


# --------------------------------------------------------------------------- map loading
def _cache_path(key: str, year: int, month: int, stride: int) -> Path:
    safe = key.replace("/", "_")
    return CACHE_DIR / f"{safe}_{year:04d}-{month:02d}_s{stride}.npz"


def _read_granule(url: str, key: str, stride: int) -> MapGrid:
    dataset_key, variable_id = key.split("/", 1)
    dataset = config.DATASETS[dataset_key]
    meta = config.get_variable_meta(dataset_key, variable_id)
    kwargs: dict = {"engine": "pydap", "session": _session()}
    if dataset.group:
        kwargs["group"] = dataset.group
    ds = xr.open_dataset(url, **kwargs)
    try:
        if variable_id not in ds.data_vars:
            raise DataAccessError(f"Variable {variable_id!r} is not in {url}")
        da = ds[variable_id]
        sub = da.isel({dataset.time_dim: 0, dataset.lat_dim: slice(None, None, stride),
                       dataset.lon_dim: slice(None, None, stride)})
        sub = sub.transpose(dataset.lat_dim, dataset.lon_dim).load()
        sub = data_access.mask_fill_values(sub, da)
        if meta.mask_variable and meta.mask_variable in ds.data_vars:
            mask_src = ds[meta.mask_variable]
            mask = mask_src.isel({dataset.time_dim: 0, dataset.lat_dim: slice(None, None, stride),
                                  dataset.lon_dim: slice(None, None, stride)})
            mask = data_access.mask_fill_values(mask.transpose(dataset.lat_dim, dataset.lon_dim).load(), mask_src)
            sub = sub.where(mask.notnull())
        values = sub.values.astype(np.float64) * meta.unit_scale + meta.unit_offset
        if dataset_key == "GPM_3IMERGM":
            values[values < 0] = np.nan  # negative rain is a fill artefact
        lat = sub[dataset.lat_dim].values.astype(np.float64)
        lon = sub[dataset.lon_dim].values.astype(np.float64)
    finally:
        ds.close()
    if lat[0] > lat[-1]:
        lat, values = lat[::-1], values[::-1, :]
    return MapGrid(lat=lat, lon=lon, values=values)


def load_month(key: str, year: int, month: int) -> MapGrid:
    """Return the global map for one month, reading NASA only on a cache miss."""
    layer = get_layer(key)
    if not isinstance(month, int) or not 1 <= month <= 12:
        raise ValueError("month must be between 1 and 12")
    path = _cache_path(key, year, month, layer.stride)
    if path.is_file():
        with np.load(path) as f:
            return MapGrid(lat=f["lat"], lon=f["lon"], values=f["values"])
    urls = available_months(key, year)
    if month not in urls:
        raise DataDiscoveryError(f"NASA has not published {key} for {year}-{month:02d} yet.")
    try:
        grid = _read_granule(urls[month], key, layer.stride)
    except Exception as exc:
        if "401" in str(exc) or "403" in str(exc):
            _reset_auth()  # session expired: re-login once
            grid = _read_granule(urls[month], key, layer.stride)
        else:
            raise
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, lat=grid.lat, lon=grid.lon, values=grid.values.astype(np.float32))
    tmp.replace(path)
    return grid


def grid_payload(grid: MapGrid, decimals: int = 2) -> dict:
    """JSON-friendly payload: row-major values from south to north, ``None`` for no data."""
    lat_step = float(np.median(np.diff(grid.lat))) if grid.lat.size > 1 else 0.0
    lon_step = float(np.median(np.diff(grid.lon))) if grid.lon.size > 1 else 0.0
    flat = np.round(grid.values.astype(np.float64), decimals).ravel()
    values = [None if np.isnan(v) else float(v) for v in flat]
    finite = grid.values[np.isfinite(grid.values)]
    return {
        "lat_count": int(grid.lat.size),
        "lon_count": int(grid.lon.size),
        "lat_start": float(grid.lat[0]),
        "lon_start": float(grid.lon[0]),
        "lat_step": lat_step,
        "lon_step": lon_step,
        "values": values,
        "min": float(finite.min()) if finite.size else None,
        "max": float(finite.max()) if finite.size else None,
    }
