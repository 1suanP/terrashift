"""Data models for the TerraShift app.

Request models (``BoundingBox``, ``TimeRange``, ``AnalysisRequest``) validate
their inputs on construction so invalid values never reach NASA services.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import pandas as pd


def _check_finite_number(name: str, value: object) -> float:
    """Return ``value`` as a float, or raise for non-numeric / non-finite input."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a finite number, got {type(value).__name__}")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number, got {value}")
    return float(value)


@dataclass(frozen=True)
class BoundingBox:
    """Geographic bounding box in (west, south, east, north) order."""

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    def __post_init__(self) -> None:
        values = {}
        for name in ("min_lon", "min_lat", "max_lon", "max_lat"):
            values[name] = _check_finite_number(name, getattr(self, name))
        for name in ("min_lon", "max_lon"):
            if not -180.0 <= values[name] <= 180.0:
                raise ValueError(f"{name} must be within [-180, 180], got {values[name]}")
        for name in ("min_lat", "max_lat"):
            if not -90.0 <= values[name] <= 90.0:
                raise ValueError(f"{name} must be within [-90, 90], got {values[name]}")
        if values["min_lon"] >= values["max_lon"]:
            raise ValueError(
                f"min_lon ({values['min_lon']}) must be less than max_lon ({values['max_lon']})"
            )
        if values["min_lat"] >= values["max_lat"]:
            raise ValueError(
                f"min_lat ({values['min_lat']}) must be less than max_lat ({values['max_lat']})"
            )

    def to_cmr_tuple(self) -> tuple[float, float, float, float]:
        """Return (min_lon, min_lat, max_lon, max_lat) as CMR expects."""
        return (self.min_lon, self.min_lat, self.max_lon, self.max_lat)


def _parse_iso_date(field_name: str, value: object) -> date:
    if not isinstance(value, str) or not value:
        raise ValueError(f"TimeRange.{field_name} must be an ISO date string (YYYY-MM-DD)")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"TimeRange.{field_name} is not a valid ISO date (YYYY-MM-DD): {value!r}"
        ) from exc


@dataclass(frozen=True)
class TimeRange:
    """Inclusive date range expressed as ISO ``YYYY-MM-DD`` strings."""

    start: str
    end: str

    def __post_init__(self) -> None:
        start = _parse_iso_date("start", self.start)
        end = _parse_iso_date("end", self.end)
        if start > end:
            raise ValueError(
                f"TimeRange.start ({self.start}) must be earlier than or equal to end ({self.end})"
            )

    @property
    def start_date(self) -> date:
        return date.fromisoformat(self.start)

    @property
    def end_date(self) -> date:
        return date.fromisoformat(self.end)

    def to_tuple(self) -> tuple[str, str]:
        return (self.start, self.end)


@dataclass(frozen=True)
class AnalysisRequest:
    """The canonical request produced by every user mode and consumed by the pipeline."""

    dataset_key: str
    variable_id: str
    bounds: BoundingBox
    time_range: TimeRange
    use_anomalies: bool = False
    region_name: str = "Selected region"


@dataclass(frozen=True)
class DatasetConfig:
    short_name: str
    version: str
    provider: str
    title: str
    description: str
    period_start: str
    period_end: str  # ISO date or "present"
    variables: tuple[str, ...]
    lat_dim: str = "lat"
    lon_dim: str = "lon"
    time_dim: str = "time"
    group: Optional[str] = None  # HDF5 group holding the variables (GPM IMERG uses "Grid")


@dataclass(frozen=True)
class VariableMeta:
    variable_id: str
    dataset_key: str
    long_name: str
    short_description: str
    units: str
    plain_language: str
    category: str
    trend_direction_hint: str
    # Display value = raw value * unit_scale + unit_offset (e.g. K -> degC, mm/hr -> mm/day)
    unit_scale: float = 1.0
    unit_offset: float = 0.0
    # Variable in the same granule whose missing cells also mark this one as missing
    # (e.g. MERRA-2 GWETTOP reports 1.0 over ocean; GWETROOT is missing there).
    mask_variable: Optional[str] = None


@dataclass(frozen=True)
class DemoPreset:
    name: str
    description: str
    dataset_key: str
    variable_id: str
    bounds: BoundingBox
    time_range: TimeRange
    use_anomalies: bool
    expected_insight: str


@dataclass(frozen=True)
class LinearTrendResult:
    slope: float  # change per year
    intercept: float
    r_value: float
    p_value: float
    std_err: float
    ci_lower: float
    ci_upper: float


@dataclass(frozen=True)
class MannKendallResult:
    trend: str  # "increasing" | "decreasing" | "no trend"
    h: bool
    p: float
    z: float
    tau: float
    s: float
    var_s: float
    slope: float
    intercept: float


@dataclass(eq=False)
class TimeSeriesResult:
    """Monthly regional time series. ``series`` is always the raw (unadjusted) data."""

    series: pd.Series
    units: str
    variable_id: str
    region_name: str
    source: str
    is_anomaly: bool = False
    anomalies: Optional[pd.Series] = field(default=None)


@dataclass(eq=False)
class AnalysisResult:
    time_series: TimeSeriesResult
    linear: LinearTrendResult
    mann_kendall: MannKendallResult
    sens_slope_value: float
    significance: str  # "increasing" | "decreasing" | "none"
    interpretation: str
    n_points: int
    region_name: str
    variable_meta: VariableMeta
