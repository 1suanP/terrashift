"""
Globe map routes - real NASA monthly global maps for the 3D Earth overlay
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

import config
from modules import coverage as coverage_mod
from modules import global_maps
from modules.errors import DataAccessError, DataDiscoveryError

router = APIRouter()


def _layer_or_404(dataset_key: str, variable_id: str) -> global_maps.MapLayer:
    try:
        return global_maps.get_layer(f"{dataset_key}/{variable_id}")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@router.get("/layers")
def list_layers() -> Dict[str, Any]:
    """Variables that can be drawn as a global map on the globe."""
    layers = []
    for key, layer in global_maps.MAP_LAYERS.items():
        dataset_key, variable_id = key.split("/", 1)
        meta = config.get_variable_meta(dataset_key, variable_id)
        start, end = config.dataset_period(dataset_key)
        layers.append({
            "key": key,
            "dataset_key": dataset_key,
            "variable_id": variable_id,
            "name": meta.long_name,
            "units": meta.units,
            "legend_max": layer.legend_max,
            "resolution_label": layer.resolution_label,
            "source": f"{config.DATASETS[dataset_key].title} ({dataset_key})",
            "resolution_deg": layer.native_resolution_deg * layer.stride,
            "native_resolution_deg": layer.native_resolution_deg,
            "first_year": start.year,
            "last_year": end.year,
        })
    return {"layers": layers}


@router.get("/coverage")
def coverage(
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lon: Optional[float] = Query(None, ge=-180, le=180),
    min_lat: Optional[float] = Query(None, ge=-90, le=90),
    max_lat: Optional[float] = Query(None, ge=-90, le=90),
    min_lon: Optional[float] = Query(None, ge=-180, le=180),
    max_lon: Optional[float] = Query(None, ge=-180, le=180),
) -> Dict[str, Any]:
    """Which variables have real data at a point (lat, lon) or in a box."""
    box_args = (min_lat, max_lat, min_lon, max_lon)
    if lat is not None and lon is not None and all(v is None for v in box_args):
        return coverage_mod.check(point=(lat, lon))
    if all(v is not None for v in box_args) and lat is None and lon is None:
        if not (min_lat < max_lat and min_lon < max_lon):  # type: ignore[operator]
            raise HTTPException(status_code=400, detail="Box needs min < max for both latitude and longitude.")
        return coverage_mod.check(box=coverage_mod.Box(min_lat, max_lat, min_lon, max_lon))  # type: ignore[arg-type]
    raise HTTPException(status_code=400, detail="Give either lat and lon, or min_lat, max_lat, min_lon and max_lon.")


@router.get("/{dataset_key}/{variable_id}/months")
def months(dataset_key: str, variable_id: str, year: int = Query(...)) -> Dict[str, Any]:
    """Months of ``year`` that NASA has actually published (asks NASA's CMR catalogue)."""
    layer = _layer_or_404(dataset_key, variable_id)
    try:
        available = global_maps.available_months(layer.key, year)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except DataDiscoveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    return {"year": year, "months": sorted(available)}


@router.get("/{dataset_key}/{variable_id}")
def month_map(
    dataset_key: str,
    variable_id: str,
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
) -> Dict[str, Any]:
    """One month's global map (real data, sampled on a coarse grid)."""
    layer = _layer_or_404(dataset_key, variable_id)
    meta = config.get_variable_meta(dataset_key, variable_id)
    dataset = config.DATASETS[dataset_key]
    try:
        grid = global_maps.load_month(layer.key, year, month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except DataDiscoveryError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except DataAccessError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from None
    except Exception as exc:  # network errors from NASA
        raise HTTPException(status_code=502, detail=f"Could not read the NASA map: {exc}") from None
    return {
        "key": layer.key,
        "year": year,
        "month": month,
        "units": meta.units,
        "name": meta.long_name,
        "source": f"{dataset.title} ({dataset.short_name} v{dataset.version}), NASA GES DISC",
        "sampling_note": (
            f"Every {layer.stride}th cell of the {layer.native_resolution_deg}\u00b0 grid "
            f"({layer.native_resolution_deg * layer.stride:g}\u00b0 spacing). Monthly mean, not real-time."
            if layer.stride > 1
            else f"Full {layer.resolution_label or 'native'} grid. Monthly mean, not real-time."
        ),
        "legend_max": layer.legend_max,
        **global_maps.grid_payload(grid, decimals=layer.decimals),
    }
