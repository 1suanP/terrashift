"""Does a dataset actually have data at a place? Answered from real NASA grids.

Some datasets only cover part of the planet: MERRA-2 land variables have no value over
oceans or ice sheets, the ocean-surface collection has none over land, and GPM IMERG
thins out near the poles. Before offering an analysis we sample one reference month of
the dataset's own grid (cached on disk after the first read) and check whether any cell
in the analysis box holds a value.

Datasets with a global, gap-free grid (MERRA-2 single-level, flux, aerosol) are reported
available everywhere without a lookup.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import numpy as np

import config
from modules import global_maps

logger = logging.getLogger(__name__)

# A month every probe dataset has published. Read once, then served from the disk cache.
REFERENCE_MONTH = (2025, 1)

# Which grid answers coverage for each dataset (variables with their own map layer use it).
DATASET_PROBES: dict[str, str] = {
    "GPM_3IMERGM": "GPM_3IMERGM/precipitation",
    "M2TMNXLND": "M2TMNXLND/GWETTOP",  # land, excluding ice sheets
    "M2TMNXOCN": "M2TMNXOCN/TSKINWTR",  # open water
}
GLOBAL_DATASETS = {"M2TMNXSLV", "M2TMNXFLX", "M2TMNXAER"}

REASONS = {
    "M2TMNXLND": "This MERRA-2 land variable has no values over oceans, lakes or ice sheets.",
    "M2TMNXOCN": "This MERRA-2 variable only has values over open water.",
    "GPM_3IMERGM": "GPM IMERG has no values here (it is thinnest near the poles).",
}


@dataclass(frozen=True)
class Box:
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float


def box_around_point(lat: float, lon: float, dataset_key: str) -> Box:
    """Same rule as the frontend (lib/geo.ts boxAroundPoint): at least one grid cell."""
    half = 0.25 if dataset_key == "GPM_3IMERGM" else 0.5
    clamp = lambda v, lo, hi: min(hi, max(lo, v))  # noqa: E731
    return Box(
        clamp(lat - half, -90, 90 - 2 * half), clamp(lat + half, -90 + 2 * half, 90),
        clamp(lon - half, -180, 180 - 2 * half), clamp(lon + half, -180 + 2 * half, 180),
    )


def valid_cells(grid: global_maps.MapGrid, box: Box) -> int:
    """Number of grid cells with data inside the box (nearest cell if the box is tiny)."""
    lat_idx = np.where((grid.lat >= box.min_lat) & (grid.lat <= box.max_lat))[0]
    lon_idx = np.where((grid.lon >= box.min_lon) & (grid.lon <= box.max_lon))[0]
    if lat_idx.size == 0:
        lat_idx = np.array([int(np.abs(grid.lat - (box.min_lat + box.max_lat) / 2).argmin())])
    if lon_idx.size == 0:
        lon_idx = np.array([int(np.abs(grid.lon - (box.min_lon + box.max_lon) / 2).argmin())])
    block = grid.values[np.ix_(lat_idx, lon_idx)]
    return int(np.isfinite(block).sum())


def _probe_key(variable_key: str) -> str | None:
    if variable_key in global_maps.MAP_LAYERS and variable_key.split("/")[0] not in GLOBAL_DATASETS:
        return variable_key
    return DATASET_PROBES.get(variable_key.split("/", 1)[0])


def check(point: tuple[float, float] | None = None, box: Box | None = None) -> dict:
    """Coverage of every analyzable variable for a point or a box."""
    if (point is None) == (box is None):
        raise ValueError("give exactly one of point or box")
    probes = sorted({k for k in (_probe_key(v) for v in config.VARIABLES) if k})

    def load(key: str):
        try:
            return key, global_maps.load_month(key, *REFERENCE_MONTH)
        except Exception as exc:  # NASA unreachable: report "unknown", never guess
            logger.warning("coverage probe %s failed: %s", key, exc)
            return key, None

    with ThreadPoolExecutor(max_workers=4) as pool:
        grids = dict(pool.map(load, probes))

    out: dict[str, dict] = {}
    for key in config.VARIABLES:
        dataset_key = key.split("/", 1)[0]
        b = box or box_around_point(point[0], point[1], dataset_key)  # type: ignore[index]
        probe = _probe_key(key)
        if dataset_key in GLOBAL_DATASETS:
            out[key] = {"status": "available", "reason": "Global coverage."}
        elif probe is None or grids.get(probe) is None:
            out[key] = {"status": "unknown", "reason": "Coverage could not be checked right now."}
        elif valid_cells(grids[probe], b) > 0:
            out[key] = {"status": "available", "reason": "The dataset has values here."}
        else:
            out[key] = {"status": "no_data_here", "reason": REASONS.get(dataset_key, "No values in this area.")}
    return {"reference_month": f"{REFERENCE_MONTH[0]}-{REFERENCE_MONTH[1]:02d}", "variables": out}
