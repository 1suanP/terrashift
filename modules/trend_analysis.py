"""Statistical trend analysis: OLS regression, Mann-Kendall, Sen's slope, and plain-language results."""
from __future__ import annotations

import math
import numbers

import numpy as np
import pandas as pd
import pymannkendall as pymk
from scipy import stats

from config import ALPHA
from modules.data_access import compute_monthly_anomalies
from modules.errors import InsufficientDataError
from modules.models import (
    AnalysisResult,
    LinearTrendResult,
    MannKendallResult,
    TimeSeriesResult,
    VariableMeta,
)


# --------------------------------------------------------------------------- helpers
def _fractional_years(index: pd.DatetimeIndex) -> np.ndarray:
    """Year plus day-of-year divided by days in that year, so slopes are per year."""
    days_in_year = np.where(index.is_leap_year, 366.0, 365.0)
    return index.year.to_numpy(dtype=float) + index.dayofyear.to_numpy(dtype=float) / days_in_year


def _require_numeric_series(series: object, name: str = "series") -> pd.Series:
    if not isinstance(series, pd.Series):
        raise TypeError(f"{name} must be a pandas Series")
    if not pd.api.types.is_numeric_dtype(series.dtype) or pd.api.types.is_bool_dtype(series.dtype):
        raise TypeError(f"{name} must be a numeric Series")
    return series


def _sign(x: float) -> int:
    return 1 if x > 0 else (-1 if x < 0 else 0)


# --------------------------------------------------------------------------- confidence interval
def slope_confidence_interval(
    slope: float, stderr: float, n: int, confidence: float = 0.95
) -> tuple[float, float]:
    """Two-sided t-based confidence interval for a regression slope."""
    if not isinstance(slope, numbers.Real) or not math.isfinite(slope):
        raise ValueError("slope must be a finite number")
    if not isinstance(stderr, numbers.Real) or not math.isfinite(stderr) or stderr < 0:
        raise ValueError("stderr must be a finite number >= 0")
    if isinstance(n, bool) or not isinstance(n, numbers.Integral) or n < 3:
        raise ValueError("n must be an integer >= 3")
    if not isinstance(confidence, numbers.Real) or not (0.0 < confidence < 1.0):
        raise ValueError("confidence must be strictly between 0 and 1")
    if stderr == 0:
        return (float(slope), float(slope))
    t_crit = float(stats.t.ppf(1.0 - (1.0 - confidence) / 2.0, df=int(n) - 2))
    half = t_crit * float(stderr)
    return (float(slope) - half, float(slope) + half)


# --------------------------------------------------------------------------- linear regression
def linear_trend(series: pd.Series) -> LinearTrendResult:
    """OLS regression of value against fractional year (slope = change per year)."""
    _require_numeric_series(series)
    if not isinstance(series.index, pd.DatetimeIndex):
        raise ValueError("linear_trend requires a Series with a DatetimeIndex")
    clean = series.dropna()
    n = len(clean)
    if n < 2:
        raise InsufficientDataError(f"Found {n} valid data points; at least 2 are required for a linear trend.")
    x = _fractional_years(clean.index)
    if np.unique(x).size < 2:
        raise InsufficientDataError("At least 2 distinct timestamps are required for a linear trend.")
    res = stats.linregress(x, clean.to_numpy(dtype=float))
    slope, intercept = float(res.slope), float(res.intercept)
    r_value = 0.0 if math.isnan(res.rvalue) else float(res.rvalue)
    p_value = 1.0 if math.isnan(res.pvalue) else float(res.pvalue)
    std_err = 0.0 if math.isnan(res.stderr) else float(res.stderr)
    if n >= 3:
        ci_lower, ci_upper = slope_confidence_interval(slope, std_err, n)
    else:
        ci_lower, ci_upper = slope, slope
    return LinearTrendResult(slope, intercept, r_value, p_value, std_err, ci_lower, ci_upper)


# --------------------------------------------------------------------------- Mann-Kendall / Sen
def mann_kendall(
    series: pd.Series, seasonal: bool = False, period: int = 12, alpha: float = ALPHA
) -> MannKendallResult:
    """Mann-Kendall monotonic trend test (optionally seasonal)."""
    _require_numeric_series(series)
    if series.ndim != 1:
        raise ValueError("series must be one-dimensional")
    if isinstance(alpha, bool) or not isinstance(alpha, numbers.Real) or not (0.001 <= alpha <= 0.5):
        raise ValueError("alpha must be between 0.001 and 0.5")
    if seasonal and (isinstance(period, bool) or not isinstance(period, numbers.Integral) or period < 2):
        raise ValueError("period must be an integer of at least 2 when seasonal=True")
    values = series.dropna().to_numpy(dtype=float)
    if len(values) < 3:
        raise ValueError(f"At least 3 non-NaN values are required, got {len(values)}")
    if seasonal and len(values) < 2 * int(period):
        raise ValueError(f"Seasonal test needs at least {2 * int(period)} non-NaN values, got {len(values)}")

    if seasonal:
        raw = pymk.seasonal_test(values, period=int(period), alpha=alpha)
    else:
        raw = pymk.original_test(values, alpha=alpha)
    p = float(raw.p)
    h = bool(p < alpha)
    z = float(raw.z)
    trend = "no trend" if not h else ("increasing" if z > 0 else "decreasing")
    return MannKendallResult(
        trend=trend, h=h, p=p, z=z, tau=float(raw.Tau), s=float(raw.s),
        var_s=float(raw.var_s), slope=float(raw.slope), intercept=float(raw.intercept),
    )


def _pairwise_median_slope(x: np.ndarray, y: np.ndarray) -> float:
    i, j = np.triu_indices(len(y), k=1)
    dx = x[j] - x[i]
    keep = dx != 0
    return float(np.median((y[j][keep] - y[i][keep]) / dx[keep]))


def sens_slope(series: pd.Series) -> float:
    """Median of pairwise slopes over index positions 0, 1, 2, ... after dropping NaN."""
    _require_numeric_series(series)
    values = series.dropna().to_numpy(dtype=float)
    if len(values) < 2:
        raise ValueError("At least 2 non-NaN values are required for Sen's slope")
    return _pairwise_median_slope(np.arange(len(values), dtype=float), values)


# --------------------------------------------------------------------------- significance
def classify_significance(p_value: float, slope: float, alpha: float = ALPHA) -> str:
    """Return ``"increasing"``, ``"decreasing"`` or ``"none"``."""
    if isinstance(alpha, bool) or not isinstance(alpha, numbers.Real) or math.isnan(alpha) or not (0.0 < alpha < 1.0):
        raise ValueError("alpha must be strictly between 0 and 1")
    if not isinstance(p_value, numbers.Real):
        raise ValueError("p_value must be a number")
    if math.isnan(p_value):
        return "none"
    if p_value < 0.0 or p_value > 1.0:
        raise ValueError("p_value must be within [0, 1]")
    if p_value >= alpha or not isinstance(slope, numbers.Real) or math.isnan(slope) or slope == 0:
        return "none"
    return "increasing" if slope > 0 else "decreasing"


def _format_rate(value: float) -> str:
    """Absolute value rounded to 2 significant figures, never in scientific notation."""
    value = abs(float(value))
    if value == 0:
        return "0"
    digits = 1 - int(math.floor(math.log10(value)))
    rounded = round(value, digits)
    return f"{rounded:.{max(digits, 0)}f}"


def interpret_trend(
    linear: LinearTrendResult,
    mk: MannKendallResult,
    variable_meta: VariableMeta,
    region_name: str,
    alpha: float = ALPHA,
) -> str:
    """Plain-language answer to: what, where, how much, and is it significant."""
    if linear is None:
        raise ValueError("linear result is required")
    if mk is None:
        raise ValueError("mann_kendall result is required")
    if variable_meta is None or not variable_meta.plain_language:
        raise ValueError("variable_meta with a plain_language description is required")
    if not isinstance(region_name, str) or not region_name.strip():
        raise ValueError("region_name must be a non-empty string")

    what = variable_meta.long_name[:1].lower() + variable_meta.long_name[1:]
    lin_dir = _sign(linear.slope)
    mk_dir = _sign(mk.slope) if mk.trend == "no trend" else (1 if mk.trend == "increasing" else -1)

    if lin_dir == 0:
        return (
            f"In {region_name}, {what} is not changing over this period. "
            "This is not statistically significant, so there is no clear trend."
        )

    word = "increasing" if lin_dir > 0 else "decreasing"
    first = f"In {region_name}, {what} is {word} by about {_format_rate(linear.slope)} {variable_meta.units} per year."

    if mk_dir != 0 and mk_dir != lin_dir:
        second = (
            "The two statistical tests disagree about the direction of change, "
            "so this trend is not statistically significant."
        )
        return f"{first} {second}"

    significant = linear.p_value < alpha and mk.trend == word
    mk_agrees = mk_dir == lin_dir
    if significant:
        tests = "linear regression and the Mann-Kendall test" if mk_agrees else "linear regression"
        second = f"This change is statistically significant, confirmed by {tests}."
    else:
        tests = "Linear regression and the Mann-Kendall test agree on the direction" if mk_agrees else "Linear regression shows this direction"
        second = (
            "This change is not statistically significant, so it could be natural variation. "
            f"{tests}."
        )
    return f"{first} {second}"


# --------------------------------------------------------------------------- full analysis
def analyze(
    series: pd.Series,
    variable_meta: VariableMeta,
    region_name: str,
    use_anomalies: bool = False,
    source: str | None = None,
    alpha: float = ALPHA,
) -> AnalysisResult:
    """Run every trend method on a monthly regional series and assemble an ``AnalysisResult``.

    The input series is never modified. ``sens_slope_value`` is expressed per year.
    """
    _require_numeric_series(series)
    if not isinstance(series.index, pd.DatetimeIndex):
        raise ValueError("analyze requires a Series with a DatetimeIndex")
    if not isinstance(region_name, str) or not region_name.strip():
        raise ValueError("region_name must be a non-empty string")

    raw = series.copy()
    n_valid = int(raw.notna().sum())
    if n_valid < 2:
        raise InsufficientDataError(f"Only {n_valid} valid data points were received; at least 2 are required.")

    anomalies = None
    working = raw
    if use_anomalies:
        if len(raw) < 12:
            raise InsufficientDataError(
                f"Removing the seasonal cycle needs at least 12 months of data; received {len(raw)}."
            )
        anomalies = compute_monthly_anomalies(raw)
        working = anomalies
    clean = working.dropna()
    if len(clean) < 2:
        raise InsufficientDataError(f"Only {len(clean)} valid data points remain; at least 2 are required.")

    linear = linear_trend(clean)
    if len(clean) >= 3:
        mk = mann_kendall(clean, alpha=alpha)
    else:  # Mann-Kendall needs 3 points; report "no trend" for a two-point series
        mk = MannKendallResult("no trend", False, 1.0, 0.0, 0.0, 0.0, 0.0, linear.slope, linear.intercept)
    x = _fractional_years(clean.index)
    sens_per_year = _pairwise_median_slope(x, clean.to_numpy(dtype=float))

    direction = "increasing" if linear.slope > 0 else "decreasing"
    significance = mk.trend if (linear.p_value < alpha and mk.trend == direction) else "none"

    interpretation = interpret_trend(linear, mk, variable_meta, region_name, alpha=alpha)
    ts = TimeSeriesResult(
        series=raw,
        units=variable_meta.units,
        variable_id=variable_meta.variable_id,
        region_name=region_name,
        source=source or variable_meta.dataset_key,
        is_anomaly=bool(use_anomalies),
        anomalies=anomalies,
    )
    return AnalysisResult(
        time_series=ts,
        linear=linear,
        mann_kendall=mk,
        sens_slope_value=sens_per_year,
        significance=significance,
        interpretation=interpretation,
        n_points=len(clean),
        region_name=region_name,
        variable_meta=variable_meta,
    )
