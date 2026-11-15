"""The single analysis pipeline shared by Guided, Expert, and Demo modes.

``build_request`` validates user input against ``config`` before any network call.
``run_pipeline`` then runs: search -> OPeNDAP URLs -> load -> regional mean -> units -> analyze.
Every call re-runs discovery, so a retry always refreshes granule URLs.
"""
from __future__ import annotations

import config
from modules import data_access, data_discovery
from modules.errors import DataAccessError, DataDiscoveryError
from modules.models import AnalysisRequest, AnalysisResult, BoundingBox, TimeRange
from modules.trend_analysis import analyze


def build_request(
    dataset_key: object,
    variable_id: object,
    bounds: BoundingBox | tuple,
    time_range: TimeRange | tuple,
    use_anomalies: bool = False,
    region_name: str = "Selected region",
) -> AnalysisRequest:
    """Construct a validated ``AnalysisRequest``. Raises ``ValueError``/``TypeError``; no network access."""
    if not isinstance(bounds, BoundingBox):
        bounds = BoundingBox(*bounds)
    if not isinstance(time_range, TimeRange):
        time_range = TimeRange(*time_range)
    config.validate_request(dataset_key, variable_id, time_range)
    return AnalysisRequest(
        dataset_key=dataset_key,  # type: ignore[arg-type]
        variable_id=variable_id,  # type: ignore[arg-type]
        bounds=bounds,
        time_range=time_range,
        use_anomalies=bool(use_anomalies),
        region_name=region_name or "Selected region",
    )


def _get_session():
    """Authenticated HTTP session for OPeNDAP, or ``None`` if unavailable."""
    try:
        import earthaccess

        return earthaccess.get_requests_https_session()
    except Exception:
        return None


def run_pipeline(request: AnalysisRequest) -> AnalysisResult:
    """Run the full analysis for a request. Assumes Earthdata Login has succeeded."""
    config.validate_request(request.dataset_key, request.variable_id, request.time_range)
    dataset = config.DATASETS[request.dataset_key]
    meta = config.get_variable_meta(request.dataset_key, request.variable_id)

    granules = data_discovery.search_granules(
        dataset.short_name, request.time_range.to_tuple(), request.bounds.to_cmr_tuple(), version=dataset.version
    )
    urls = data_discovery.get_opendap_urls(granules)
    if not urls:
        raise DataDiscoveryError(
            f"The {dataset.short_name} granules found for this request do not offer OPeNDAP access."
        )

    dims = (dataset.lat_dim, dataset.lon_dim, dataset.time_dim)
    ds = data_access.load_granules(
        urls, request.variable_id, request.bounds, request.time_range, session=_get_session(), dims=dims,
        group=dataset.group, mask_variable=meta.mask_variable,
    )
    raw = data_access.compute_regional_average(ds, request.variable_id, request.bounds, dims=dims)
    series = data_access.apply_unit_conversion(raw, meta)
    return analyze(
        series, meta, request.region_name, use_anomalies=request.use_anomalies, source=dataset.short_name
    )


__all__ = ["build_request", "run_pipeline", "DataAccessError", "DataDiscoveryError"]
